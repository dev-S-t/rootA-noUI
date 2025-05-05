from google.adk.sessions import InMemorySessionService
from google.adk.memory import InMemoryMemoryService

# --- Session and Memory Service Setup for Import ---
# These can be imported and used in other modules
APP_NAME = "multi_tool_agent_app"
USER_ID = "user_1"
SESSION_ID = "session_001"

session_service = InMemorySessionService()
memory_service = InMemoryMemoryService()
