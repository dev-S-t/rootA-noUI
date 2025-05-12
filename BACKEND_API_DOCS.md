# Backend API Documentation

This document provides a comprehensive overview of the backend API for the Multi-Tool Agent application. It covers authentication, available endpoints, request/response formats, error codes, and example usage flows.

**Version:** 1.0.0
**Base URL:** `/` (The application is served from the root)

## 1. Authentication

The API uses **HTTP Basic Authentication**. Clients must include an `Authorization` header with their requests, containing the word `Basic` followed by a space and a base64-encoded string of `username:password`.

**Example:** `Authorization: Basic dXNlcjpwYXNzd29yZA==`

User credentials are stored in `users.json`.

## 2. Core Concepts

*   **RAG (Retrieval Augmented Generation):** The system uses RAG to answer user queries. Users can have a "default RAG" or a "custom RAG".
*   **Custom RAG:** Users can upload documents (PDF, DOCX) and provide custom instructions to create their own RAG. This RAG is specific to the user.
*   **Sessions:** Interactions with the agent are session-based. A `user_id` and `session_id` are used to maintain context.
*   **Agents:** The backend utilizes a `root_agent` which can delegate tasks to sub-agents like `search_bot`.

## 3. API Endpoints

### 3.1. User Authentication and RAG Management

#### 3.1.1. `GET /upload/{user_name}`

*   **Description:** Checks the status of a user's custom RAG or initiates the upload process view. This endpoint is typically called after a successful login to determine if a custom RAG exists or if there are temporary files pending processing.
*   **Method:** `GET`
*   **Path Parameter:**
    *   `user_name` (string, required): The username.
*   **Authentication:** Required.
*   **Responses:**
    *   `200 OK`:
        *   **Content-Type:** `application/json`
        *   **Body:**
            ```json
            {
              "db_exists": true, // boolean: true if a custom RAG exists for the user
              "message": "Custom RAG for 'username' exists.", // string: status message
              "temp_files_exist": false // boolean: true if there are unprocessed files in the user's temp upload directory
            }
            ```
            ```json
            {
              "db_exists": false,
              "message": "No custom RAG found for 'username'. Upload files or instructions to create one.",
              "temp_files_exist": true
            }
            ```
    *   `401 Unauthorized`: If authentication fails.
        ```json
        {
          "detail": "Incorrect username or password"
        }
        ```
    *   `403 Forbidden`: If `user_name` in the path does not match the authenticated user.
        ```json
        {
          "detail": "Forbidden: Cannot access another user's upload area"
        }
        ```
*   **Error Codes Specific to this Endpoint:**
    *   `401 Unauthorized`: Invalid credentials.
    *   `403 Forbidden`: Attempting to access another user's data.

#### 3.1.2. `POST /upload`

*   **Description:** This is a redirect endpoint. It's intended to redirect to the user-specific upload GET endpoint (`/upload/{user_name}`) after successful authentication. Primarily used by HTML forms or clients that follow redirects.
*   **Method:** `POST`
*   **Authentication:** Required.
*   **Responses:**
    *   `307 Temporary Redirect`: Redirects to `/upload/{user_name}`.
    *   `401 Unauthorized`: If authentication fails.

#### 3.1.3. `POST /upload/{user_name}`

*   **Description:** Handles file uploads and custom instruction submissions for a user's custom RAG. Uploaded files are temporarily staged.
*   **Method:** `POST`
*   **Path Parameter:**
    *   `user_name` (string, required): The username.
*   **Authentication:** Required.
*   **Request Body:** `multipart/form-data`
    *   `files` (List[UploadFile], optional): A list of files to upload (PDF, DOCX).
    *   `custom_instructions` (string, optional): Text-based custom instructions for the RAG.
*   **Responses:**
    *   `200 OK`:
        *   **Content-Type:** `application/json`
        *   **Body Example (Files uploaded, instructions provided):**
            ```json
            {
              "message": "Files received for user 'username'. Review and confirm to process.",
              "uploaded_files": ["document1.pdf", "report.docx"],
              "rejected_files": [{"name": "image.png", "reason": "Invalid file type"}],
              "instructions_status": "Custom instructions saved as 'username_instructions.txt' in your RAG directory.",
              "confirmation_required": "To process these files (if any), make a POST request to /process_docs/username"
            }
            ```
        *   **Body Example (Only instructions provided):**
            ```json
            {
                "message": "Custom instructions received for user 'username'.",
                "uploaded_files": [],
                "rejected_files": [],
                "instructions_status": "Custom instructions saved as 'username_instructions.txt' in your RAG directory.",
                "confirmation_required": "To process these files (if any), make a POST request to /process_docs/username"
            }
            ```
        *   **Body Example (No files, empty instructions):**
            ```json
            {
                "message": "Upload attempt processed for user 'username'.",
                "uploaded_files": [],
                "rejected_files": [],
                "instructions_status": "Custom instructions field was submitted empty; no instructions were saved.",
                "confirmation_required": "To process these files (if any), make a POST request to /process_docs/username"
            }
            ```
    *   `401 Unauthorized`: If authentication fails.
    *   `403 Forbidden`: If `user_name` in the path does not match the authenticated user.
*   **Error Codes Specific to this Endpoint:**
    *   `401 Unauthorized`: Invalid credentials.
    *   `403 Forbidden`: Attempting to upload to another user's area.
    *   Rejection of files due to type or other errors will be listed in the `rejected_files` array in the `200 OK` response.

#### 3.1.4. `POST /process_docs/{user_name}`

*   **Description:** Processes the temporarily staged files (uploaded via `POST /upload/{user_name}`) to build or update the user's custom RAG database.
*   **Method:** `POST`
*   **Path Parameter:**
    *   `user_name` (string, required): The username.
*   **Authentication:** Required.
*   **Responses:**
    *   `200 OK`:
        *   **Content-Type:** `application/json`
        *   **Body:**
            ```json
            {
              "message": "RAG database for 'username' created/updated successfully.",
              "access_endpoints": {
                "run": "/run/username",
                "run_sse": "/run_sse/username"
              }
            }
            ```
    *   `400 Bad Request`: If no files are found in the temporary upload directory for the user.
        ```json
        {
          "error": "No files found to process. Please upload files first."
        }
        ```
    *   `401 Unauthorized`: If authentication fails.
    *   `403 Forbidden`: If `user_name` in the path does not match the authenticated user.
    *   `500 Internal Server Error`: If an error occurs during document processing or RAG building.
        ```json
        {
          "error": "Failed to process documents: <specific error message>"
        }
        ```
*   **Error Codes Specific to this Endpoint:**
    *   `400 Bad Request`: No files to process.
    *   `401 Unauthorized`: Invalid credentials.
    *   `403 Forbidden`: Attempting to process another user's documents.
    *   `500 Internal Server Error`: Backend error during RAG creation.

#### 3.1.5. `POST /signup`

*   **Description:** Allows a new user to sign up for an account by providing a username, password, and a specific access code.
*   **Method:** `POST`
*   **Authentication:** Not required (as this is for creating new users).
*   **Request Body:** `application/json`
    ```json
    {
      "username": "newuser",
      "password": "newpassword123",
      "access_code": "dev.sahil.tomar"
    }
    ```
*   **Responses:**
    *   `201 Created`:
        *   **Content-Type:** `application/json`
        *   **Body:**
            ```json
            {
              "message": "User 'newuser' created successfully. You can now login."
            }
            ```
    *   `400 Bad Request`: If the username already exists.
        ```json
        {
          "detail": "Username already exists."
        }
        ```
    *   `403 Forbidden`: If the provided `access_code` is invalid.
        ```json
        {
          "detail": "Invalid access code."
        }
        ```
    *   `422 Unprocessable Entity`: If the request body is malformed (e.g., missing fields).
*   **Error Codes Specific to this Endpoint:**
    *   `400 Bad Request`: Username already exists.
    *   `403 Forbidden`: Invalid access code.
    *   `422 Unprocessable Entity`: Invalid request payload.

### 3.2. Agent Interaction

#### 3.2.1. `POST /run` and `POST /run/{user_rag_name}`

*   **Description:** Runs the agent with a given prompt. If `user_rag_name` is provided in the path, the agent uses that specific user's custom RAG. Otherwise, it uses the "default_rag". This endpoint returns a single JSON response after the agent has finished processing.
*   **Method:** `POST`
*   **Path Parameter:**
    *   `user_rag_name` (string, optional): The name of the user-specific RAG to use. If omitted, "default_rag" is used.
*   **Authentication:** Not explicitly enforced at this endpoint by `get_current_user` but relies on the overall application security context if any. The `user_id` in the request body determines user context for the agent.
*   **Request Body:** `application/json`
    ```json
    {
      "user_id": "user_1", // string, required: Identifier for the user
      "session_id": "session_001", // string, required: Identifier for the session
      "prompt": "What is the weather in New York?" // string, required: The user's query
    }
    ```
*   **Responses:**
    *   `200 OK`:
        *   **Content-Type:** `application/json`
        *   **Body:**
            ```json
            {
              "response": "The agent's final textual response."
            }
            ```
            *If the agent escalates:*
            ```json
            {
              "response": "Agent escalated: <error message or 'No specific message.'>"
            }
            ```
    *   `400 Bad Request`: If the `prompt` is missing in the request body.
        ```json
        {
          "error": "Missing prompt"
        }
        ```
*   **Error Codes Specific to this Endpoint:**
    *   `400 Bad Request`: Missing `prompt`.
    *   Agent-specific errors might be contained within the `response` text if an escalation occurs.

#### 3.2.2. `POST /run_sse` and `POST /run_sse/{user_rag_name}`

*   **Description:** Runs the agent with a given prompt using Server-Sent Events (SSE) for streaming responses. If `user_rag_name` is provided, it uses that specific custom RAG. Otherwise, it uses "default_rag".
*   **Method:** `POST`
*   **Path Parameter:**
    *   `user_rag_name` (string, optional): The name of the user-specific RAG to use.
*   **Authentication:** Not explicitly enforced at this endpoint.
*   **Request Body:** `application/json` (Same as `/run` endpoint)
    ```json
    {
      "user_id": "user_1",
      "session_id": "session_001",
      "prompt": "Tell me about Google ADK."
    }
    ```
*   **Responses:**
    *   `200 OK`:
        *   **Content-Type:** `text/event-stream`
        *   **Body:** A stream of events. Each event is a JSON string representing an agent event (e.g., tool call, intermediate response, final response).
            **Example Event:**
            `data: {"event_type": "final_response", "content": {"role": "model", "parts": [{"text": "Google Agent Development Kit (ADK) is a framework..."}]}, ...}`
            `

`
    *   `400 Bad Request`: If the `prompt` is missing. (This response will be a standard JSON, not SSE).
*   **Error Codes Specific to this Endpoint:**
    *   `400 Bad Request`: Missing `prompt`.
    *   Connection errors or stream interruptions can occur.

### 3.3. Static Files

*   **`GET /` and other paths under `/` (e.g., `/app.js`, `/style.css`)**
    *   **Description:** Serves static files for the UI (HTML, CSS, JavaScript).
    *   **Method:** `GET`
    *   **Authentication:** Not required for static assets.
    *   **Responses:**
        *   `200 OK`: With the content of the requested static file.
        *   `404 Not Found`: If the static file does not exist.

## 4. Agent Capabilities (via `agent.py`)

The backend agent (`root_agent`) has the following tools and capabilities:

*   **`get_current_time(city: str)`:** Get the current time for a specified city.
*   **`get_weather(city: str)`:** Get the weather for a specified city.
*   **`rag_answer(question: str)`:** Answer questions using the active RAG (either default or user-specific).
    *   If no relevant documents are found, it returns a "no_matches_found" status.
    *   If the RAG DB is unavailable, it uses a fallback knowledge base.
*   **`load_memory()`:** Loads previous messages from the conversation history.
*   **Sub-agent `search_bot`:**
    *   **`web_search(query: str, engine: str = "google")`:** Performs a web search.
    *   **`link_fetcher(url: str)`:** Fetches content from a URL.
    *   **`summarizer(query: str, content: str)`:** Summarizes fetched content.

The agent's behavior is guided by instructions that prioritize RAG search, allow for web searches if RAG is insufficient, and handle transfers to/from the `search_bot`.

## 5. Example Flows

### 5.1. Flow 1: User Logs In, Uploads Documents, Processes them, and Chats with Custom RAG

1.  **Client (Frontend) logs in user "testuser" with password "testpass".**
    *   Frontend might first call `GET /upload/testuser` with Basic Auth.
    *   Server responds `200 OK` with `{"db_exists": false, "message": "No custom RAG...", "temp_files_exist": false}`.

2.  **Client uploads `mydoc.pdf` and provides "Use this document for summaries" as custom_instructions for "testuser".**
    *   `POST /upload/testuser`
    *   **Headers:** `Authorization: Basic dGVzdHVzZXI6dGVzdHBhc3M=`
    *   **Body (multipart/form-data):**
        *   `files`: `mydoc.pdf` (the file object)
        *   `custom_instructions`: "Use this document for summaries" (the string)
    *   Server responds `200 OK`:
        ```json
        {
          "message": "Files received for user 'testuser'. Review and confirm to process.",
          "uploaded_files": ["mydoc.pdf"],
          "rejected_files": [],
          "instructions_status": "Custom instructions saved as 'testuser_instructions.txt' in your RAG directory.",
          "confirmation_required": "To process these files (if any), make a POST request to /process_docs/testuser"
        }
        ```

3.  **Client triggers document processing for "testuser".**
    *   `POST /process_docs/testuser`
    *   **Headers:** `Authorization: Basic dGVzdHVzZXI6dGVzdHBhc3M=`
    *   Server responds `200 OK`:
        ```json
        {
          "message": "RAG database for 'testuser' created/updated successfully.",
          "access_endpoints": {
            "run": "/run/testuser",
            "run_sse": "/run_sse/testuser"
          }
        }
        ```

4.  **Client sends a prompt to the custom RAG for "testuser".**
    *   `POST /run/testuser` (or `/run_sse/testuser` for streaming)
    *   **Request Body (application/json):**
        ```json
        {
          "user_id": "testuser",
          "session_id": "session_abc123",
          "prompt": "Summarize mydoc.pdf based on our instructions"
        }
        ```
    *   Server responds `200 OK` (for `/run`):
        ```json
        {
          "response": "Based on the information I retrieved from my knowledge base: From mydoc.pdf: <content summary according to instructions>..."
        }
        ```
        (For `/run_sse`, it would be a stream of events).

### 5.2. Flow 2: User Chats with Default RAG

1.  **Client sends a prompt to the default RAG.** (Assuming user is "anyuser", session "session_def456")
    *   `POST /run` (or `/run_sse`)
    *   **Request Body (application/json):**
        ```json
        {
          "user_id": "anyuser",
          "session_id": "session_def456",
          "prompt": "What is Google ADK?"
        }
        ```
    *   Server responds `200 OK` (for `/run`):
        ```json
        {
          "response": "Based on the information I retrieved from my knowledge base: Google Agent Development Kit (ADK) is a framework..."
        }
        ```

### 5.3. Flow 3: Agent Uses Web Search via `search_bot`

1.  **Client sends a prompt that requires web search.** (User "webuser", session "session_web789", using default RAG initially)
    *   `POST /run`
    *   **Request Body (application/json):**
        ```json
        {
          "user_id": "webuser",
          "session_id": "session_web789",
          "prompt": "What's the latest news about Gemini models?"
        }
        ```
2.  **Agent Interaction (internal, simplified):**
    *   `root_agent` receives prompt.
    *   `root_agent` attempts `rag_answer("What's the latest news about Gemini models?")`. RAG returns no specific news.
    *   `root_agent` decides to use web search. It transfers control to `search_bot`.
    *   `search_bot` calls `web_search("latest news Gemini models")`. Gets search results.
    *   `search_bot` calls `link_fetcher(url_from_results)`. Gets content.
    *   `search_bot` calls `summarizer("latest news Gemini models", fetched_content)`. Gets summary.
    *   `search_bot` transfers control back to `root_agent` with the summary.
3.  **Server responds `200 OK` (for `/run`):**
    *   ```json
      {
        "response": "I found some information online: <summary of latest news about Gemini models>"
      }
      ```
