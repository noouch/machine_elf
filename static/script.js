document.addEventListener('DOMContentLoaded', function() {
    // DOM Elements
    const disclaimerModal = document.getElementById('disclaimer-modal');
    const acceptDisclaimerBtn = document.getElementById('accept-disclaimer');
    const therapistImage = document.getElementById('therapist-image');
    const chatHistory = document.getElementById('chat-history');
    const userInput = document.getElementById('user-input');
    const sendButton = document.getElementById('send-button');
    const feedbackSection = document.getElementById('feedback-section');
    const feedbackButtons = document.querySelectorAll('.feedback-btn');
    const thankYouSection = document.getElementById('thank-you-section');
    const inputSection = document.getElementById('input-section');
    
    // Session variables
    let sessionData = null;
    let therapistNumber = 1; // Default therapist number
    
    // Check if disclaimer has been accepted
    if (!localStorage.getItem('elfTherapistDisclaimerAccepted')) {
        disclaimerModal.style.display = 'flex';
    }
    
    // Accept disclaimer
    acceptDisclaimerBtn.addEventListener('click', function() {
        localStorage.setItem('elfTherapistDisclaimerAccepted', 'true');
        disclaimerModal.style.display = 'none';
    });
    
    // Initialize session
    initializeSession();
    
    // Send message when button is clicked
    sendButton.addEventListener('click', sendMessage);
    
    // Send message when Enter is pressed
    userInput.addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            sendMessage();
        }
    });
    
    // Handle feedback buttons
    feedbackButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Hide feedback section and show thank you message
            feedbackSection.classList.add('hidden');
            thankYouSection.classList.remove('hidden');
            
            // Change therapist image to "gone" state
            therapistImage.src = `/static/images/therapist_${therapistNumber}_gone.webp`;
        });
    });
    
    // Initialize session with server
    async function initializeSession() {
        try {
            const response = await fetch('/session');
            if (response.ok) {
                sessionData = await response.json();
                therapistNumber = sessionData.therapist_number;
            } else {
                console.error('Failed to initialize session');
            }
        } catch (error) {
            console.error('Error initializing session:', error);
        }
    }
    
    // Send message to server
    async function sendMessage() {
        const message = userInput.value.trim();
        if (!message) return;
        
        // Add user message to chat history
        addMessageToChat(message, 'user');
        
        // Clear input and disable it while waiting for response
        userInput.value = '';
        userInput.disabled = true;
        sendButton.disabled = true;
        
        try {
            // Create a new message div for the assistant response
            const assistantMessageDiv = document.createElement('div');
            assistantMessageDiv.classList.add('message', 'assistant-message');
            chatHistory.appendChild(assistantMessageDiv);
            
            // Send message to server with streaming
            const response = await fetch('/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ message: message })
            });
            
            if (response.ok) {
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let assistantMessage = '';
                let keywords = [];
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    // Decode the chunk
                    const chunk = decoder.decode(value, { stream: true });
                    
                    // Check if this chunk contains keywords
                    if (chunk.includes('<keywords>')) {
                        // Extract keywords from the special marker
                        const keywordsStart = chunk.indexOf('<keywords>') + 10;
                        const keywordsEnd = chunk.indexOf('</keywords>');
                        if (keywordsStart > 9 && keywordsEnd > keywordsStart) {
                            const keywordsStr = chunk.substring(keywordsStart, keywordsEnd);
                            try {
                                keywords = JSON.parse(keywordsStr);
                            } catch (e) {
                                console.error('Error parsing keywords:', e);
                            }
                        }
                    } else {
                        // Add the chunk to the message
                        assistantMessage += chunk;
                        
                        // Update the message div with the new content
                        assistantMessageDiv.textContent = assistantMessage;
                        
                        // Scroll to bottom
                        chatHistory.scrollTop = chatHistory.scrollHeight;
                    }
                }
                
                // Handle special keywords after streaming is complete
                if (keywords.length > 0) {
                    handleSpecialKeywords(keywords);
                }
            } else {
                addMessageToChat('Sorry, I encountered an error. Please try again.', 'assistant');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            addMessageToChat('Sorry, I encountered an error. Please try again.', 'assistant');
        } finally {
            // Re-enable input
            userInput.disabled = false;
            sendButton.disabled = false;
            userInput.focus();
        }
    }
    
    // Add message to chat history
    function addMessageToChat(content, sender) {
        const messageDiv = document.createElement('div');
        messageDiv.classList.add('message');
        messageDiv.classList.add(sender + '-message');
        messageDiv.textContent = content;
        chatHistory.appendChild(messageDiv);
        
        // Scroll to bottom
        chatHistory.scrollTop = chatHistory.scrollHeight;
    }
    
    // Handle special keywords from server
    function handleSpecialKeywords(keywords) {
        keywords.forEach(keyword => {
            switch (keyword) {
                case 'END_CHAT':
                    // Hide input section and show feedback section
                    inputSection.classList.add('hidden');
                    feedbackSection.classList.remove('hidden');
                    break;
                case 'EMOTE_IDLE':
                    therapistImage.src = `/static/images/therapist_${therapistNumber}_idle.webp`;
                    break;
                case 'EMOTE_CONFUSED':
                    therapistImage.src = `/static/images/therapist_${therapistNumber}_confused.webp`;
                    break;
                case 'EMOTE_THINKING':
                    therapistImage.src = `/static/images/therapist_${therapistNumber}_thinking.webp`;
                    break;
                case 'EMOTE_CALM':
                    therapistImage.src = `/static/images/therapist_${therapistNumber}_calm.webp`;
                    break;
            }
        });
    }
});
