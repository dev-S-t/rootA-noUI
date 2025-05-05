import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from multi_tool_agent.agent import AGENT, SESSION_SERVICE, MEMORY_SERVICE, APP_NAME
from google.adk.runners import Runner
from google.genai import types

app = FastAPI()

# Helper to get or create a session for a user/session_id
def ensure_session(user_id: str, session_id: str):
    SESSION_SERVICE.create_session(
        app_name=APP_NAME,
        user_id=user_id,
        session_id=session_id
    )

# /run endpoint: Accepts JSON with user_id, session_id, and prompt
@app.post("/run")
async def run_endpoint(request: Request):
    data = await request.json()
    user_id = data.get("user_id", "user_1")
    session_id = data.get("session_id", "session_001")
    prompt = data.get("prompt")
    if not prompt:
        return JSONResponse({"error": "Missing prompt"}, status_code=400)
    ensure_session(user_id, session_id)
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
    return JSONResponse({"response": final_response_text})

# /run_sse endpoint: Accepts JSON and streams events as SSE
@app.post("/run_sse")
async def run_sse_endpoint(request: Request):
    data = await request.json()
    user_id = data.get("user_id", "user_1")
    session_id = data.get("session_id", "session_001")
    prompt = data.get("prompt")
    if not prompt:
        return JSONResponse({"error": "Missing prompt"}, status_code=400)
    ensure_session(user_id, session_id)
    runner = Runner(
        agent=AGENT,
        app_name=APP_NAME,
        session_service=SESSION_SERVICE,
        memory_service=MEMORY_SERVICE
    )
    content = types.Content(role='user', parts=[types.Part(text=prompt)])

    async def event_generator():
        async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
            yield f"data: {event.model_dump_json() if hasattr(event, 'model_dump_json') else str(event)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
