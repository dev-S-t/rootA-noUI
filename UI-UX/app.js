document.addEventListener('DOMContentLoaded', () => {
    // --- DOM Elements ---
    const loginSection = document.getElementById('login-section');
    const uploadSection = document.getElementById('upload-section');
    const chatSection = document.getElementById('chat-section');
    const signupSection = document.getElementById('signup-section'); // Added

    const userInfo = document.getElementById('user-info');
    const usernameDisplay = document.getElementById('username-display');
    const logoutButton = document.getElementById('logout-button');

    const loginForm = document.getElementById('login-form');
    const usernameInput = document.getElementById('username');
    const passwordInput = document.getElementById('password');
    const loginError = document.getElementById('login-error');

    // Signup form elements
    const signupForm = document.getElementById('signup-form');
    const signupUsernameInput = document.getElementById('signup-username');
    const signupPasswordInput = document.getElementById('signup-password');
    const accessCodeInput = document.getElementById('access-code');
    const signupMessage = document.getElementById('signup-message');
    const showSignupLink = document.getElementById('show-signup-link');
    const showLoginLink = document.getElementById('show-login-link');

    const dbStatusMessage = document.getElementById('db-status-message');
    const uploadForm = document.getElementById('upload-form');
    const filesInput = document.getElementById('files');
    const selectedFilesPreview = document.getElementById('selected-files-preview');
    const customInstructionsInput = document.getElementById('custom-instructions'); // Added for custom instructions
    const uploadButton = uploadForm.querySelector('button[type="submit"]');
    const uploadStatus = document.getElementById('upload-status');
    const processFilesButton = document.getElementById('process-files-button');
    const processStatus = document.getElementById('process-status');

    const chatDefaultRagButton = document.getElementById('chat-default-rag-button');
    const chatDefaultRagSseButton = document.getElementById('chat-default-rag-sse-button'); // New button
    const chatCustomRagButton = document.getElementById('chat-custom-rag-button');
    const chatCustomRagSseButton = document.getElementById('chat-custom-rag-sse-button'); // New button for custom RAG with steps
    const backToUploadButton = document.getElementById('back-to-upload-button');

    // Log initial element fetching
    console.log('Initial DOM elements:');
    console.log('chatCustomRagButton:', chatCustomRagButton);
    console.log('chatCustomRagSseButton:', chatCustomRagSseButton);

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
    let streamWithSteps = false; // New flag for SSE streaming with steps

    // --- Helper Function to Generate Session ID ---
    function generateSessionId() {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
            var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        });
    }

    // --- Helper Functions for Markdown Rendering ---
    function decodeHtmlEntities(text) {
        const textarea = document.createElement('textarea');
        textarea.innerHTML = text;
        return textarea.value;
    }

    function markdownToHtml(markdown) {
        let html = decodeHtmlEntities(markdown);

        // Normalize line endings
        html = html.replace(/\r\n?/g, '\n');

        // Placeholders for content that should not be processed further by markdown rules
        const placeholders = [];
        let placeholderId = 0;
        const addPlaceholder = (content) => {
            placeholders[placeholderId] = content;
            return `%%PLACEHOLDER_${placeholderId++}%%`;
        };

        // Code blocks (```lang\ncode\n``` or ```\ncode\n```)
        html = html.replace(/^```(\w*)\n([\s\S]*?)\n```$/gm, (match, lang, code) => {
            const languageClass = lang ? `language-${lang}` : '';
            const escapedCode = code.replace(/</g, '&lt;').replace(/>/g, '&gt;');
            return addPlaceholder(`\n<pre><code class="${languageClass}">${escapedCode.trim()}\n</code></pre>\n`);
        });
        
        // Inline code (`code`)
        html = html.replace(/`([^`]+?)`/g, (match, code) => {
            return addPlaceholder(`<code>${code.replace(/</g, '&lt;').replace(/>/g, '&gt;')}</code>`);
        });

        // Headings (###### H6 through # H1)
        html = html.replace(/^###### (.*$)/gim, '<h6>$1</h6>');
        html = html.replace(/^##### (.*$)/gim, '<h5>$1</h5>');
        html = html.replace(/^#### (.*$)/gim, '<h4>$1</h4>');
        html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');

        // Horizontal Rules (---, ***, ___)
        html = html.replace(/^(?:---|___|\*\*\*)\s*$/gm, '<hr>');

        // Blockquotes (> text)
        // Process line by line for blockquotes to handle multi-line quotes correctly
        html = html.split('\n').map(line => {
            if (line.match(/^> /)) {
                return line.replace(/^> (.*)/, '<blockquote>$1</blockquote>');
            }
            return line;
        }).join('\n');
        html = html.replace(/<\/blockquote>\n?<blockquote>/g, '\n'); // Merge adjacent

        // Lists (Unordered: *, -, +; Ordered: 1.)
        // This is a simplified list handling. Does not handle deep nesting well.
        // Unordered lists
        html = html.replace(/^\s*([*+-]) +(.*)/gm, '<li>$2</li>');
        // Ordered lists
        html = html.replace(/^\s*(\d+)\. +(.*)/gm, '<li>$2</li>'); // Simplified to <li>, <ol> can add start later if needed

        // Wrap consecutive <li> elements in <ul> or <ol>
        // This regex is basic and assumes all lists are <ul> for simplicity here.
        // A more robust solution would differentiate based on original markers.
        html = html.replace(/((?:<li>.*?<\/li>\n?)+)/g, (match) => {
            return `<ul>\n${match.trim()}\n</ul>\n`;
        });
        html = html.replace(/<\/ul>\s*<ul>/g, ''); // Clean up adjacent <ul> tags

        // Links: [text](url "title") or [text](url)
        html = html.replace(/\[([^\]]+)\]\(([^)\s]+)(?:\s+"([^"]+)")?\)/g, (match, text, url, title) => {
            const titleAttr = title ? ` title="${title}"` : '';
            // Ensure URL is not a placeholder before making it a link
            if (url.startsWith('%%PLACEHOLDER_')) return match; // Don't link placeholders
            return `<a href="${url}"${titleAttr} target="_blank">${text}</a>`;
        });
        
        // Emphasis (Order matters: process stronger/longer patterns first)
        // Bold and Italic combined (***text*** or ___text___)
        html = html.replace(/(?:\*\*\*|___)([^\*\n_]+?)(?:\*\*\*|___)/g, '<strong><em>$1</em></strong>');
        // Bold (**text** or __text__)
        html = html.replace(/(?:\*\*|__)([^\*\n_]+?)(?:\*\*|__)/g, '<strong>$1</strong>');
        // Italic (*text* or _text_)
        html = html.replace(/(?:\*|_)([^\*\n_]+?)(?:\*|_)/g, '<em>$1</em>');
        // Strikethrough (~~text~~)
        html = html.replace(/~~([^~]+?)~~/g, '<del>$1</del>');

        // Paragraphs: Wrap lines that are not part of other block elements
        html = html.split('\n').map(line => {
            const trimmedLine = line.trim();
            if (trimmedLine === '') return '';
            // Check if the line is already a block element or a placeholder
            if (/^<(ul|ol|li|h[1-6]|blockquote|hr|pre|p|div)/i.test(trimmedLine) || 
                /%%PLACEHOLDER_\d+%%/.test(trimmedLine) ||
                /^<\/(ul|ol|h[1-6]|blockquote|pre|p|div)>/.test(trimmedLine)) {
                return line;
            }
            return `<p>${line}</p>`;
        }).join('\n');
        
        html = html.replace(/<p>\s*<\/p>/g, ''); // Remove empty paragraphs
        html = html.replace(/\n/g, '<br>'); // Convert remaining newlines to <br>

        // Restore placeholders
        for (let i = 0; i < placeholderId; i++) {
            // Ensure regex is safe for replacement string
            const placeholderRegex = new RegExp(`%%PLACEHOLDER_${i}%%`, 'g');
            html = html.replace(placeholderRegex, placeholders[i]);
        }
        
        // Final cleanup of <br> tags that might be redundant
        html = html.replace(/<br\s*\/?>\s*(<(ul|ol|li|h[1-6]|blockquote|hr|p|div|pre))/gi, '$1');
        html = html.replace(/(<\/(ul|ol|li|h[1-6]|blockquote|hr|p|div|pre)>)\s*<br\s*\/?>/gi, '$1');
        html = html.replace(/(<br\s*\/?>\s*){2,}/gi, '<br>');
        html = html.replace(/^<br\s*\/?>|<br\s*\/?>$/g, ''); // Remove leading/trailing <br>

        return html.trim();
    }

    // --- UI Update Functions ---
    function updateUIState() {
        if (currentUser) {
            usernameDisplay.textContent = `${currentUser}`;
            userInfo.classList.remove('hidden');
            loginSection.classList.remove('active-section');
            loginSection.classList.add('hidden');
            signupSection.classList.remove('active-section'); // Hide signup when logged in
            signupSection.classList.add('hidden');

            uploadSection.classList.add('active-section');
            uploadSection.classList.remove('hidden');
            chatSection.classList.remove('active-section');
            chatSection.classList.add('hidden');

            // Make sure file input and instructions are visible when switching to upload section
            filesInput.classList.remove('hidden');
            if (customInstructionsInput) customInstructionsInput.classList.remove('hidden'); // Show instructions input
            uploadButton.classList.remove('hidden');
            uploadButton.textContent = 'Upload Files & Instructions'; // Updated button text
            uploadButton.disabled = false;

            chatDefaultRagButton.textContent = 'Chat with Default RAG'; // Updated
            chatDefaultRagButton.classList.remove('hidden');
            chatDefaultRagSseButton.classList.remove('hidden'); // Show SSE button

            const uploadSectionTitle = uploadSection.querySelector('h2');
            if (uploadSectionTitle) uploadSectionTitle.textContent = `Manage RAG for ${currentUser}`;
        } else {
            userInfo.classList.add('hidden');
            usernameDisplay.textContent = '';
            loginSection.classList.add('active-section');
            loginSection.classList.remove('hidden');
            signupSection.classList.remove('active-section'); // Ensure signup is hidden initially if not logged in
            signupSection.classList.add('hidden');
            uploadSection.classList.remove('active-section');
            uploadSection.classList.add('hidden');
            chatSection.classList.remove('active-section');
            chatSection.classList.add('hidden');
            chatDefaultRagButton.classList.add('hidden'); // Updated
            chatDefaultRagSseButton.classList.add('hidden'); // Hide SSE button
            if (chatCustomRagButton) chatCustomRagButton.classList.add('hidden');
            if (chatCustomRagSseButton) chatCustomRagSseButton.classList.add('hidden'); // Hide custom SSE button

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
        if (customInstructionsInput) customInstructionsInput.classList.remove('hidden'); // Show instructions input
        uploadButton.classList.remove('hidden');
        uploadButton.textContent = 'Upload Files & Instructions'; // Updated button text
        uploadButton.disabled = false;

        filesInput.value = '';
        if (customInstructionsInput) customInstructionsInput.value = ''; // Clear instructions input
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

    showSignupLink.addEventListener('click', (e) => {
        e.preventDefault();
        loginSection.classList.remove('active-section');
        loginSection.classList.add('hidden');
        signupSection.classList.add('active-section');
        signupSection.classList.remove('hidden');
        loginError.textContent = ''; // Clear login errors
        signupMessage.textContent = ''; // Clear previous signup messages
    });

    showLoginLink.addEventListener('click', (e) => {
        e.preventDefault();
        signupSection.classList.remove('active-section');
        signupSection.classList.add('hidden');
        loginSection.classList.add('active-section');
        loginSection.classList.remove('hidden');
        signupMessage.textContent = ''; // Clear signup errors
        loginError.textContent = ''; // Clear previous login messages
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

    signupForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const username = signupUsernameInput.value.trim();
        const password = signupPasswordInput.value;
        const accessCode = accessCodeInput.value.trim();

        if (!username || !password || !accessCode) {
            signupMessage.textContent = 'All fields are required for signup.';
            signupMessage.style.color = 'red';
            return;
        }

        signupMessage.textContent = 'Attempting to sign up...';
        signupMessage.style.color = 'var(--primary-color, blue)';

        try {
            const response = await fetch('/signup', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    username: username,
                    password: password,
                    access_code: accessCode
                })
            });

            const data = await response.json();

            if (response.ok) {
                signupMessage.textContent = data.message + ' Please login.';
                signupMessage.style.color = 'green';
                signupForm.reset(); // Clear the form
                // Optionally, switch to login view automatically
                setTimeout(() => {
                    signupSection.classList.remove('active-section');
                    signupSection.classList.add('hidden');
                    loginSection.classList.add('active-section');
                    loginSection.classList.remove('hidden');
                    loginError.textContent = ''; // Clear previous login messages
                }, 2000); // Switch after 2 seconds
            } else {
                signupMessage.textContent = `Signup failed: ${data.detail || response.statusText}`;
                signupMessage.style.color = 'red';
            }
        } catch (error) {
            signupMessage.textContent = 'Signup failed: Network error or server down.';
            signupMessage.style.color = 'red';
            console.error("Signup error:", error);
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
        console.log('[fetchUserRagStatus] Called for user:', currentUser);
        console.log('[fetchUserRagStatus] chatCustomRagSseButton element at start of function:', chatCustomRagSseButton);


        try {
            const response = await fetch(`/upload/${currentUser}`, {
                method: 'GET',
                headers: { 'Authorization': 'Basic ' + btoa(currentUser + ":" + currentPassword) }
            });
            const data = await response.json();
            console.log('[fetchUserRagStatus] Response data:', data);

            if (response.ok) {
                dbStatusMessage.textContent = data.message;
                userHasCustomRag = data.db_exists;
                console.log('[fetchUserRagStatus] userHasCustomRag set to:', userHasCustomRag);
                dbStatusMessage.style.color = userHasCustomRag ? 'green' : 'orange';

                if (data.temp_files_exist) {
                    processFilesButton.classList.remove('hidden');
                    dbStatusMessage.textContent += " Pending files to process.";
                }

                // Revised logic for custom RAG buttons visibility
                if (userHasCustomRag) {
                    if (chatCustomRagButton) {
                        chatCustomRagButton.textContent = `Chat with ${currentUser}'s RAG`;
                        chatCustomRagButton.classList.remove('hidden');
                        console.log('[fetchUserRagStatus] chatCustomRagButton made visible.');
                    } else {
                        console.log('[fetchUserRagStatus] chatCustomRagButton element NOT found (userHasCustomRag true).');
                    }
                    if (chatCustomRagSseButton) {
                        chatCustomRagSseButton.textContent = `Chat with ${currentUser}'s RAG (Show Steps)`;
                        chatCustomRagSseButton.classList.remove('hidden');
                        console.log('[fetchUserRagStatus] chatCustomRagSseButton made visible. Classes:', chatCustomRagSseButton.classList.toString());
                    } else {
                        console.log('[fetchUserRagStatus] chatCustomRagSseButton element NOT found (userHasCustomRag true).');
                    }
                } else { // userHasCustomRag is false
                    if (chatCustomRagButton) {
                        chatCustomRagButton.classList.add('hidden');
                        console.log('[fetchUserRagStatus] chatCustomRagButton hidden.');
                    } else {
                        console.log('[fetchUserRagStatus] chatCustomRagButton element NOT found (userHasCustomRag false).');
                    }
                    if (chatCustomRagSseButton) {
                        chatCustomRagSseButton.classList.add('hidden');
                        console.log('[fetchUserRagStatus] chatCustomRagSseButton hidden. Classes:', chatCustomRagSseButton.classList.toString());
                    } else {
                        console.log('[fetchUserRagStatus] chatCustomRagSseButton element NOT found (userHasCustomRag false).');
                    }
                }

            } else {
                dbStatusMessage.textContent = `Error checking status: ${data.detail || response.statusText}`;
                dbStatusMessage.style.color = 'red';
                userHasCustomRag = false;
                console.error('[fetchUserRagStatus] Response not OK. Status:', response.status, 'Detail:', data.detail);
                if (chatCustomRagButton) {
                    chatCustomRagButton.classList.add('hidden');
                }
                if (chatCustomRagSseButton) {
                    chatCustomRagSseButton.classList.add('hidden');
                    console.log('[fetchUserRagStatus] chatCustomRagSseButton hidden due to response error.');
                }
            }
        } catch (error) {
            dbStatusMessage.textContent = 'Error checking RAG status (network/server issue).';
            dbStatusMessage.style.color = 'red';
            console.error("[fetchUserRagStatus] Error in try-catch block:", error);
            userHasCustomRag = false;
            if (chatCustomRagButton) {
                chatCustomRagButton.classList.add('hidden');
            }
            if (chatCustomRagSseButton) {
                chatCustomRagSseButton.classList.add('hidden');
                console.log('[fetchUserRagStatus] chatCustomRagSseButton hidden due to catch error.');
            }
        }
    }

    uploadForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        const customInstructionsText = customInstructionsInput ? customInstructionsInput.value : ''; // Original value

        if (!currentUser) return;

        if (selectedFilesStore.length === 0 && customInstructionsText.trim() === '') {
            uploadStatus.textContent = 'Please select files to upload or enter custom agent instructions.';
            uploadStatus.style.color = 'orange';
            return;
        }

        uploadButton.disabled = true;
        uploadButton.textContent = 'Uploading...';
        processFilesButton.classList.add('hidden');
        uploadStatus.innerHTML = ''; // Clear previous messages

        const BATCH_SIZE = 50;
        let overallSuccess = true;
        let anyFilesStaged = false;
        let aggregatedUploadedFiles = [];
        let aggregatedRejectedFiles = [];
        let lastInstructionStatus = '';
        let lastGeneralMessage = '';

        // If there are files, batch them.
        if (selectedFilesStore.length > 0) {
            uploadStatus.innerHTML = '<h4>Upload Progress:</h4>';
            for (let i = 0; i < selectedFilesStore.length; i += BATCH_SIZE) {
                const batchFiles = selectedFilesStore.slice(i, i + BATCH_SIZE);
                const batchFormData = new FormData();
                batchFiles.forEach(file => batchFormData.append('files', file));
                batchFormData.append('custom_instructions', customInstructionsText); // Send original instructions text

                const batchNumber = (i / BATCH_SIZE) + 1;
                const totalBatches = Math.ceil(selectedFilesStore.length / BATCH_SIZE);
                uploadStatus.innerHTML += `<p>Uploading batch ${batchNumber} of ${totalBatches} (${batchFiles.length} files)...</p>`;

                try {
                    const response = await fetch(`/upload/${currentUser}`, {
                        method: 'POST',
                        headers: { 'Authorization': 'Basic ' + btoa(currentUser + ":" + currentPassword) },
                        body: batchFormData
                    });
                    
                    // Try to parse JSON regardless of response.ok for error details from server
                    let data = {};
                    try {
                        data = await response.json();
                    } catch (jsonError) {
                        // If JSON parsing fails, server might have sent HTML (e.g. for 413 from proxy)
                        // or a non-JSON error.
                        if (!response.ok) { // If HTTP status is also an error
                             const rawText = await response.text(); // get raw response
                             data = { detail: `Server returned non-JSON response (Status: ${response.status}). Response: ${rawText.substring(0,100)}...` };
                        } else { // response.ok but not JSON - less likely for this endpoint
                             data = { detail: "Server returned non-JSON response but status was OK."};
                        }
                        console.error("JSON parsing error during upload batch:", jsonError, "Raw response:", await response.text());
                    }


                    if (response.ok) {
                        if (data.uploaded_files && data.uploaded_files.length > 0) {
                            anyFilesStaged = true;
                            aggregatedUploadedFiles.push(...data.uploaded_files);
                            uploadStatus.innerHTML += `<p style="color: green;">&nbsp;&nbsp;&nbsp;&#10004; Batch ${batchNumber}: ${data.uploaded_files.length} file(s) staged.</p>`;
                        }
                        if (data.rejected_files && data.rejected_files.length > 0) {
                            aggregatedRejectedFiles.push(...data.rejected_files);
                            uploadStatus.innerHTML += `<p style="color: orange;">&nbsp;&nbsp;&nbsp;&#x26A0; Batch ${batchNumber}: ${data.rejected_files.length} file(s) rejected.</p>`;
                        }
                        if (data.instructions_status) {
                            lastInstructionStatus = data.instructions_status;
                        }
                        if (data.message) {
                            lastGeneralMessage = data.message;
                        }
                    } else {
                        overallSuccess = false;
                        uploadStatus.innerHTML += `<p style="color: red;">&nbsp;&nbsp;&nbsp;&#10060; Error in batch ${batchNumber}: ${data.detail || response.statusText}</p>`;
                        // break; // Optional: stop on first batch error
                    }
                } catch (error) { // Network or other fetch-related error
                    overallSuccess = false;
                    uploadStatus.innerHTML += `<p style="color: red;">&nbsp;&nbsp;&nbsp;&#10060; Network error during batch ${batchNumber}: ${error.message}</p>`;
                    console.error(`Upload error in batch ${batchNumber}:`, error);
                    break; // Stop on network error
                }
            }
        } else if (customInstructionsText.trim() !== '') { // Only custom instructions, no files
            uploadStatus.innerHTML = '<h4>Upload Progress:</h4><p>Uploading custom instructions...</p>';
            const instructionFormData = new FormData();
            instructionFormData.append('custom_instructions', customInstructionsText);

            try {
                const response = await fetch(`/upload/${currentUser}`, {
                    method: 'POST',
                    headers: { 'Authorization': 'Basic ' + btoa(currentUser + ":" + currentPassword) },
                    body: instructionFormData
                });
                const data = await response.json();
                if (response.ok) {
                    if (data.instructions_status) {
                        lastInstructionStatus = data.instructions_status;
                    }
                    if (data.message) {
                        lastGeneralMessage = data.message;
                    }
                } else {
                    overallSuccess = false;
                    lastGeneralMessage = `Error uploading instructions: ${data.detail || response.statusText}`;
                }
            } catch (error) {
                overallSuccess = false;
                lastGeneralMessage = `Network error uploading instructions: ${error.message}`;
                console.error("Instruction upload error:", error);
            }
        }

        // After all batches or instruction-only upload: Display Summary
        let summaryHTML = '<h4>Upload Summary:</h4>';
        if (selectedFilesStore.length > 0) { // If files were part of the attempt
            summaryHTML += `<p>Total files selected for upload: ${selectedFilesStore.length}</p>`;
            if (aggregatedUploadedFiles.length > 0) {
                summaryHTML += `<p style="color: green;">Total files successfully staged: ${aggregatedUploadedFiles.length}</p>`;
            }
            if (aggregatedRejectedFiles.length > 0) {
                summaryHTML += `<p style="color: orange;">Total files rejected: ${aggregatedRejectedFiles.length}</p>`;
                // aggregatedRejectedFiles.forEach(rf => summaryHTML += `<p style="color: orange;">&nbsp;&nbsp;- ${rf.name}: ${rf.reason}</p>`);
            }
            if (aggregatedUploadedFiles.length === 0 && selectedFilesStore.length > 0) {
                 summaryHTML += `<p style="color: red;">No files were successfully staged from the selection.</p>`;
            }
        }

        if (lastInstructionStatus) {
            let color = 'var(--text-color, black)';
            if (lastInstructionStatus.startsWith('Failed')) color = 'red';
            else if (lastInstructionStatus.includes('saved as')) color = 'green';
            else if (lastInstructionStatus.includes('submitted empty')) color = 'orange';
            summaryHTML += `<p>Instructions Status: <span style="color: ${color};">${lastInstructionStatus}</span></p>`;
        }
        
        if (lastGeneralMessage && !(selectedFilesStore.length > 0 && anyFilesStaged)) { // Show general message if relevant
            summaryHTML += `<p>${lastGeneralMessage}</p>`;
        }

        if (!overallSuccess) {
            summaryHTML += '<p style="color: red;">One or more steps in the upload process encountered an error. Please review messages above.</p>';
        } else if (selectedFilesStore.length === 0 && customInstructionsText.trim() !== '' && lastInstructionStatus.includes('saved as')) {
            summaryHTML += '<p style="color: green;">Custom instructions submitted successfully.</p>';
        } else if (anyFilesStaged) {
             summaryHTML += '<p style="color: green;">File upload process completed.</p>';
        }


        uploadStatus.innerHTML += summaryHTML; // Append summary to progress messages

        if (anyFilesStaged) {
            processFilesButton.textContent = 'Confirm and Process Staged Files';
            processFilesButton.classList.remove('hidden');
            processStatus.textContent = 'Please click "Confirm and Process Staged Files" to build/update your RAG.';
            processStatus.style.color = 'var(--primary-color, blue)';
            
            filesInput.classList.add('hidden');
            if (customInstructionsInput) customInstructionsInput.classList.add('hidden');
            uploadButton.classList.add('hidden'); // Hide main upload button
            
            selectedFilesStore = []; 
            renderSelectedFilesPreview();
            // customInstructionsInput.value = ''; // Optionally clear
        } else {
            filesInput.classList.remove('hidden');
            if (customInstructionsInput) customInstructionsInput.classList.remove('hidden');
            uploadButton.classList.remove('hidden'); // Keep upload button visible for retry
        }

        // Reset upload button state if it's still visible
        if (!uploadButton.classList.contains('hidden')) {
            uploadButton.disabled = false;
            uploadButton.textContent = 'Upload Files & Instructions';
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
                if (customInstructionsInput) customInstructionsInput.classList.remove('hidden'); // Show instructions input
                uploadButton.classList.remove('hidden');
                uploadButton.textContent = 'Upload Files & Instructions'; // Updated button text
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
            processStatus.textContent = 'Processing request timed out or a network issue occurred. The process might still be running on the server. Please check RAG status again in a few moments.';
            processStatus.style.color = 'orange'; // Changed to orange to indicate uncertainty
            console.error("Processing error/timeout:", error);
            // Re-enable button for user to acknowledge message or retry (if applicable for the error)
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

    chatDefaultRagButton.addEventListener('click', () => {
        uploadSection.classList.remove('active-section');
        uploadSection.classList.add('hidden');
        chatSection.classList.add('active-section');
        chatSection.classList.remove('hidden');

        chatTitle.textContent = `Chat with Default RAG Agent`;
        if (chatTargetIsCustom || streamWithSteps || !currentSessionId) { // Reset session if mode changes
            currentSessionId = `chat_default_${currentUser}_${Date.now()}`;
        }
        chatTargetIsCustom = false;
        streamWithSteps = false; // Ensure normal chat
        clearChat();
        appendChatMessage('system', 'Interacting with Default RAG (standard mode).');
    });

    chatDefaultRagSseButton.addEventListener('click', () => {
        chatTargetIsCustom = false;
        streamWithSteps = true; // Enable SSE streaming with steps
        currentSessionId = generateSessionId(); // Generate new session ID for new chat
        clearChat();
        chatTitle.textContent = 'Chat with Default RAG (Showing Steps)';
        uploadSection.classList.remove('active-section');
        uploadSection.classList.add('hidden');
        chatSection.classList.add('active-section');
        chatSection.classList.remove('hidden');
    });

    if (chatCustomRagButton) {
        chatCustomRagButton.addEventListener('click', () => {
            if (!userHasCustomRag) {
                alert("Custom RAG not available. Please upload documents first.");
                return;
            }
            chatTargetIsCustom = true;
            streamWithSteps = false; // Disable SSE streaming with steps for this button
            currentSessionId = generateSessionId(); // Generate new session ID for new chat
            clearChat();
            chatTitle.textContent = `Chat with ${currentUser}'s RAG`;
            uploadSection.classList.remove('active-section');
            uploadSection.classList.add('hidden');
            chatSection.classList.add('active-section');
            chatSection.classList.remove('hidden');
        });
    }

    // Event listener for the new custom RAG SSE button
    if (chatCustomRagSseButton) {
        chatCustomRagSseButton.addEventListener('click', () => {
            if (!userHasCustomRag) {
                alert("Custom RAG not available. Please upload documents first.");
                return;
            }
            chatTargetIsCustom = true;
            streamWithSteps = true; // Enable SSE streaming with steps
            currentSessionId = generateSessionId(); // Generate new session ID for new chat
            clearChat();
            chatTitle.textContent = `Chat with ${currentUser}'s RAG (Showing Steps)`;
            uploadSection.classList.remove('active-section');
            uploadSection.classList.add('hidden');
            chatSection.classList.add('active-section');
            chatSection.classList.remove('hidden');
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
        if (customInstructionsInput) customInstructionsInput.classList.remove('hidden'); // Show instructions input
        uploadButton.classList.remove('hidden');
        uploadButton.textContent = 'Upload Files & Instructions'; // Updated button text
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

        // Determine endpoint based on streamWithSteps and chatTargetIsCustom
        let endpoint = '/run'; // Default
        if (streamWithSteps) {
            endpoint = chatTargetIsCustom && currentUser ? `/run_sse/${currentUser}` : '/run_sse';
        } else {
            endpoint = chatTargetIsCustom && currentUser ? `/run/${currentUser}` : '/run';
        }
        
        // Ensure session ID is generated if somehow missed
        if (!currentSessionId) {
            if (chatTargetIsCustom && currentUser) {
                currentSessionId = `chat_${currentUser}_${Date.now()}`;
            } else if (streamWithSteps) {
                currentSessionId = `chat_default_sse_${currentUser}_${Date.now()}`;
            } else {
                currentSessionId = `chat_default_${currentUser}_${Date.now()}`;
            }
            console.warn("Session ID was not set, generated new one:", currentSessionId);
        }

        if (streamWithSteps) {
            await handleSseStream(endpoint, message);
        } else {
            await handleStandardChat(endpoint, message);
        }
    });

    async function handleStandardChat(endpoint, promptText) {
        const thinkingMessage = appendChatMessage('agent', 'Thinking...', true);
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Basic ' + btoa(currentUser + ":" + currentPassword)
                },
                body: JSON.stringify({
                    "prompt": promptText,
                    "user_id": currentUser,
                    "session_id": currentSessionId
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
            console.error("Chat error (standard):", error);
        } finally {
            chatInput.disabled = false;
            chatSubmitButton.disabled = false;
            chatInput.focus();
        }
    }

    async function handleSseStream(endpoint, promptText) {
        let agentMessageElement = null; // To update the same message element for streaming
        let accumulatedText = "";

        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Basic ' + btoa(currentUser + ":" + currentPassword)
                },
                body: JSON.stringify({
                    prompt: promptText,
                    user_id: currentUser,
                    session_id: currentSessionId,
                    stream_events: true // Explicitly request detailed events if backend supports
                })
            });

            if (!response.ok) {
                const errorData = await response.json().catch(() => ({ detail: response.statusText }));
                appendChatMessage('agent', `Error starting stream: ${errorData.detail || 'Failed to connect'}`);
                chatStatus.textContent = `Stream error: ${errorData.detail || response.statusText}`;
                chatStatus.style.color = 'red';
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    if (agentMessageElement && accumulatedText.trim() === '') {
                        // If stream ended and no text was ever added, remove the "Agent is thinking..."
                        agentMessageElement.remove();
                    } else if (agentMessageElement) {
                        // Finalize the message - remove 'thinking' class if it was added
                        agentMessageElement.classList.remove('thinking');
                    }
                    appendChatMessage('system', 'Stream ended.');
                    break;
                }
                buffer += decoder.decode(value, { stream: true });

                let eolIndex;
                while ((eolIndex = buffer.indexOf('\n\n')) >= 0) { // SSE messages are separated by double newlines
                    const message = buffer.slice(0, eolIndex).trim();
                    buffer = buffer.slice(eolIndex + 2);

                    if (message.startsWith('data: ')) {
                        const jsonData = message.substring(5);
                        try {
                            const eventData = JSON.parse(jsonData);
                            
                            // Remove initial "Thinking..." if this is the first actual content
                            if (agentMessageElement && agentMessageElement.classList.contains('thinking') && eventData.content?.parts?.[0]?.text) {
                                agentMessageElement.remove();
                                agentMessageElement = null; 
                                accumulatedText = "";
                            }

                            if (eventData.event === 'agent_request' && eventData.data?.message) {
                                appendChatMessage('system', `Agent Request: ${eventData.data.message}`);
                            } else if (eventData.event === 'tool_code' && eventData.data?.tool_name) {
                                appendChatMessage('system', `Using Tool: ${eventData.data.tool_name}`);
                                if(eventData.data.tool_input) {
                                    const inputStr = JSON.stringify(eventData.data.tool_input, null, 2);
                                    appendChatMessage('system', `Tool Input: <pre>${inputStr.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</pre>`, false, 'tool-input-message');
                                }
                            } else if (eventData.event === 'tool_response' && eventData.data?.tool_name) {
                                appendChatMessage('system', `Tool Response from ${eventData.data.tool_name} received.`);
                                 if(eventData.data.tool_output) {
                                    const outputStr = typeof eventData.data.tool_output === 'string' ? eventData.data.tool_output : JSON.stringify(eventData.data.tool_output, null, 2);
                                    appendChatMessage('system', `Tool Output: <pre>${outputStr.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</pre>`, false, 'tool-output-message');
                                }
                            } else if (eventData.event === 'agent_response_start') {
                                // This might be where you initialize the agent's message bubble
                                if (!agentMessageElement) {
                                    agentMessageElement = appendChatMessage('agent', '...', true); // Start with a placeholder
                                }
                            } else if (eventData.content && eventData.content.parts && eventData.content.parts[0].text) {
                                const textPart = eventData.content.parts[0].text;
                                accumulatedText += textPart;
                                if (!agentMessageElement) {
                                    agentMessageElement = appendChatMessage('agent', accumulatedText, !eventData.is_final_response);
                                } else {
                                    agentMessageElement.innerHTML = `<strong>Agent:</strong> ${accumulatedText.replace(/</g, "&lt;").replace(/>/g, "&gt;")}`;
                                    if (!eventData.is_final_response) {
                                        agentMessageElement.classList.add('thinking'); // Keep it looking like it's typing
                                    } else {
                                        agentMessageElement.classList.remove('thinking');
                                    }
                                }
                            } else if (eventData.is_final_response) {
                                if (agentMessageElement) {
                                    agentMessageElement.classList.remove('thinking');
                                }
                                // If there was no content part but it's final, ensure any "Thinking" is removed or updated.
                                if (!accumulatedText && agentMessageElement) {
                                     agentMessageElement.innerHTML = `<strong>Agent:</strong> (No textual response)`;
                                }
                            } else if (eventData.event === 'error') {
                                appendChatMessage('system', `Stream Error: ${eventData.data?.message || 'Unknown error'}`);
                            } else if (eventData.event) { // Catch other named events
                                appendChatMessage('system', `Event: ${eventData.event} - ${JSON.stringify(eventData.data || {})}`);
                            }


                        } catch (e) {
                            console.error("Error parsing SSE event data:", e, jsonData);
                            appendChatMessage('system', `Error parsing stream data: ${jsonData.substring(0,100)}...`);
                        }
                    }
                }
            }
        } catch (error) {
            console.error("SSE Chat error:", error);
            appendChatMessage('agent', 'Error: Could not connect to the streaming agent.');
            chatStatus.textContent = 'Stream error: Network issue or server down.';
            chatStatus.style.color = 'red';
            if (agentMessageElement) agentMessageElement.classList.remove('thinking');
        } finally {
            chatInput.disabled = false;
            chatSubmitButton.disabled = false;
            chatInput.focus();
        }
    }

    function appendChatMessage(sender, text, isThinking = false, customClass = null) {
        const messageElement = document.createElement('div');
        messageElement.classList.add('message');
        messageElement.classList.add(sender === 'user' ? 'user-message' : (sender === 'system' ? 'system-message' : 'agent-message'));
        if (customClass) {
            messageElement.classList.add(customClass);
        }

        const senderDisplay = sender.charAt(0).toUpperCase() + sender.slice(1);

        const strongSender = document.createElement('strong');
        strongSender.textContent = senderDisplay + ': ';
        messageElement.appendChild(strongSender);

        const contentSpan = document.createElement('span');
        contentSpan.classList.add('message-content'); // Added class for styling

        if (isThinking && sender === 'agent') {
            messageElement.classList.add('thinking');
            contentSpan.textContent = text; // Thinking message is plain text
        } else if (sender === 'agent') {
            contentSpan.innerHTML = markdownToHtml(text);
        } else if ((sender === 'system' || customClass === 'tool-input-message' || customClass === 'tool-output-message') && text.includes('<pre>')) {
            // For system messages with <pre> (like tool inputs/outputs), trust the HTML
            contentSpan.innerHTML = text;
        } else { // User messages or simple system messages without pre-formatted HTML
            contentSpan.textContent = text; // Display as plain text, browser will escape
        }
        messageElement.appendChild(contentSpan);

        chatMessages.appendChild(messageElement);
        chatMessages.scrollTop = chatMessages.scrollHeight;
        return messageElement;
    }

    // --- Initial Setup ---
    updateUIState();
    renderSelectedFilesPreview();
});
