
# This MUST be at the very top of this __init__.py file.
import sys
SQLITE_PATCHED_IN_AGENT_PACKAGE = False
try:
    import pysqlite3
    sys.modules['sqlite3'] = pysqlite3
    SQLITE_PATCHED_IN_AGENT_PACKAGE = True
    # Optional: You might want a more specific logger if you have one for this package
    print(f"MULTI_TOOL_AGENT: Successfully patched sqlite3 with pysqlite3. Using SQLite version: {pysqlite3.sqlite_version}")
except ImportError:
    print("WARNING (MULTI_TOOL_AGENT): pysqlite3 module not found. Ensure 'pysqlite3-binary' is installed. Falling back to system sqlite3.")
except Exception as e:
    print(f"WARNING (MULTI_TOOL_AGENT): An unexpected error occurred while patching sqlite3: {e}. Falling back to system sqlite3.")
# --- END SQLITE PATCH ---


from . import agent