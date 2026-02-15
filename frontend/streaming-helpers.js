// Add these helper functions for streaming at the end of app.js

// ===== Streaming Message Helpers =====
function addStreamingMessage(role, content) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message message-${role}`;
    messageDiv.id = `streaming-${Date.now()}`;

    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    contentDiv.innerHTML = formatMessageContent(content) + '<span class="cursor">▌</span>';

    messageDiv.appendChild(contentDiv);
    elements.chatMessages.appendChild(messageDiv);
    scrollToBottom();

    return messageDiv.id;
}

function updateStreamingMessage(messageId, content) {
    const messageDiv = document.getElementById(messageId);
    if (messageDiv) {
        const contentDiv = messageDiv.querySelector('.message-content');
        contentDiv.innerHTML = formatMessageContent(content) + '<span class="cursor">▌</span>';
        scrollToBottom();
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
        const citationsDiv = createCitationsElement(citations);
        contentDiv.appendChild(citationsDiv);
    }

    // Add metadata
    if (metadata && metadata.queryType) {
        const metaDiv = document.createElement('div');
        metaDiv.className = 'message-meta';

        const badges = [];
        badges.push(`<span>Type: ${metadata.queryType}</span>`);
        if (metadata.usedWebSearch) {
            badges.push(`<span>🌐 Web Search</span>`);
        }

        metaDiv.innerHTML = badges.join(' • ');
        messageDiv.appendChild(metaDiv);
    }
}
