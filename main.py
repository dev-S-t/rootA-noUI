# --- BEGIN SQLITE PATCH ---
# This MUST be at the very top, before any imports that might load sqlite3 indirectly (like chromadb)
import sys
SQLITE_PATCHED = False
try:
    import pysqlite3
    sys.modules['sqlite3'] = pysqlite3
    SQLITE_PATCHED = True
    print(f"Successfully patched sqlite3 with pysqlite3 in FastAPI app. Using SQLite version: {pysqlite3.sqlite_version}")
except ImportError:
    print("WARNING (FastAPI app): pysqlite3 module not found. Ensure 'pysqlite3-binary' is installed in the correct environment. Falling back to system sqlite3.")
except Exception as e:
    print(f"WARNING (FastAPI app): An unexpected error occurred while trying to patch sqlite3 with pysqlite3: {e}. Falling back to system sqlite3.")
# --- END SQLITE PATCH ---



import os
import asyncio
import shutil
from fastapi import FastAPI, Request, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse, StreamingResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
import json
from typing import List, Optional
import pathlib
from pydantic import BaseModel

from multi_tool_agent.agent import AGENT, SESSION_SERVICE, MEMORY_SERVICE, APP_NAME, get_vector_db_path, root_agent as agent_root_agent, DEFAULT_ROOT_AGENT_INSTRUCTION
import multi_tool_agent.agent as agent_module

from google.adk.runners import Runner
from google.genai import types

from rag_builder import process_documents_and_build_db, load_environment as load_rag_env

app = FastAPI()

security = HTTPBasic()
USERS_FILE = pathlib.Path(__file__).parent / "users.json"
CUSTOM_RAG_BASE_PATH = pathlib.Path(__file__).parent / "custom_rag"
TEMP_UPLOAD_DIR_NAME = "_temp_uploads"

# Add a model for the signup request body
class SignupPayload(BaseModel):
    username: str
    password: str
    access_code: str

def get_current_user(credentials: HTTPBasicCredentials = Depends(security)):
    with open(USERS_FILE, "r") as f:
        users = json.load(f)
    correct_password = users.get(credentials.username)
    if not (correct_password and credentials.password == correct_password):
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username

# Define the access code
ACCESS_CODE = "dev.sahil.tomar"

@app.post("/signup")
async def signup_user(payload: SignupPayload):
    if payload.access_code != ACCESS_CODE:
        raise HTTPException(
            status_code=403,
            detail="Invalid access code."
        )

    with open(USERS_FILE, "r+") as f:
        try:
            users = json.load(f)
        except json.JSONDecodeError:
            users = {} # Initialize if file is empty or malformed

        if payload.username in users:
            raise HTTPException(
                status_code=400,
                detail="Username already exists."
            )

        users[payload.username] = payload.password
        f.seek(0)
        json.dump(users, f, indent=2)
        f.truncate()

    return JSONResponse(
        status_code=201,
        content={"message": f"User '{payload.username}' created successfully. You can now login."}
    )

def ensure_session(user_id: str, session_id: str):
    SESSION_SERVICE.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id
    )

@app.post("/upload")
async def upload_redirect_base(user: str = Depends(get_current_user)):
    return RedirectResponse(url=f"/upload/{user}", status_code=307)

@app.get("/upload/{user_name}")
async def check_or_initiate_upload_get(user_name: str, current_user: str = Depends(get_current_user)):
    if user_name != current_user:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot access another user's upload area")

    user_db_path = CUSTOM_RAG_BASE_PATH / user_name
    user_temp_upload_path = CUSTOM_RAG_BASE_PATH / f"{user_name}{TEMP_UPLOAD_DIR_NAME}"
    
    db_exists = user_db_path.exists() and any(f.name != f"{user_name}_instructions.txt" for f in user_db_path.iterdir() if f.is_file()) \
                 or (user_db_path.exists() and any(d.is_dir() for d in user_db_path.iterdir())) # Check for non-instruction files or any subdirectories

    temp_files_exist = user_temp_upload_path.exists() and any(user_temp_upload_path.iterdir())

    if db_exists:
        return JSONResponse({
            "db_exists": True,
            "message": f"Custom RAG for '{user_name}' exists.",
            "temp_files_exist": temp_files_exist
        })
    else:
        return JSONResponse({
            "db_exists": False,
            "message": f"No custom RAG found for '{user_name}'. Upload files or instructions to create one.",
            "temp_files_exist": temp_files_exist
        })

@app.post("/upload/{user_name}")
async def handle_file_upload(
    user_name: str,
    files: Optional[List[UploadFile]] = File(None),
    custom_instructions: Optional[str] = Form(None), # Field is present in form, might be ""
    current_user: str = Depends(get_current_user)
):
    if user_name != current_user:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot access another user's upload area")

    user_temp_upload_path = CUSTOM_RAG_BASE_PATH / f"{user_name}{TEMP_UPLOAD_DIR_NAME}"
    user_temp_upload_path.mkdir(parents=True, exist_ok=True)

    uploaded_file_names = []
    rejected_file_names = []
    allowed_extensions = {".pdf", ".docx"}

    if files:
        for file_upload in files:
            file_ext = pathlib.Path(file_upload.filename).suffix.lower()
            if file_ext in allowed_extensions:
                dest_path = user_temp_upload_path / file_upload.filename
                try:
                    with open(dest_path, "wb") as buffer:
                        shutil.copyfileobj(file_upload.file, buffer)
                    uploaded_file_names.append(file_upload.filename)
                except Exception as e:
                    rejected_file_names.append({"name": file_upload.filename, "reason": str(e)})
                finally:
                    file_upload.file.close()
            else:
                rejected_file_names.append({"name": file_upload.filename, "reason": "Invalid file type"})

    # Revised instruction message logic
    instructions_message = "No custom instructions were submitted by the client." # Should not happen if form field is always sent
    if custom_instructions is not None: # Check if the field was present in the form
        if custom_instructions.strip(): # Actually has content
            user_db_specific_path = CUSTOM_RAG_BASE_PATH / user_name
            user_db_specific_path.mkdir(parents=True, exist_ok=True)
            instructions_file_name = f"{user_name}_instructions.txt"
            try:
                with open(user_db_specific_path / instructions_file_name, "w") as f:
                    f.write(custom_instructions) # Save the original value
                instructions_message = f"Custom instructions saved as '{instructions_file_name}' in your RAG directory."
            except Exception as e:
                instructions_message = f"Failed to save custom instructions: {str(e)}"
        else: # Field was present but empty or all whitespace
            instructions_message = "Custom instructions field was submitted empty; no instructions were saved."

    if not uploaded_file_names and not (custom_instructions and custom_instructions.strip()):
        # Condition: No files were successfully staged AND no actual new instructions were provided.
        # If temp path is empty and no actual content was submitted, it's a "nothing to do" scenario.
        if user_temp_upload_path.exists() and not any(user_temp_upload_path.iterdir()):
             shutil.rmtree(user_temp_upload_path) # Clean up empty temp dir

        # If only empty instructions were sent and no files, this is the primary message.
        # If files were sent but all rejected, uploaded_file_names is empty, this path is also taken.
        # The JSON response below will carry more specific info.
        if not uploaded_file_names and custom_instructions is not None and not custom_instructions.strip():
             # This specific case: only empty instructions submitted.
             pass # instructions_message already set.
        elif not uploaded_file_names and custom_instructions is None:
             # No files, no instruction field submitted at all.
             pass # instructions_message already set.


    # Ensure a general message if nothing specific is set for the primary "message" field
    # The "instructions_status" will carry the detailed instruction outcome.
    response_message = f"Upload attempt processed for user '{user_name}'."
    if uploaded_file_names:
        response_message = f"Files received for user '{user_name}'. Review and confirm to process."
    elif custom_instructions is not None and custom_instructions.strip():
        response_message = f"Custom instructions received for user '{user_name}'."


    return JSONResponse({
        "message": response_message,
        "uploaded_files": uploaded_file_names,
        "rejected_files": rejected_file_names,
        "instructions_status": instructions_message, # This is the key for instruction feedback
        "confirmation_required": f"To process these files (if any), make a POST request to /process_docs/{user_name}"
    })

@app.post("/process_docs/{user_name}")
async def process_uploaded_documents(user_name: str, current_user: str = Depends(get_current_user)):
    if user_name != current_user:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot process another user's documents")

    user_temp_upload_path = CUSTOM_RAG_BASE_PATH / f"{user_name}{TEMP_UPLOAD_DIR_NAME}"
    user_db_target_path = CUSTOM_RAG_BASE_PATH / user_name

    if not user_temp_upload_path.exists() or not any(user_temp_upload_path.iterdir()):
        return JSONResponse({"error": "No files found to process. Please upload files first."}, status_code=400)

    try:
        load_rag_env()
        process_documents_and_build_db(
            docs_folder=str(user_temp_upload_path),
            db_path=str(user_db_target_path),
            collection_name=f"{user_name}_collection",
            embedding_model_name="models/embedding-001",
            chunk_size=1000,
            chunk_overlap=200
        )
        shutil.rmtree(user_temp_upload_path)

        return JSONResponse({
            "message": f"RAG database for '{user_name}' created/updated successfully.",
            "access_endpoints": {
                "run": f"/run/{user_name}",
                "run_sse": f"/run_sse/{user_name}"
            }
        })
    except Exception as e:
        return JSONResponse({"error": f"Failed to process documents: {str(e)}"}, status_code=500)

async def run_agent_with_rag_context(user_id: str, session_id: str, prompt: str, rag_name_override: Optional[str]):
    original_active_rag_name = agent_module.ACTIVE_RAG_NAME
    original_agent_instruction = agent_root_agent.instruction

    if rag_name_override:
        agent_module.ACTIVE_RAG_NAME = rag_name_override
        custom_instructions_path = CUSTOM_RAG_BASE_PATH / rag_name_override / f"{rag_name_override}_instructions.txt"
        if custom_instructions_path.exists():
            try:
                with open(custom_instructions_path, "r") as f:
                    agent_root_agent.instruction = f.read()
                print(f"Loaded custom instructions for RAG: {rag_name_override}")
            except Exception as e:
                print(f"Error loading custom instructions for {rag_name_override}, using default: {e}")
                agent_root_agent.instruction = DEFAULT_ROOT_AGENT_INSTRUCTION
        else:
            agent_root_agent.instruction = DEFAULT_ROOT_AGENT_INSTRUCTION
            print(f"No custom instructions file found for RAG: {rag_name_override}. Using default agent instructions.")
    else:
        agent_module.ACTIVE_RAG_NAME = "default_rag"
        default_instructions_path = CUSTOM_RAG_BASE_PATH / "default_rag" / "default_rag_instructions.txt"
        if default_instructions_path.exists():
            try:
                with open(default_instructions_path, "r") as f:
                    agent_root_agent.instruction = f.read()
                print("Loaded custom instructions for default_rag.")
            except Exception as e:
                print(f"Error loading custom instructions for default_rag, using default: {e}")
                agent_root_agent.instruction = DEFAULT_ROOT_AGENT_INSTRUCTION
        else:
            agent_root_agent.instruction = DEFAULT_ROOT_AGENT_INSTRUCTION
            print("Using default agent instructions for default_rag.")

    try:
        runner = Runner(
            agent=AGENT,
            app_name=APP_NAME,
            session_service=SESSION_SERVICE,
            memory_service=MEMORY_SERVICE
        )
        content = types.Content(role='user', parts=[types.Part(text=prompt)])
        
        final_response_text = "Agent did not produce a final response."
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            if event.is_final_response():
                if event.content and event.content.parts:
                    final_response_text = event.content.parts[0].text
                elif event.actions and event.actions.escalate:
                    final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
                break
        return final_response_text
    finally:
        agent_module.ACTIVE_RAG_NAME = original_active_rag_name
        agent_root_agent.instruction = original_agent_instruction

@app.post("/run")
@app.post("/run/{user_rag_name}")
async def run_endpoint(request: Request, user_rag_name: Optional[str] = None):
    data = await request.json()
    user_id = data.get("user_id", "user_1")
    session_id = data.get("session_id", "session_001")
    prompt = data.get("prompt")
    if not prompt:
        return JSONResponse({"error": "Missing prompt"}, status_code=400)
    ensure_session(user_id, session_id)
    
    response_text = await run_agent_with_rag_context(user_id, session_id, prompt, user_rag_name)
    return JSONResponse({"response": response_text})

@app.post("/run_sse")
@app.post("/run_sse/{user_rag_name}")
async def run_sse_endpoint(request: Request, user_rag_name: Optional[str] = None):
    data = await request.json()
    user_id = data.get("user_id", "user_1")
    session_id = data.get("session_id", "session_001")
    prompt = data.get("prompt")
    if not prompt:
        return JSONResponse({"error": "Missing prompt"}, status_code=400)
    ensure_session(user_id, session_id)

    async def event_generator():
        original_active_rag_name = agent_module.ACTIVE_RAG_NAME
        original_agent_instruction = agent_root_agent.instruction

        if user_rag_name:
            agent_module.ACTIVE_RAG_NAME = user_rag_name
            custom_instructions_path = CUSTOM_RAG_BASE_PATH / user_rag_name / f"{user_rag_name}_instructions.txt"
            if custom_instructions_path.exists():
                try:
                    with open(custom_instructions_path, "r") as f:
                        agent_root_agent.instruction = f.read()
                    print(f"Loaded custom instructions for RAG: {user_rag_name} in SSE")
                except Exception as e:
                    print(f"Error loading custom instructions for {user_rag_name} in SSE, using default: {e}")
                    agent_root_agent.instruction = DEFAULT_ROOT_AGENT_INSTRUCTION
            else:
                agent_root_agent.instruction = DEFAULT_ROOT_AGENT_INSTRUCTION
                print(f"No custom instructions file found for RAG: {user_rag_name} in SSE. Using default agent instructions.")
        else:
            agent_module.ACTIVE_RAG_NAME = "default_rag"
            default_instructions_path = CUSTOM_RAG_BASE_PATH / "default_rag" / "default_rag_instructions.txt"
            if default_instructions_path.exists():
                try:
                    with open(default_instructions_path, "r") as f:
                        agent_root_agent.instruction = f.read()
                    print("Loaded custom instructions for default_rag in SSE.")
                except Exception as e:
                    print(f"Error loading custom instructions for default_rag in SSE, using default: {e}")
                    agent_root_agent.instruction = DEFAULT_ROOT_AGENT_INSTRUCTION
            else:
                agent_root_agent.instruction = DEFAULT_ROOT_AGENT_INSTRUCTION
                print("Using default agent instructions for default_rag in SSE.")
        
        try:
            runner = Runner(
                agent=AGENT,
                app_name=APP_NAME,
                session_service=SESSION_SERVICE,
                memory_service=MEMORY_SERVICE
            )
            content = types.Content(role='user', parts=[types.Part(text=prompt)])
            async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
                yield f"data: {event.model_dump_json() if hasattr(event, 'model_dump_json') else str(event)}\n\n"
        finally:
            agent_module.ACTIVE_RAG_NAME = original_active_rag_name
            agent_root_agent.instruction = original_agent_instruction

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Mount static files - this should be after all API routes and before the __main__ block
static_files_path = pathlib.Path(__file__).parent / "UI-UX"
app.mount("/", StaticFiles(directory=static_files_path, html=True), name="ui")

if __name__ == "__main__":
    import uvicorn
    import asyncio # Ensure asyncio is imported if not already

    CUSTOM_RAG_BASE_PATH.mkdir(parents=True, exist_ok=True)
    
    # Define the desired max body size (100MB in this example)
    max_body_size_bytes = 100 * 1024 * 1024 # 104,857,600 bytes

    config = uvicorn.Config(
        "main:app", 
        host="0.0.0.0", 
        port=int(os.environ.get("PORT", 8000)), 
        log_level="info", # Added for better logging
        limit_max_body_size=max_body_size_bytes
    )
    server = uvicorn.Server(config)
    server.run() # This will internally use asyncio.run if needed
