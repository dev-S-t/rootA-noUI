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

from multi_tool_agent.agent import AGENT, SESSION_SERVICE, MEMORY_SERVICE, APP_NAME, get_vector_db_path
import multi_tool_agent.agent as agent_module

from google.adk.runners import Runner
from google.genai import types

from rag_builder import process_documents_and_build_db, load_environment as load_rag_env

app = FastAPI()

security = HTTPBasic()
USERS_FILE = pathlib.Path(__file__).parent / "users.json"
CUSTOM_RAG_BASE_PATH = pathlib.Path(__file__).parent / "custom_rag"
TEMP_UPLOAD_DIR_NAME = "_temp_uploads"

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
    if user_db_path.exists() and any(user_db_path.iterdir()):
        return JSONResponse({"status": "db_exists", "message": f"Database for '{user_name}' already exists. Uploading new files will attempt to update it."})
    else:
        return JSONResponse({"status": "no_existing_db", "message": f"No existing database for '{user_name}'. Uploading files will create a new one."})

@app.post("/upload/{user_name}")
async def handle_file_upload(
    user_name: str,
    files: List[UploadFile] = File(...),
    current_user: str = Depends(get_current_user)
):
    if user_name != current_user:
        raise HTTPException(status_code=403, detail="Forbidden: Cannot access another user's upload area")

    user_temp_upload_path = CUSTOM_RAG_BASE_PATH / f"{user_name}{TEMP_UPLOAD_DIR_NAME}"
    user_temp_upload_path.mkdir(parents=True, exist_ok=True)

    uploaded_file_names = []
    rejected_file_names = []
    allowed_extensions = {".pdf", ".docx"}

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

    if not uploaded_file_names:
        if user_temp_upload_path.exists():
            shutil.rmtree(user_temp_upload_path)
        return JSONResponse({
            "message": "No valid files (PDF or DOCX) were uploaded.",
            "uploaded_files": [],
            "rejected_files": rejected_file_names
        }, status_code=400)

    return JSONResponse({
        "message": f"Files received for user '{user_name}'. Review and confirm to process.",
        "uploaded_files": uploaded_file_names,
        "rejected_files": rejected_file_names,
        "confirmation_required": f"To process these files, make a POST request to /process_docs/{user_name}"
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

    if rag_name_override:
        agent_module.ACTIVE_RAG_NAME = rag_name_override
    else:
        agent_module.ACTIVE_RAG_NAME = "default_rag"

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
        if user_rag_name:
            agent_module.ACTIVE_RAG_NAME = user_rag_name
        else:
            agent_module.ACTIVE_RAG_NAME = "default_rag"
        
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

    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Mount static files - this should be after all API routes and before the __main__ block
static_files_path = pathlib.Path(__file__).parent / "UI-UX"
app.mount("/", StaticFiles(directory=static_files_path, html=True), name="ui")

if __name__ == "__main__":
    import uvicorn
    CUSTOM_RAG_BASE_PATH.mkdir(parents=True, exist_ok=True)
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
