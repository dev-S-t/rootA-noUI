document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const loginSection = document.getElementById('login-section');
    const uploadSection = document.getElementById('upload-section');
    const chatSection = document.getElementById('chat-section');

    const userInfo = document.getElementById('user-info');
    const usernameDisplay = document.getElementById('username-display');
    const logoutButton = document.getElementById('logout-button');

    const loginForm = document.getElementById('login-form');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const loginError = document.getElementById('login-error');

    const dbStatusMessage = document.getElementById('db-status-message');
    const uploadForm = document.getElementById('upload-form');
    const filesInput = document.getElementById('files');
    const selectedFilesPreview = document.getElementById('selected-files-preview');
    const uploadButton = uploadForm.querySelector('button[type="submit"]');
    const uploadStatus = document.getElementById('upload-status');
    const processFilesButton = document.getElementById('process-files-button');
    const processStatus = document.getElementById('process-status');

    const toggleChatButton = document.getElementById('toggle-chat-button'); // This will be for Default RAG
    const chatCustomRagButton = document.getElementById('chat-custom-rag-button'); // New button for Custom RAG
    const backToUploadButton = document.getElementById('back-to-upload-button');

    const chatMessages = document.getElementById('chat-messages');
    const chatForm = document.getElementById('chat-form');
    const chatInput = document.getElementById('chat-input');
    const chatStatus = document.getElementById('chat-status');
    const chatSubmitButton = chatForm.querySelector('button[type="submit"]');
    const chatTitle = chatSection.querySelector('h2');

    // --- State Variables ---
    let currentUser = null;
    let currentPassword = null;
    let selectedFilesStore = [];
    let userHasCustomRag = false;
    let chatTargetIsCustom = false; // To track which RAG the chat is targeting
    let currentSessionId = null; // Added for stable session ID

    // --- UI Update Functions ---
    function updateUIState() {
        if (currentUser) {
            usernameDisplay.textContent = `${currentUser}`;
            userInfo.classList.remove('hidden');
            loginSection.classList.remove('active-section');
            loginSection.classList.add('hidden');

            uploadSection.classList.add('active-section');
            uploadSection.classList.remove('hidden');
            chatSection.classList.remove('active-section');
            chatSection.classList.add('hidden');

            // Make sure file input is visible when switching to upload section
            filesInput.classList.remove('hidden');
            uploadButton.classList.remove('hidden');
            uploadButton.textContent = 'Upload Files';
            uploadButton.disabled = false;

            toggleChatButton.textContent = 'Chat with Default RAG';
            toggleChatButton.classList.remove('hidden');

            const uploadSectionTitle = uploadSection.querySelector('h2');
            if (uploadSectionTitle) uploadSectionTitle.textContent = `Manage RAG for ${currentUser}`;
        } else {
            userInfo.classList.add('hidden');
            usernameDisplay.textContent = '';
            loginSection.classList.add('active-section');
            loginSection.classList.remove('hidden');
            uploadSection.classList.remove('active-section');
            uploadSection.classList.add('hidden');
            chatSection.classList.remove('active-section');
            chatSection.classList.add('hidden');
            toggleChatButton.classList.add('hidden');
            if (chatCustomRagButton) chatCustomRagButton.classList.add('hidden');

            clearUploadInfo();
            clearChat();
            selectedFilesStore = [];
            renderSelectedFilesPreview();
            currentSessionId = null; // Reset session ID on logout
        }
    }

    function clearUploadInfo() {
        dbStatusMessage.textContent = '';
        uploadStatus.textContent = '';
        processStatus.textContent = '';
        processFilesButton.classList.add('hidden');
        processFilesButton.textContent = 'Process Uploaded Files'; // Reset text
        processFilesButton.disabled = false; // Reset disabled state

        // Show file input and upload button again if they were hidden
        filesInput.classList.remove('hidden');
        uploadButton.classList.remove('hidden');
        uploadButton.textContent = 'Upload Files';
        uploadButton.disabled = false;

        filesInput.value = '';
        selectedFilesStore = [];
        renderSelectedFilesPreview();
        const apiInfoBox = document.getElementById('api-info-box');
        if (apiInfoBox) apiInfoBox.classList.add('hidden');
    }

    function clearChat() {
        chatMessages.innerHTML = '';
        chatInput.value = '';
        chatStatus.textContent = '';
        // currentSessionId is NOT reset here, only when navigating away or logging out.
    }

    function renderSelectedFilesPreview() {
        selectedFilesPreview.innerHTML = '';
        if (selectedFilesStore.length === 0) {
            selectedFilesPreview.classList.add('hidden');
            return;
        }
        selectedFilesPreview.classList.remove('hidden');
        const ul = document.createElement('ul');
        selectedFilesStore.forEach((file, index) => {
            const li = document.createElement('li');
            li.classList.add('selected-file-item');

            const fileNameSpan = document.createElement('span');
            fileNameSpan.textContent = file.name;
            li.appendChild(fileNameSpan);

            const removeButton = document.createElement('button');
            removeButton.classList.add('remove-file-button');
            removeButton.textContent = 'Remove';
            removeButton.type = 'button';
            removeButton.addEventListener('click', () => {
                selectedFilesStore.splice(index, 1);
                renderSelectedFilesPreview();
            });
            li.appendChild(removeButton);
            ul.appendChild(li);
        });
        selectedFilesPreview.appendChild(ul);
    }

    // --- Event Handlers ---
    filesInput.addEventListener('change', (e) => {
        const newFiles = Array.from(e.target.files);
        newFiles.forEach(newFile => {
            if (!selectedFilesStore.find(existingFile => existingFile.name === newFile.name && existingFile.size === newFile.size)) {
                selectedFilesStore.push(newFile);
            }
        });
        renderSelectedFilesPreview();
        e.target.value = null;
    });

    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = usernameInput.value.trim();
        const password = passwordInput.value;

        if (!username || !password) {
            loginError.textContent = 'Username and password are required.';
            loginError.style.color = 'red';
            return;
        }

        loginError.textContent = 'Attempting login...';
        loginError.style.color = 'var(--primary-color, blue)';

        try {
            const response = await fetch(`/upload/${username}`, {
                method: 'GET',
                headers: {
                    'Authorization': 'Basic ' + btoa(username + ":" + password)
                }
            });

            if (response.ok) {
                currentUser = username;
                currentPassword = password;
                loginError.textContent = 'Login successful!';
                loginError.style.color = 'green';
                passwordInput.value = '';
                updateUIState();
                await fetchUserRagStatus();
            } else if (response.status === 401) {
                loginError.textContent = 'Login failed: Invalid credentials.';
                loginError.style.color = 'red';
                currentUser = null;
                currentPassword = null;
            } else {
                const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                loginError.textContent = `Login failed: ${errorData.detail} (Status: ${response.status})`;
                loginError.style.color = 'red';
                currentUser = null;
                currentPassword = null;
            }
        } catch (error) {
            loginError.textContent = 'Login failed: Network error or server down.';
            loginError.style.color = 'red';
            console.error("Login error:", error);
            currentUser = null;
            currentPassword = null;
        }
    });

    logoutButton.addEventListener('click', () => {
        currentUser = null;
        currentPassword = null;
        userHasCustomRag = false;
        loginError.textContent = '';
        currentSessionId = null; // Reset session ID on logout
        updateUIState();
    });

    async function fetchUserRagStatus() {
        if (!currentUser) return;
        dbStatusMessage.textContent = 'Checking RAG status...';
        dbStatusMessage.style.color = 'var(--primary-color, blue)';
        processFilesButton.classList.add('hidden');

        try {
            const response = await fetch(`/upload/${currentUser}`, {
                method: 'GET',
                headers: { 'Authorization': 'Basic ' + btoa(currentUser + ":" + currentPassword) }
            });
            const data = await response.json();

            if (response.ok) {
                dbStatusMessage.textContent = data.message;
                userHasCustomRag = data.db_exists;
                dbStatusMessage.style.color = userHasCustomRag ? 'green' : 'orange';

                if (data.temp_files_exist) {
                    processFilesButton.classList.remove('hidden');
                    dbStatusMessage.textContent += " Pending files to process.";
                }

                // Revised logic for chatCustomRagButton visibility
                if (chatCustomRagButton) { // Check if the button element exists in the DOM
                    if (userHasCustomRag) { // And the user has a custom RAG
                        chatCustomRagButton.textContent = `Chat with ${currentUser}'s RAG`;
                        chatCustomRagButton.classList.remove('hidden'); // Show it
                    } else { // User does not have a custom RAG (db_exists was false)
                        chatCustomRagButton.classList.add('hidden'); // Hide it
                    }
                }

            } else {
                dbStatusMessage.textContent = `Error checking status: ${data.detail || response.statusText}`;
                dbStatusMessage.style.color = 'red';
                userHasCustomRag = false;
                if (chatCustomRagButton) { // Ensure button is hidden on error
                    chatCustomRagButton.classList.add('hidden');
                }
            }
        } catch (error) {
            dbStatusMessage.textContent = 'Error checking RAG status (network/server issue).';
            dbStatusMessage.style.color = 'red';
            console.error("RAG status error:", error);
            userHasCustomRag = false;
            if (chatCustomRagButton) { // Ensure button is hidden on error
                chatCustomRagButton.classList.add('hidden');
            }
        }
    }

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        if (!currentUser || selectedFilesStore.length === 0) {
            uploadStatus.textContent = 'Please select one or more PDF/DOCX files to upload.';
            uploadStatus.style.color = 'orange';
            return;
        }

        const formData = new FormData();
        selectedFilesStore.forEach(file => {
            formData.append('files', file);
        });

        uploadStatus.textContent = 'Uploading file(s)...';
        uploadStatus.style.color = 'var(--primary-color, blue)';
        uploadButton.disabled = true;
        uploadButton.textContent = 'Uploading...';
        processFilesButton.classList.add('hidden');

        try {
            const response = await fetch(`/upload/${currentUser}`, {
                method: 'POST',
                headers: {
                    'Authorization': 'Basic ' + btoa(currentUser + ":" + currentPassword)
                },
                body: formData
            });
            const data = await response.json();

            if (response.ok) {
                uploadStatus.textContent = data.message || 'Files staged on server. Ready to process.';
                uploadStatus.style.color = 'green';

                if (data.uploaded_files && data.uploaded_files.length > 0) {
                    processFilesButton.textContent = 'Confirm and Process Files'; // Confirm text
                    processFilesButton.classList.remove('hidden');
                    processStatus.textContent = 'Please click "Confirm and Process Files" to build/update your RAG.';
                    processStatus.style.color = 'var(--primary-color, blue)';

                    // Hide file input and upload button as files are staged
                    filesInput.classList.add('hidden');
                    uploadButton.classList.add('hidden');
                    uploadStatus.textContent = ''; // Clear initial upload status, processStatus takes over

                } else {
                    processFilesButton.classList.add('hidden');
                    if (!data.rejected_files || data.rejected_files.length === 0) {
                        uploadStatus.textContent = 'No valid files were processed by the server.';
                        uploadStatus.style.color = 'orange';
                    }
                    // Keep file input and upload button visible if no files were actually staged
                    filesInput.classList.remove('hidden');
                    uploadButton.classList.remove('hidden');
                }
                selectedFilesStore = []; // Clear store after successful staging
                renderSelectedFilesPreview(); // Clear preview
            } else {
                uploadStatus.textContent = `Upload failed: ${data.detail || response.statusText}`;
                uploadStatus.style.color = 'red';
                // Keep file input and upload button visible on failure
                filesInput.classList.remove('hidden');
                uploadButton.classList.remove('hidden');
            }
        } catch (error) {
            uploadStatus.textContent = 'Upload error: Network issue or server down.';
            uploadStatus.style.color = 'red';
            console.error("Upload error:", error);
            // Keep file input and upload button visible on error
            filesInput.classList.remove('hidden');
            uploadButton.classList.remove('hidden');
        } finally {
            // Only re-enable upload button if it's still visible (i.e., staging didn't hide it)
            if (!uploadButton.classList.contains('hidden')) {
                uploadButton.disabled = false;
                uploadButton.textContent = 'Upload Files';
            }
        }
    });

    processFilesButton.addEventListener('click', async () => {
        if (!currentUser) return;

        processStatus.textContent = 'Processing documents... This may take a moment.';
        processStatus.style.color = 'var(--primary-color, blue)';
        processFilesButton.disabled = true;
        processFilesButton.textContent = 'Processing...';
        const apiInfoBox = document.getElementById('api-info-box');

        try {
            const response = await fetch(`/process_docs/${currentUser}`, {
                method: 'POST',
                headers: {
                    'Authorization': 'Basic ' + btoa(currentUser + ":" + currentPassword),
                }
            });
            const data = await response.json();
            if (response.ok) {
                processStatus.textContent = data.message || 'Documents processed successfully! RAG updated.';
                processStatus.style.color = 'green';
                processFilesButton.classList.add('hidden'); // Hide after successful processing
                await fetchUserRagStatus(); // This updates userHasCustomRag and custom chat button visibility

                // Show file input and upload button again for next batch
                filesInput.classList.remove('hidden');
                uploadButton.classList.remove('hidden');
                uploadButton.textContent = 'Upload Files';
                uploadButton.disabled = false;

                // --- START: API Info Box Logic ---
                if (apiInfoBox && currentUser) {
                    const runEndpoint = `${window.location.origin}/run/${currentUser}`;
                    const runSseEndpoint = `${window.location.origin}/run_sse/${currentUser}`;
                    const base64Credentials = btoa(currentUser + ":" + "YOUR_PASSWORD_HERE");

                    const curlCommand = `curl -X POST "${runEndpoint}" \\
  -H "Authorization: Basic ${base64Credentials}" \\
  -H "Content-Type: application/json" \\
  -d '{
    "prompt": "Hello, custom RAG!",
    "user_id": "${currentUser}",
    "session_id": "your_unique_session_id_123"
  }'`;

                    apiInfoBox.innerHTML = `
                        <h3>API Endpoint Information</h3>
                        <p>Your custom RAG for '<strong>${currentUser}</strong>' is ready! You can interact with it programmatically:</p>
                        <p><strong>Chat (blocking):</strong> <code>${runEndpoint}</code></p>
                        <p><strong>Chat (streaming):</strong> <code>${runSseEndpoint}</code></p>
                        <h4>Example cURL Request (replace YOUR_PASSWORD_HERE with your password):</h4>
                        <pre><code id="api-curl-example">${curlCommand.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</code></pre>
                        <p><em>Note: The username '${currentUser}' is pre-filled in the example.</em></p>
                    `;
                    apiInfoBox.classList.remove('hidden');
                }
                // --- END: API Info Box Logic ---

            } else {
                processStatus.textContent = `Processing failed: ${data.detail || response.statusText}`;
                processStatus.style.color = 'red';
                // Don't hide the button on failure, allow retry
                processFilesButton.disabled = false;
                processFilesButton.textContent = 'Confirm and Process Files';
            }
        } catch (error) {
            processStatus.textContent = 'Processing error: Network issue or server down.';
            processStatus.style.color = 'red';
            console.error("Processing error:", error);
            // Don't hide the button on failure, allow retry
            processFilesButton.disabled = false;
            processFilesButton.textContent = 'Confirm and Process Files';
        } finally {
            // If processing was successful, button is hidden. If not, it's re-enabled above.
            // If an unexpected error didn't lead to .ok or .notOk, ensure button is usable.
            if (processStatus.style.color !== 'green' && processFilesButton.disabled) {
                processFilesButton.disabled = false;
                processFilesButton.textContent = 'Confirm and Process Files';
            }
        }
    });

    toggleChatButton.addEventListener('click', () => { // This is now the "Chat with Default RAG" button
        uploadSection.classList.remove('active-section');
        uploadSection.classList.add('hidden');
        chatSection.classList.add('active-section');
        chatSection.classList.remove('hidden');

        chatTitle.textContent = `Chat with Default RAG Agent`;
        if (chatTargetIsCustom || !currentSessionId) { // If changing target or no session ID
            currentSessionId = `chat_default_${currentUser}_${Date.now()}`;
        }
        chatTargetIsCustom = false; // Target default RAG
        clearChat();
    });

    if (chatCustomRagButton) {
        chatCustomRagButton.addEventListener('click', () => { // New listener for Custom RAG button
            uploadSection.classList.remove('active-section');
            uploadSection.classList.add('hidden');
            chatSection.classList.add('active-section');
            chatSection.classList.remove('hidden');

            if (currentUser) {
                chatTitle.textContent = `Chat with ${currentUser}'s RAG Agent`;
            } else {
                chatTitle.textContent = `Chat with Custom RAG Agent`; // Fallback
            }
            if (!chatTargetIsCustom || !currentSessionId) { // If changing target or no session ID
                currentSessionId = `chat_${currentUser}_${Date.now()}`;
            }
            chatTargetIsCustom = true; // Target custom RAG
            clearChat();
        });
    }

    backToUploadButton.addEventListener('click', () => {
        chatSection.classList.remove('active-section');
        chatSection.classList.add('hidden');
        uploadSection.classList.add('active-section');
        uploadSection.classList.remove('hidden');
        currentSessionId = null; // Reset session ID when leaving chat section

        // Ensure file input and upload button are visible when navigating back
        filesInput.classList.remove('hidden');
        uploadButton.classList.remove('hidden');
        uploadButton.textContent = 'Upload Files';
        uploadButton.disabled = false;
    });

    chatForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const message = chatInput.value.trim();
        if (!message || !currentUser) return;

        appendChatMessage('user', message);
        chatInput.value = '';
        chatInput.disabled = true;
        chatSubmitButton.disabled = true;
        chatStatus.textContent = '';

        const thinkingMessage = appendChatMessage('agent', 'Thinking...', true);

        const endpoint = chatTargetIsCustom && currentUser ? `/run/${currentUser}` : '/run';

        // Ensure session ID is generated if somehow missed (e.g., direct navigation or refresh)
        if (!currentSessionId) {
            if (chatTargetIsCustom && currentUser) {
                currentSessionId = `chat_${currentUser}_${Date.now()}`;
            } else {
                currentSessionId = `chat_default_${currentUser}_${Date.now()}`;
            }
            console.warn("Session ID was not set, generated new one:", currentSessionId);
        }

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Basic ' + btoa(currentUser + ":" + currentPassword)
                },
                body: JSON.stringify({
                    "messages": [{ "role": "user", "content": message }],
                    "context_overrides": {
                        "user_id": currentUser,
                        "session_id": currentSessionId // Use the stable session ID
                    }
                })
            });

            if (thinkingMessage) thinkingMessage.remove();

            if (response.ok) {
                const data = await response.json();
                let agentResponse = "No response content found.";
                if (data && data.response) {
                    agentResponse = data.response;
                } else if (data && data.messages && data.messages.length > 0) {
                    const assistantMsg = data.messages.find(m => m.role === 'assistant');
                    if (assistantMsg) agentResponse = assistantMsg.content;
                } else if (typeof data === 'string') {
                    agentResponse = data;
                }
                appendChatMessage('agent', agentResponse);
            } else {
                const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                appendChatMessage('agent', `Error: ${errorData.detail || 'Failed to get response'}`);
                chatStatus.textContent = `Chat error: ${errorData.detail || response.statusText}`;
                chatStatus.style.color = 'red';
            }
        } catch (error) {
            if (thinkingMessage) thinkingMessage.remove();
            appendChatMessage('agent', 'Error: Could not connect to the agent.');
            chatStatus.textContent = 'Chat error: Network issue or server down.';
            chatStatus.style.color = 'red';
            console.error("Chat error:", error);
        } finally {
            chatInput.disabled = false;
            chatSubmitButton.disabled = false;
            chatInput.focus();
        }
    });

    function appendChatMessage(sender, text, isThinking = false) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message');
        messageElement.classList.add(sender === 'user' ? 'user-message' : 'agent-message');

        if (isThinking) {
            messageElement.classList.add('thinking');
            messageElement.textContent = text;
        } else {
            const sanitizedText = text.replace(/</g, "&lt;").replace(/>/g, "&gt;");
            messageElement.innerHTML = `<strong>${sender.charAt(0).toUpperCase() + sender.slice(1)}:</strong> ${sanitizedText}`;
        }

        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return messageElement;
    }

    // --- Initial Setup ---
    updateUIState();
    renderSelectedFilesPreview();
});
