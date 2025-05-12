# Frontend Integration Guide for Multi-Tool Agent Backend

This guide is for frontend designers and developers to understand how to interact with and integrate the Multi-Tool Agent backend API.

## 1. Overview

The backend provides a conversational AI agent with capabilities for Retrieval Augmented Generation (RAG), web search, and other tools. Users can interact with a default knowledge base or create their own custom knowledge base by uploading documents.

**Key Frontend Responsibilities:**

*   Handle user authentication (Login).
*   Provide an interface for uploading files and custom instructions to create/update a user-specific RAG.
*   Manage the process of building the custom RAG.
*   Facilitate chat interactions with the agent, targeting either the default RAG or the user's custom RAG.
*   Display responses, including streamed responses (SSE).
*   Manage user sessions.

## 2. Authentication and Signup

*   **Authentication Method:** HTTP Basic Authentication for most protected routes.
*   **Signup Flow:**
    1.  The UI provides a "Sign up" link on the login page, which reveals the signup form (`signup-section`).
    2.  The signup form collects a desired username, password, and a specific access code (`dev.sahil.tomar`).
    3.  On submission, the frontend makes a `POST` request to `/signup` with the `application/json` payload:
        ```json
        {
          "username": "newuser",
          "password": "newpassword123",
          "access_code": "dev.sahil.tomar"
        }
        ```
    4.  **Response Handling for Signup:**
        *   `201 Created`: User successfully created. Display a success message (e.g., "User 'newuser' created successfully. You can now login."). The `app.js` then typically hides the signup form and shows the login form again.
        *   `400 Bad Request` (e.g., `{"detail": "Username already exists."}`): Display an appropriate error (e.g., "Username already taken. Please choose another.").
        *   `403 Forbidden` (e.g., `{"detail": "Invalid access code."}`): Display an error (e.g., "Invalid access code provided.").
        *   Other errors (network, server-side): Display a generic error message.
*   **Login Flow:**
    1.  Collect username and password from the user.
    2.  Make a `GET` request to `/upload/{username}` (e.g., `/upload/testuser`) with the Basic Auth header.
    3.  If the response status is `200 OK`, login is successful. Store the credentials (or a token if implementing a more advanced session mechanism on the frontend, though the backend is stateless per request beyond ADK sessions).
    4.  If `401 Unauthorized`, display an "Invalid credentials" error.
    5.  The response from `GET /upload/{username}` will indicate if a custom RAG exists (`db_exists`) and if there are pending temporary files (`temp_files_exist`). Use this to update the UI.

## 3. Managing Custom RAG

### 3.1. Checking RAG Status

*   After login, or when navigating to the RAG management section for a user, call:
    *   `GET /upload/{user_name}` (Authenticated)
*   The response will inform the UI:
    *   `db_exists: true`: A custom RAG is already built. The user might want to chat with it or upload more files to update it.
    *   `db_exists: false`: No custom RAG. The user needs to upload files/instructions.
    *   `temp_files_exist: true`: Files have been uploaded but not yet processed. A "Process Files" button should be enabled.

### 3.2. Uploading Files and Instructions

*   Provide a form where users can:
    *   Select multiple files (PDF, DOCX).
    *   Enter custom text instructions for their RAG.
*   On submission, make a `POST` request to `/upload/{user_name}` (Authenticated).
    *   **Content-Type:** `multipart/form-data`.
    *   Include selected files under the `files` field and custom instructions text under the `custom_instructions` field.
*   **Response Handling:**
    *   The `200 OK` JSON response will contain:
        *   `message`: A general status.
        *   `uploaded_files`: List of successfully staged file names.
        *   `rejected_files`: List of files that were not accepted (e.g., wrong type) and reasons.
        *   `instructions_status`: Feedback on saving the custom instructions.
        *   `confirmation_required`: A message indicating the next step is to process these files.
    *   Display this information to the user. If `uploaded_files` is not empty, enable a "Process Files" button.

### 3.3. Processing Uploaded Documents

*   When the user confirms they want to build/update their RAG with the uploaded files:
    *   Make a `POST` request to `/process_docs/{user_name}` (Authenticated).
*   **Response Handling:**
    *   `200 OK`:
        *   `message`: Success message (e.g., "RAG database for 'username' created/updated successfully.").
        *   `access_endpoints`: Provides the specific paths to use for chatting with this newly built/updated custom RAG (e.g., `/run/username`).
        *   Update the UI to indicate the RAG is ready. Disable the "Process Files" button until new files are uploaded.
    *   `400 Bad Request`: If no files were pending. Inform the user.
    *   `500 Internal Server Error`: If processing failed. Display an error message.

## 4. Chat Interface

### 4.1. Starting a Chat Session

*   **Session ID:** Generate a unique session ID on the client-side when a new chat conversation starts (e.g., a UUID). This `session_id` should be reused for subsequent messages within the same conversation flow. The existing `app.js` uses `currentSessionId`.
*   **User ID:** This is the username of the logged-in user (`currentUser` in `app.js`).
*   **Target RAG:**
    *   **Default RAG:** Use the `/run` or `/run_sse` endpoint.
    *   **Custom RAG:** Use the `/run/{user_rag_name}` or `/run_sse/{user_rag_name}` endpoint, where `{user_rag_name}` is the current user's username. The `chatTargetIsCustom` variable in `app.js` can determine this.

### 4.2. Sending a Prompt and Receiving Responses

*   **Request:**
    *   `POST /run` (for single response) or `POST /run_sse` (for streaming).
    *   Use the appropriate path if targeting a custom RAG (e.g., `/run/myusername`).
    *   **Content-Type:** `application/json`.
    *   **Body:**
        ```json
        {
          "user_id": "currentUser", // e.g., "testuser"
          "session_id": "currentSessionId", // e.g., "chat_session_12345"
          "prompt": "User's chat message"
        }
        ```

*   **Response Handling (`/run` - Single JSON):**
    *   The `200 OK` response will be a JSON object: `{"response": "Agent's full text answer"}`.
    *   Display the `response` text in the chat interface.

*   **Response Handling (`/run_sse` - Server-Sent Events):**
    1.  Initiate the request using `fetch`. The `app.js` example uses `fetch` and then processes the stream.
        ```javascript
        // Simplified from app.js logic for clarity
        const ragNamePath = chatTargetIsCustom ? `/${currentUser}` : '';
        const response = await fetch(`/run_sse${ragNamePath}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': 'Basic ' + btoa(currentUser + ":" + currentPassword) // If SSE endpoint needs auth
            },
            body: JSON.stringify({
                user_id: currentUser,
                session_id: currentSessionId,
                prompt: promptText
            })
        });

        if (!response.ok) {
            // Handle HTTP error before trying to read stream
            const errorData = await response.json().catch(() => ({ detail: response.statusText }));
            // Display error
            return;
        }

        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        let buffer = '';

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buffer += decoder.decode(value, { stream: true });

            let eolIndex;
            while ((eolIndex = buffer.indexOf('\n\n')) >= 0) {
                const message = buffer.slice(0, eolIndex).trim();
                buffer = buffer.slice(eolIndex + 2);

                if (message.startsWith('data: ')) {
                    const jsonData = message.substring(5);
                    try {
                        const eventData = JSON.parse(jsonData);
                        // Process eventData:
                        // Example: appendChatMessage('Agent', eventData.content?.parts?.[0]?.text, !eventData.is_final_response);
                        if (eventData.is_final_response && eventData.content && eventData.content.parts) {
                             appendChatMessage('Agent', eventData.content.parts[0].text);
                        } else if (eventData.content && eventData.content.parts) {
                             appendChatMessage('Agent', eventData.content.parts[0].text, true); // true for streaming/intermediate
                        }
                        // Handle other event types if needed (tool calls, etc.)
                    } catch (e) {
                        console.error("Error parsing SSE event data:", e, jsonData);
                    }
                }
            }
        }
        // Final part of buffer if any (though SSE usually ends with 

)
        if (buffer.startsWith('data: ')) { /* ... process remaining ... */ }

        ```
    2.  **Key Event Fields to Look For (based on ADK structure in JSON):**
        *   `is_final_response: true`: Indicates the complete answer from the agent for that turn.
        *   `content.parts[0].text`: The actual text content of the message.
        *   The frontend might receive multiple events before the final one, allowing for a "typing" or "streaming" effect. Update the agent's message bubble incrementally.
        *   Tool usage events (e.g., `actions.tool_code`, `actions.tool_response`) can be observed if you want to display "Agent is using [tool name]..." or similar feedback.

### 4.3. UI Considerations for Chat

*   **Message Display:** Clearly distinguish between user messages and agent messages. The `app.js` `appendChatMessage` function handles this.
*   **Loading/Thinking Indicator:** Show a visual indicator while waiting for the agent's response. For SSE, this might be active until the `is_final_response` event is received. `chatStatus` in `app.js` can be used.
*   **Error Handling:** Display errors from the API (e.g., `400 Bad Request` if prompt is missing) or network errors.
*   **Switching RAG Context:** If the user switches between default RAG and custom RAG (using `chatDefaultRagButton`, `chatCustomRagButton`), ensure the correct endpoint is called for subsequent messages. It's good practice to clear the chat history or visually separate conversations from different RAG contexts, as `app.js` does by calling `clearChat()`.

## 5. User Interface Structure (`UI-UX/app.js` based)

The existing `UI-UX/app.js` provides a robust foundation with sections for:

*   **Login (`login-section`):** Handles authentication.
    *   Includes a link to switch to the Signup section.
*   **Signup (`signup-section`):** Handles new user registration.
    *   Fields for username, password, and access code.
    *   Submits to `POST /signup`.
    *   Includes a link to switch back to the Login section.
*   **Upload (`upload-section`):**
    *   Displays RAG status (`dbStatusMessage`).
    *   Handles file input (`filesInput`), selected files preview (`selectedFilesPreview`), and custom instructions (`customInstructionsInput`).
    *   Shows upload status (`uploadStatus`) and processing status (`processStatus`).
    *   Buttons for uploading (`uploadButton`) and processing (`processFilesButton`).
*   **Chat (`chat-section`):**
    *   Buttons to select RAG context (`chatDefaultRagButton`, `chatCustomRagButton`).
    *   Chat messages display area (`chatMessages`).
    *   Chat input form (`chatForm`, `chatInput`).
    *   Chat status/typing indicator (`chatStatus`).

**Integration Points with `app.js` Logic (Confirm and Enhance):**

*   **Authentication:** The login form submission in `app.js` correctly calls `GET /upload/{username}`.
*   **Signup:** The signup form submission in `app.js` correctly calls `POST /signup` and handles responses.
*   **RAG Status:** `fetchUserRagStatus()` in `app.js` fetches and updates the UI.
*   **File Upload:** `uploadForm` submission handles sending files and instructions to `POST /upload/{user_name}`.
*   **Process Files:** `processFilesButton` click handler calls `POST /process_docs/{user_name}`.
*   **Chat Submission (`chatForm.addEventListener('submit', async (e) => { ... })`):**
    *   Ensure `currentSessionId` is generated if null (e.g., on first message or when chat section becomes active).
    *   The SSE handling logic within `app.js` needs to correctly parse the streamed JSON events and update `chatMessages` incrementally, potentially updating the last agent message if it's streaming, or appending new parts.
    *   The `appendChatMessage(sender, text, isThinking = false)` function is a good place to manage how streaming text updates an existing message bubble versus creating a new one.

## 6. Error Handling and User Feedback

*   **Clear Error Messages:** For API errors (4xx, 5xx), display user-friendly messages. `app.js` has `loginError`, `signupError`, `uploadStatus`, `processStatus`, `chatStatus` for these.
*   **Loading States:** Use spinners or messages like "Uploading...", "Processing...", "Agent is thinking..."
*   **Success Feedback:** Confirm actions like "Files uploaded successfully," "RAG updated," "Message sent."
*   **Rejected Files:** Clearly list which files were rejected during upload and why (from the `rejected_files` array in the upload response).

This guide, in conjunction with the Backend API Documentation, should provide frontend developers with the necessary information to successfully integrate with the Multi-Tool Agent backend.
