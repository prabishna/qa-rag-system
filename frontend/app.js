
// ===== Configuration =====
const API_BASE_URL = 'http://localhost:8000';

// ===== State =====
let conversationId = null;
let isProcessing = false;
let uploadedFiles = [];
let conversationHistory = [];

// ===== DOM Elements =====
const elements = {
    // Sidebar
    newChatBtn: document.getElementById('newChatBtn'),
    uploadArea: document.getElementById('uploadArea'),
    fileInput: document.getElementById('fileInput'),
    fileList: document.getElementById('fileList'),
    historyList: document.getElementById('historyList'),
    uploadProgress: document.getElementById('uploadProgress'),
    progressFill: document.getElementById('progressFill'),
    uploadStatus: document.getElementById('uploadStatus'),
    statusIndicator: document.getElementById('statusIndicator'),

    // Sidebar Toggle
    sidebar: document.querySelector('.sidebar'),
    sidebarToggle: document.getElementById('sidebarToggle'),
    historyToggle: document.getElementById('historyToggle'),

    // Main Area
    headerTitle: document.querySelector('.conversation-title'),
    conversationIdDisplay: document.getElementById('conversationId'),
    chatMessages: document.getElementById('chatMessages'),
    chatInput: document.getElementById('chatInput'),
    sendBtn: document.getElementById('sendBtn'),
};

// ===== Initialization =====
document.addEventListener('DOMContentLoaded', () => {
    initializeApp();
    setupEventListeners();
});

async function initializeApp() {
    await checkServerStatus();
    await fetchDocuments();
    await fetchHistory();
}

// ===== Server Status =====
async function checkServerStatus() {
    try {
        const response = await fetch(`${API_BASE_URL}/api/health`);
        const data = await response.json();
        updateStatus('online', 'Connected');
    } catch (error) {
        updateStatus('offline', 'Disconnected');
        console.error('Server check failed:', error);
    }
}

function updateStatus(status, text) {
    if (!elements.statusIndicator) return;
    const dot = elements.statusIndicator.querySelector('.status-dot');
    const label = elements.statusIndicator.querySelector('.status-text');

    if (dot) dot.className = `status-dot ${status}`;
    if (label) label.textContent = text;
}

// ===== Event Listeners =====
function setupEventListeners() {
    // Sidebar Actions
    elements.newChatBtn.addEventListener('click', startNewConversation);

    if (elements.sidebarToggle) {
        elements.sidebarToggle.addEventListener('click', () => {
            elements.sidebar.classList.toggle('collapsed');
        });
    }
    if (elements.historyToggle) {
        elements.historyToggle.addEventListener('click', () => {
            const icon = elements.historyToggle.querySelector('i');
            icon.classList.add('fa-spin');
            fetchHistory().then(() => setTimeout(() => icon.classList.remove('fa-spin'), 500));
        });
    }

    // Upload
    elements.uploadArea.addEventListener('click', () => elements.fileInput.click());
    elements.fileInput.addEventListener('change', handleFileSelect);

    // Drag & Drop
    elements.uploadArea.addEventListener('dragover', (e) => {
        e.preventDefault();
        elements.uploadArea.classList.add('drag-over');
    });
    elements.uploadArea.addEventListener('dragleave', () => {
        elements.uploadArea.classList.remove('drag-over');
    });
    elements.uploadArea.addEventListener('drop', handleDrop);

    // Chat
    elements.sendBtn.addEventListener('click', handleSendMessage);
    elements.chatInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSendMessage();
        }
    });

    // Auto-resize input
    elements.chatInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = (this.scrollHeight) + 'px';
        elements.sendBtn.disabled = this.value.trim() === '';
    });
}

// ===== History Management =====
async function fetchHistory() {
    try {
        const response = await fetch(`${API_BASE_URL}/conversations`);
        const data = await response.json();
        conversationHistory = data.conversations || [];
        renderHistoryList();

        // Update header title if we're in an active conversation
        if (conversationId) {
            const currentConv = conversationHistory.find(c => c.id === conversationId);
            if (currentConv && currentConv.title && elements.headerTitle) {
                elements.headerTitle.textContent = currentConv.title;
            }
        }
    } catch (error) {
        console.error('Failed to fetch history:', error);
    }
}

function renderHistoryList() {
    if (!elements.historyList) return;
    elements.historyList.innerHTML = '';

    if (conversationHistory.length === 0) {
        elements.historyList.innerHTML = '<li class="file-item" style="justify-content:center; color:var(--text-light); border:none;">No history</li>';
        return;
    }

    // Reverse logic if needed, but backend sorts by DESC usually.
    // If backend returns objects, use them.
    conversationHistory.forEach(conv => {
        const li = document.createElement('li');
        li.className = 'file-item';
        li.style.cursor = 'pointer';

        let id, title;
        if (typeof conv === 'object') {
            id = conv.id;
            title = conv.title || `Chat ${id.substring(0, 6)}...`;
        } else {
            id = conv;
            title = `Chat ${id.substring(0, 6)}...`;
        }

        li.innerHTML = `
            <div class="file-info">
                <i class="fa-regular fa-comments file-icon"></i>
                <span class="file-name" title="${title}">${title}</span>
            </div>
            <div class="file-actions">
                <button class="action-btn delete-btn" title="Delete conversation">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </div>
        `;

        // Add click event for loading conversation
        li.onclick = (e) => {
            // Don't load if clicking actions
            if (e.target.closest('.file-actions')) return;
            loadConversation(id, title);
        };

        // Add click event for delete button
        const deleteBtn = li.querySelector('.delete-btn');
        if (deleteBtn) {
            deleteBtn.onclick = (e) => {
                e.stopPropagation();
                if (confirm('Are you sure you want to delete this conversation?')) {
                    deleteConversation(id);
                }
            };
        }

        elements.historyList.appendChild(li);
    });
}

async function deleteConversation(id) {
    if (!id) return;

    try {
        const response = await fetch(`${API_BASE_URL}/conversations/${id}`, {
            method: 'DELETE'
        });

        if (response.ok) {
            // Refresh history
            fetchHistory();

            // If deleted conversation is currently open, clear it
            if (conversationId === id) {
                conversationId = null;
                elements.conversationIdDisplay.textContent = '';
                if (elements.headerTitle) elements.headerTitle.textContent = 'New Conversation';
                elements.chatMessages.innerHTML = `
                    <div class="welcome-screen">
                        <div class="welcome-icon"><i class="fa-solid fa-robot"></i></div>
                        <div class="welcome-title">SourceMind AI</div>
                        <div class="welcome-subtitle">Select a conversation or start a new one</div>
                    </div>
                `;
            }
        } else {
            console.error('Failed to delete conversation');
            alert('Failed to delete conversation');
        }
    } catch (error) {
        console.error('Error deleting conversation:', error);
        alert('Error deleting conversation');
    }
}

async function loadConversation(id, title) {
    console.log('[DEBUG] Loading conversation:', id, title);
    conversationId = id;
    elements.conversationIdDisplay.textContent = id;
    if (elements.headerTitle) elements.headerTitle.textContent = title || 'Conversation';

    // Show loading state
    elements.chatMessages.innerHTML = `
        <div class="welcome-screen">
            <div class="welcome-icon"><i class="fa-solid fa-spinner fa-spin"></i></div>
            <div class="welcome-title">Loading Conversation...</div>
            <div class="welcome-subtitle">ID: ${id}</div>
        </div>
    `;

    try {
        // Fetch conversation history from API
        console.log('[DEBUG] Fetching from:', `${API_BASE_URL}/conversations/${id}`);
        const response = await fetch(`${API_BASE_URL}/conversations/${id}`);
        console.log('[DEBUG] Response status:', response.status, response.ok);

        if (!response.ok) {
            throw new Error('Failed to load conversation');
        }

        const data = await response.json();
        console.log('[DEBUG] Received data:', data);
        const history = data.history || [];
        console.log('[DEBUG] History length:', history.length);
        console.log('[DEBUG] History:', history);

        // Clear chat area
        elements.chatMessages.innerHTML = '';

        // Display conversation messages
        if (history.length === 0) {
            console.log('[DEBUG] No messages in history');
            elements.chatMessages.innerHTML = `
                <div class="welcome-screen">
                    <div class="welcome-icon"><i class="fa-solid fa-clock-rotate-left"></i></div>
                    <div class="welcome-title">Conversation Loaded</div>
                    <div class="welcome-subtitle">No messages yet</div>
                </div>
            `;
        } else {
            console.log('[DEBUG] Rendering messages...');
            // Render each message in the conversation
            history.forEach((msg, index) => {
                console.log(`[DEBUG] Message ${index}:`, msg);
                if (msg.type === 'human' || msg.type === 'user') {
                    addMessage('user', msg.content);
                } else if (msg.type === 'ai' || msg.type === 'assistant') {
                    // Check if there are citations in the message
                    const citations = msg.citations || [];
                    addMessage('assistant', msg.content, citations);
                }
            });
            console.log('[DEBUG] Finished rendering messages');
        }

        // Close sidebar on mobile (optional logic)
        if (window.innerWidth < 768 && elements.sidebar) {
            elements.sidebar.classList.add('collapsed');
        }

    } catch (error) {
        console.error('[DEBUG] Error loading conversation:', error);
        elements.chatMessages.innerHTML = `
            <div class="welcome-screen">
                <div class="welcome-icon"><i class="fa-solid fa-circle-exclamation" style="color: var(--error-color);"></i></div>
                <div class="welcome-title">Error Loading Conversation</div>
                <div class="welcome-subtitle">Please try again</div>
            </div>
        `;
    }
}

// ===== Document Management =====
async function fetchDocuments() {
    try {
        const response = await fetch(`${API_BASE_URL}/documents`);
        const data = await response.json();

        uploadedFiles = data.documents || [];
        renderFileList();
    } catch (error) {
        console.error('Failed to fetch documents:', error);
    }
}

function renderFileList() {
    elements.fileList.innerHTML = '';

    if (uploadedFiles.length === 0) {
        elements.fileList.innerHTML = '<li class="file-item" style="justify-content:center; color:var(--text-light); border:none;">No files</li>';
        return;
    }

    uploadedFiles.forEach(file => {
        const li = document.createElement('li');
        li.className = 'file-item';

        let iconClass = 'fa-file';
        if (file.type === 'PDF') iconClass = 'fa-file-pdf';
        if (file.type === 'TXT') iconClass = 'fa-file-lines';

        li.innerHTML = `
            <i class="fa-solid ${iconClass} file-icon"></i>
            <span class="file-name" title="${file.name}">${file.name}</span>
            <span class="file-size">${formatSize(file.size)}</span>
            <div class="file-actions">
                <button class="file-action-btn preview-btn" title="Preview">
                    <i class="fa-solid fa-eye"></i>
                </button>
                <button class="file-action-btn delete-btn" title="Delete">
                    <i class="fa-solid fa-trash"></i>
                </button>
            </div>
        `;

        // Add event listeners instead of inline onclick
        const previewBtn = li.querySelector('.preview-btn');
        const deleteBtn = li.querySelector('.delete-btn');

        previewBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            previewFile(file.id);
        });

        deleteBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            deleteFile(file.id, file.name);
        });

        elements.fileList.appendChild(li);
    });
}

function formatSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Delete file function
async function deleteFile(docId, filename) {
    // Confirm deletion
    if (!confirm(`Are you sure you want to delete "${filename}"?\n\nThis will remove the document from the database and vector store.`)) {
        return;
    }

    try {
        const response = await fetch(`${API_BASE_URL}/documents/${docId}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (response.ok && result.status === 'success') {
            // Show success message
            console.log('Document deleted successfully:', result.message);

            // Refresh the file list
            await fetchDocuments();

            // Reset file input to allow re-uploading the same file
            if (elements.fileInput) {
                elements.fileInput.value = '';
            }
        } else {
            throw new Error(result.message || 'Failed to delete document');
        }
    } catch (error) {
        console.error('Delete failed:', error);
        alert(`Failed to delete document: ${error.message}`);
    }
}

// Preview file function
function previewFile(docId) {
    // Open preview in a new tab
    const previewUrl = `${API_BASE_URL}/documents/${docId}/preview`;
    window.open(previewUrl, '_blank');
}

// ===== File Upload =====
function handleDrop(e) {
    e.preventDefault();
    elements.uploadArea.classList.remove('drag-over');
    if (e.dataTransfer.files.length) uploadFile(e.dataTransfer.files[0]);
}

function handleFileSelect(e) {
    if (e.target.files.length) uploadFile(e.target.files[0]);
}

async function uploadFile(file) {
    if (file.size > 10 * 1024 * 1024) {
        alert("File too large (>10MB). Please use a smaller file.");
        return;
    }

    // Show progress and status
    elements.uploadProgress.style.display = 'block';
    if (elements.uploadStatus) {
        elements.uploadStatus.style.display = 'block';
        elements.uploadStatus.innerHTML = '<i class="fa-solid fa-cloud-arrow-up"></i> Uploading...';
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        let width = 0;
        // Upload phase simulation (fast)
        const interval = setInterval(() => {
            if (width >= 90) {
                clearInterval(interval);
                // Processing phase
                if (elements.uploadStatus) {
                    elements.uploadStatus.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Processing... (this may take a moment)';
                }
            } else {
                width += 10;
                elements.progressFill.style.width = width + '%';
            }
        }, 200);

        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });

        clearInterval(interval);
        elements.progressFill.style.width = '100%';

        const data = await response.json();

        if (response.ok) {
            // Success
            if (elements.uploadStatus) {
                elements.uploadStatus.innerHTML = '<i class="fa-solid fa-check" style="color:var(--success-color)"></i> Done!';
            }
            setTimeout(() => {
                elements.uploadProgress.style.display = 'none';
                if (elements.uploadStatus) elements.uploadStatus.style.display = 'none';
                elements.progressFill.style.width = '0%';

                // Refresh document list (from DB now)
                fetchDocuments();
            }, 1000);
        } else {
            throw new Error(data.message || 'Upload failed');
        }
    } catch (error) {
        console.error('Upload error:', error);
        alert('Upload failed: ' + error.message);
        elements.uploadProgress.style.display = 'none';
        if (elements.uploadStatus) {
            elements.uploadStatus.innerHTML = `<i class="fa-solid fa-circle-exclamation" style="color:var(--error-color)"></i> Error during processing`;
        }
    }
}

// ===== Conversation Logic =====
function startNewConversation() {
    conversationId = null;
    if (elements.headerTitle) elements.headerTitle.textContent = 'New Chat';

    elements.chatMessages.innerHTML = `
        <div class="welcome-screen">
            <div class="welcome-icon"><i class="fa-solid fa-layer-group"></i></div>
            <div class="welcome-title">SourceMind AI</div>
            <div class="welcome-subtitle">Secure Knowledge Retrieval System</div>
        </div>
    `;
    elements.conversationIdDisplay.textContent = 'New Conversation';
    elements.chatInput.value = '';
    elements.chatInput.focus();
}


// ===== Streaming Logic =====

async function handleSendMessage() {
    const text = elements.chatInput.value.trim();
    if (!text || isProcessing) return;

    isProcessing = true;
    elements.sendBtn.disabled = true;
    elements.chatInput.value = '';
    elements.chatInput.style.height = 'auto';

    // Remove welcome screen
    const welcome = elements.chatMessages.querySelector('.welcome-screen');
    if (welcome) welcome.remove();

    // Add User Message
    addMessage('user', text);

    // Create a placeholder for the assistant's message
    const messageId = addStreamingMessage('assistant', '');
    let fullAnswer = '';

    // Create status indicator
    const statusId = 'status-' + Date.now();
    const statusDiv = document.createElement('div');
    statusDiv.id = statusId;
    statusDiv.className = 'message-status';
    statusDiv.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Initializing...';
    statusDiv.style.fontSize = '0.8rem';
    statusDiv.style.color = 'var(--text-secondary)';
    statusDiv.style.marginLeft = '1rem';
    statusDiv.style.marginBottom = '0.5rem';
    elements.chatMessages.appendChild(statusDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

    try {
        const response = await fetch(`${API_BASE_URL}/query/stream`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                query: text,
                conversation_id: conversationId
            })
        });

        if (!response.ok) throw new Error('Network response was not ok');

        const reader = response.body.getReader();
        const decoder = new TextDecoder();

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            const chunk = decoder.decode(value);
            const lines = chunk.split('\n\n');

            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const dataStr = line.replace('data: ', '').trim();
                    if (dataStr === '[DONE]') break;

                    try {
                        const event = JSON.parse(dataStr);

                        switch (event.type) {
                            case 'start':
                                if (!conversationId && event.conversation_id) {
                                    conversationId = event.conversation_id;
                                    elements.conversationIdDisplay.textContent = conversationId;
                                    updateHistoryOptimistically(text, conversationId);
                                }
                                break;

                            case 'status':
                                statusDiv.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> ${event.message}`;
                                break;

                            case 'token':
                                fullAnswer += event.content;
                                updateStreamingMessage(messageId, fullAnswer);
                                break;

                            case 'complete':
                                statusDiv.remove();
                                addCitationsToMessage(messageId, event.citations, {
                                    queryType: event.query_type,
                                    usedWebSearch: event.used_web_search
                                });
                                break;

                            case 'error':
                                statusDiv.innerHTML = `<i class="fa-solid fa-triangle-exclamation" style="color:var(--error-color)"></i> Error: ${event.message}`;
                                break;
                        }
                    } catch (e) {
                        console.error('Error parsing SSE event:', e);
                    }
                }
            }
        }

    } catch (error) {
        console.error('Stream error:', error);
        statusDiv.innerHTML = `<i class="fa-solid fa-triangle-exclamation" style="color:var(--error-color)"></i> Network error`;
        addMessage('assistant', 'Sorry, I encountered a network error.');
    } finally {
        isProcessing = false;
        elements.sendBtn.disabled = false;
        elements.chatInput.focus();
    }
}

function updateHistoryOptimistically(text, id) {
    const newTitle = text.length > 30 ? text.substring(0, 30) + '...' : text;
    const newItem = { id: id, title: newTitle };

    // Check if already exists
    if (!conversationHistory.find(c => c.id === id)) {
        conversationHistory.unshift(newItem);
        renderHistoryList();
        setTimeout(fetchHistory, 4000); // Sync with backend later
    }
}

// ===== Streaming Message Helpers =====
function addStreamingMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${role}`;
    messageDiv.id = `streaming-${Date.now()}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    // Initial empty content with cursor
    contentDiv.innerHTML = '<span class="cursor">▌</span>';

    messageDiv.appendChild(contentDiv);
    elements.chatMessages.appendChild(messageDiv);
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;

    return messageDiv.id;
}

function updateStreamingMessage(messageId, content) {
    const messageDiv = document.getElementById(messageId);
    if (messageDiv) {
        const contentDiv = messageDiv.querySelector('.message-content');
        contentDiv.innerHTML = formatContent(content) + '<span class="cursor">▌</span>';
        elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
    }
}

function addCitationsToMessage(messageId, citations, metadata) {
    const messageDiv = document.getElementById(messageId);
    if (!messageDiv) return;

    const contentDiv = messageDiv.querySelector('.message-content');

    // Remove cursor
    const cursor = contentDiv.querySelector('.cursor');
    if (cursor) cursor.remove();

    // Add citations
    if (citations && citations.length > 0) {
        const citationsHtml = `
            <div class="citations">
                <div class="citations-title"><i class="fa-solid fa-book-open"></i> Sources</div>
                <div class="citation-list">
                    ${citations.slice(0, 3).map(cit => {
            const pageInfo = cit.page_number ? ` (Page ${cit.page_number})` : '';
            return `
                            <div class="citation-card" title="${cit.chunk_text || ''}">
                                <div class="citation-doc">${cit.document_name || 'Unknown'}${pageInfo}</div>
                                <div class="citation-preview">${(cit.chunk_text || '').substring(0, 80)}...</div>
                            </div>
                        `;
        }).join('')}
                </div>
            </div>
        `;
        contentDiv.insertAdjacentHTML('beforeend', citationsHtml);
    }

    // Add metadata
    if (metadata) {
        const metaDiv = document.createElement('div');
        metaDiv.className = 'message-meta';
        metaDiv.style.fontSize = '0.75rem';
        metaDiv.style.color = 'var(--text-light)';
        metaDiv.style.marginTop = '0.5rem';
        metaDiv.style.display = 'flex';
        metaDiv.style.gap = '0.5rem';

        const badges = [];
        if (metadata.queryType) badges.push(`<span><i class="fa-solid fa-tag"></i> ${metadata.queryType}</span>`);
        if (metadata.usedWebSearch) badges.push(`<span><i class="fa-solid fa-globe"></i> Web Search</span>`);

        metaDiv.innerHTML = badges.join(' • ');
        messageDiv.appendChild(metaDiv);
    }
}

function addMessage(role, content, citations = []) {
    // Legacy function for non-streaming messages (e.g. history)
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${role}`;

    // Use the streaming helper logic to populate it instantly
    const messageId = `msg-${Date.now()}-${Math.random()}`;
    messageDiv.id = messageId;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = formatContent(content);

    messageDiv.appendChild(contentDiv);
    elements.chatMessages.appendChild(messageDiv);

    if (citations && citations.length > 0) {
        addCitationsToMessage(messageId, citations);
    }

    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
}

function formatContent(text) {
    if (!text) return '';
    // Simple markdown formatting
    return text
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/`([^`]+)`/g, '<code style="background:rgba(0,0,0,0.1); padding:0.2rem; border-radius:4px;">$1</code>')
        .replace(/\n/g, '<br>');
}

