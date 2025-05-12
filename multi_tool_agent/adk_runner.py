import os
import asyncio
from google.adk.agents import Agent
from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService
from google.adk.runners import Runner
from google.genai import types

# --- Session and Memory Setup ---
APP_NAME = "multi_tool_agent_app"
USER_ID = "user_1"
SESSION_ID = "session_001"

# Initialize session and memory services
session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()

# --- Agent Import ---
# Import your root_agent from agent.py
from multi_tool_agent.agent import root_agent

# --- Runner Setup ---
runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
    memory_service=memory_service
)

# --- Async Conversation Function ---
async def call_agent_async(query: str, runner, user_id, session_id):
    """Sends a query to the agent and prints the final response."""
    print(f"\n>>> User Query: {query}")
    content = types.Content(role='user', parts=[types.Part(text=query)])
    final_response_text = "Agent did not produce a final response."
    async for event in runner.run_async(user_id=user_id, session_id=session_id, new_message=content):
        if event.is_final_response():
            if event.content and event.content.parts:
                final_response_text = event.content.parts[0].text
            elif event.actions and event.actions.escalate:
                final_response_text = f"Agent escalated: {event.error_message or 'No specific message.'}"
            break
    print(f"<<< Agent Response: {final_response_text}")

    # Add session to memory after the interaction
    completed_session = session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
    if completed_session:
        memory_service.add_session_to_memory(completed_session)
        print(f"--- Session {session_id} added to memory ---")
    else:
        print(f"--- Could not retrieve session {session_id} to add to memory ---")

    return final_response_text

# --- Example Usage ---
if __name__ == "__main__":
    async def main():
        # Ensure session exists
        session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=SESSION_ID
        )
        # Example conversation
        await call_agent_async("Tell me about SHL assessments.", runner, USER_ID, SESSION_ID)
        await call_agent_async("What is the weather in New York?", runner, USER_ID, SESSION_ID)
        await call_agent_async("Search for Techiemaya startup.", runner, USER_ID, SESSION_ID)
    asyncio.run(main())
