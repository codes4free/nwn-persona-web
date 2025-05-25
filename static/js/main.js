// Initialize the Socket.IO connection
const socket = io({ 
    withCredentials: true, 
    transports: ['polling', 'websocket'],  // Change order to try polling first
    reconnectionAttempts: 10,
    reconnectionDelay: 1000,
    timeout: 5000,  // Reduce timeout to 5 seconds
    forceNew: true,
    upgrade: false,  // Prevent transport upgrades initially
    rememberUpgrade: false
});

// DOM elements
const characterNameElement = document.getElementById('character-name');
const characterDetailsElement = document.getElementById('character-details');
const characterListElement = document.getElementById('character-list');
const chatMessagesElement = document.getElementById('chat-messages');
const responseOptionsElement = document.getElementById('response-options');
const incomingMessageElement = document.getElementById('incoming-message');
const generateResponseButton = document.getElementById('generate-response');
const notificationToast = document.getElementById('notification-toast');
const portugueseTextElement = document.getElementById('portuguese-text');
const translateButton = document.getElementById('translate-button');
const translationResultElement = document.getElementById('translation-result');
const translatedTextElement = document.getElementById('translated-text');
const copyTranslationButton = document.getElementById('copy-translation');
const feedbackSummaryElement = document.getElementById('feedback-summary');
const feedbackProgressElement = document.getElementById('feedback-progress');
const positiveCountElement = document.getElementById('positive-count');
const negativeCountElement = document.getElementById('negative-count');
const totalCountElement = document.getElementById('total-count');

// Bootstrap Toast object
const toast = new bootstrap.Toast(notificationToast);

// Global state
let activeCharacter = null;
let lastPlayerMessage = null;
let lastPlayerName = null;
let selectedMessage = null;
let availableCharacters = [];
let currentMessageData = null;  // Store the current message data for feedback
let chatHistory = [];  // Store chat history for context window

// Maximum number of messages to keep in chat history
const MAX_CHAT_HISTORY = 20;

// Helper function to clean em dashes
function cleanEmDashes(text) {
    return text ? text.replace(/—/g, '-') : text;
}

// Connect to WebSocket
socket.on('connect', () => {
    console.log('Connected to server');
    chatMessagesElement.innerHTML = '<p class="text-center text-success">Connected to server</p>';
    
    // Update connection status indicator
    const statusBadge = document.getElementById('socket-status');
    if (statusBadge) {
        statusBadge.className = 'badge bg-success';
        statusBadge.textContent = 'Connected';
        
        // Show transport info
        const transport = socket.io.engine.transport.name;
        statusBadge.textContent = `Connected (${transport})`;
    }
    
    // Request initial data
    fetchCharacters();
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    chatMessagesElement.innerHTML += '<p class="text-center text-danger">Disconnected from server</p>';
    
    // Update connection status indicator
    const statusBadge = document.getElementById('socket-status');
    if (statusBadge) {
        statusBadge.className = 'badge bg-danger';
        statusBadge.textContent = 'Disconnected';
    }
});

socket.on('connect_error', (error) => {
    console.error('Connection error:', error);
    
    // Update connection status indicator
    const statusBadge = document.getElementById('socket-status');
    if (statusBadge) {
        statusBadge.className = 'badge bg-danger';
        statusBadge.textContent = 'Error: ' + error.message;
    }
});

// Listen for character change
socket.on('character_change', (data) => {
    console.log('[DEBUG] character_change event received:', data);
    if (data.character) {
        activeCharacter = data.character;
        updateCharacterDisplay(data.character);
    }
});

// Listen for new chat messages
socket.on('new_message', (data) => {
    console.log('[DEBUG] new_message event received:', data);
    // Debug diagnostic information
    console.log('%c NEW MESSAGE RECEIVED', 'background: green; color: white; font-size: 16px;');
    console.log('Message data:', data);
    
    // Visual indicators
    document.title = "New message!"; // Change page title to indicate new message
    
    // Determine if this message is for the current user/session
    const currentUser = document.querySelector('.navbar').textContent.trim().replace('Welcome, ', '').replace('Logout', '').trim();
    const isRelevantToUser = !data.client || data.client === currentUser;
    
    console.log('Message client:', data.client, 'Current user:', currentUser, 'Is relevant:', isRelevantToUser);
    
    // Add a global alert for debugging
    let debugAlert = document.createElement('div');
    debugAlert.style.position = 'fixed';
    debugAlert.style.top = '10px';
    debugAlert.style.right = '10px';
    debugAlert.style.padding = '10px';
    debugAlert.style.background = '#ffcc00';
    debugAlert.style.border = '1px solid #cc9900';
    debugAlert.style.zIndex = '9999';
    debugAlert.textContent = 'New message received at ' + new Date().toLocaleTimeString() + 
                            (data.client ? ` (from ${data.client})` : '');
    document.body.appendChild(debugAlert);
    
    // Remove the alert after 5 seconds
    setTimeout(() => {
        debugAlert.remove();
    }, 5000);
    
    // Try to append to chat
    try {
        console.log('Attempting to append message');
        console.log('Chat messages container:', chatMessagesElement);
        console.log('Message content:', data.message);
        
        if (!chatMessagesElement) {
            console.error('Chat messages container is null or undefined!');
            // Try to get it again
            chatMessagesElement = document.getElementById('chat-messages');
            if (!chatMessagesElement) {
                console.error('Failed to find chat-messages element!');
                return;
            }
        }
        
        appendChatMessage(data.message, data.is_own, data.original_message);
        console.log('Message appended to chat');
        
        // Force scroll to bottom
        chatMessagesElement.scrollTop = chatMessagesElement.scrollHeight;
    } catch (error) {
        console.error('Error appending message:', error);
        
        // Fallback direct DOM manipulation
        try {
            console.log('Attempting fallback direct DOM insertion');
            const msgEl = document.createElement('div');
            msgEl.className = 'message message-other';
            msgEl.innerHTML = data.message + '<div class="message-time">' + new Date().toLocaleTimeString() + '</div>';
            
            const chatContainer = document.getElementById('chat-messages');
            if (chatContainer) {
                chatContainer.appendChild(msgEl);
                console.log('Fallback insertion successful');
            } else {
                console.error('Could not find chat-messages container for fallback!');
            }
        } catch (fallbackError) {
            console.error('Even fallback insertion failed:', fallbackError);
        }
    }
});

// Listen for system messages
socket.on('system_message', (data) => {
    console.log('System message:', data);
    // Add system message to chat
    const messageElement = document.createElement('div');
    messageElement.className = 'message system-message';
    messageElement.innerHTML = `<strong>System:</strong> ${data.message}`;
    
    // Add timestamp
    const timestampElement = document.createElement('div');
    timestampElement.className = 'message-time';
    timestampElement.textContent = new Date().toLocaleTimeString();
    messageElement.appendChild(timestampElement);
    
    chatMessagesElement.appendChild(messageElement);
    
    // Auto-scroll
    chatMessagesElement.scrollTop = chatMessagesElement.scrollHeight;
});

// Listen for player messages that may need a response
socket.on('player_message', (data) => {
    console.log('[DEBUG] player_message event received:', data);
    console.log('Player message:', data);
    
    // Get the current user from the navbar
    const currentUser = document.querySelector('.navbar').textContent.trim().replace('Welcome, ', '').replace('Logout', '').trim();
    const isRelevantToUser = !data.client || data.client === currentUser;
    
    console.log('Message client:', data.client, 'Current user:', currentUser, 'Is relevant:', isRelevantToUser);
    
    // Continue processing even if not for current user, as the client might want to respond to any message
    lastPlayerMessage = data.message;
    lastPlayerName = data.player_name;
    incomingMessageElement.textContent = `${data.player_name}: ${data.message}`;
    generateResponseButton.disabled = false;
    
    // Store message data for feedback
    currentMessageData = {
        message: data.message,
        player_name: data.player_name
    };
});

// Listen for AI generated responses
socket.on('ai_reply', (data) => {
    console.log('AI replies:', data);
    if (data.error) {
        responseOptionsElement.innerHTML = `<p class="text-danger">${data.error}</p>`;
        return;
    }
    
    displayResponseOptions(data.responses);
    
    // Show toast notification that responses are ready
    const toastBody = notificationToast.querySelector('.toast-body');
    toastBody.textContent = 'AI responses generated! Choose an option below.';
    toast.show();
    
    // Scroll to responses section
    document.getElementById('ai-responses').scrollIntoView({ behavior: 'smooth' });
});

// Listen for translation results
socket.on('translation_result', (data) => {
    console.log('Translation received:', data);
    if (data.error) {
        translatedTextElement.innerHTML = `<span class="text-danger">${data.error}</span>`;
        translationResultElement.style.display = 'block';
        return;
    }
    
    // Display the translation (clean any em dashes again just to be safe)
    translatedTextElement.innerHTML = cleanEmDashes(data.translated);
    translationResultElement.style.display = 'block';
    
    // Scroll to translation result
    translationResultElement.scrollIntoView({ behavior: 'smooth' });
});

// Listen for feedback results
socket.on('feedback_result', (data) => {
    console.log('Feedback result:', data);
    
    // Show toast notification with feedback result
    const toastBody = notificationToast.querySelector('.toast-body');
    if (data.success) {
        toastBody.textContent = 'Feedback submitted! Thank you for helping improve the character.';
    } else {
        toastBody.textContent = 'Error submitting feedback: ' + (data.error || 'Unknown error');
    }
    toast.show();
});

// Add listener for character activation result
socket.on('activation_result', (data) => {
    console.log('Character activation result:', data);
    
    if (data.error) {
        characterDetailsElement.innerHTML = `<p class="text-danger">${data.error}</p>`;
        
        // Show error notification
        const toastBody = notificationToast.querySelector('.toast-body');
        toastBody.textContent = `Error: ${data.error}`;
        toast.show();
        return;
    }
    
    // Update the active character in the state
    activeCharacter = data.active_character;
    
    // Show success notification
    const toastBody = notificationToast.querySelector('.toast-body');
    toastBody.textContent = `${data.active_character} activated successfully!`;
    toast.show();
});

// UI event listeners
generateResponseButton.addEventListener('click', () => {
    // Check if we have a selected message or fall back to the last player message
    const messageToRespond = selectedMessage || (lastPlayerMessage && lastPlayerName ? {text: lastPlayerMessage, playerName: lastPlayerName} : null);
    
    if (!activeCharacter) {
        // Show a notification if no character is selected
        const toastBody = notificationToast.querySelector('.toast-body');
        toastBody.textContent = 'Please select a character first!';
        toast.show();
        return;
    }
    
    if (!messageToRespond) {
        // Show a notification if no message is selected
        const toastBody = notificationToast.querySelector('.toast-body');
        toastBody.textContent = 'Please select a message to respond to!';
        toast.show();
        return;
    }
    
    // Update message display
    const messageSource = messageToRespond.playerName || lastPlayerName || 'Player';
    const messageText = messageToRespond.text || messageToRespond || lastPlayerMessage || '';
    
    // Update UI to show the message we're responding to
    incomingMessageElement.innerHTML = `<strong>${messageSource}:</strong> ${messageText}`;
    
    // Get conversation context
    const context = buildConversationContext(messageSource);
    
    // Show context indicator if available
    if (context && context.messages && context.messages.length > 0) {
        const contextCount = context.messages.length;
        incomingMessageElement.innerHTML += ` <span class="badge bg-info ms-2" title="${contextCount} messages of context included">+${contextCount} context</span>`;
    }
    
    responseOptionsElement.innerHTML = '<p class="text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div> Generating responses...</p>';
    
    // Log what we're sending
    console.log('Requesting AI response:', {
        character: activeCharacter,
        message: messageText,
        player_name: messageSource,
        context: context
    });
    
    // Send the request with context
    socket.emit('request_ai_reply', {
        character: activeCharacter,
        message: messageText,
        player_name: messageSource,
        context: context
    });
});

// Translation button handler
translateButton.addEventListener('click', () => {
    const portugueseText = portugueseTextElement.value.trim();
    
    if (!activeCharacter) {
        const toastBody = notificationToast.querySelector('.toast-body');
        toastBody.textContent = 'No active character selected!';
        toast.show();
        return;
    }
    
    if (!portugueseText) {
        const toastBody = notificationToast.querySelector('.toast-body');
        toastBody.textContent = 'Please enter text to express!';
        toast.show();
        return;
    }
    
    // Show loading state
    translatedTextElement.innerHTML = '<div class="spinner-border text-primary spinner-border-sm" role="status"><span class="visually-hidden">Loading...</span></div> Creating character expression...';
    translationResultElement.style.display = 'block';
    
    // Send translation request
    socket.emit('translate_message', {
        character: activeCharacter,
        text: portugueseText
    });
});

// Copy translation button handler
copyTranslationButton.addEventListener('click', () => {
    const translatedText = translatedTextElement.innerText;
    // Clean any em dashes before copying
    const cleanedText = cleanEmDashes(translatedText);
    
    navigator.clipboard.writeText(cleanedText)
        .then(() => {
            // Show notification
            const toastBody = notificationToast.querySelector('.toast-body');
            toastBody.textContent = 'Character expression copied to clipboard!';
            toast.show();
        })
        .catch(err => {
            console.error('Failed to copy: ', err);
            const toastBody = notificationToast.querySelector('.toast-body');
            toastBody.textContent = 'Failed to copy to clipboard!';
            toast.show();
        });
});

// Functions
function fetchCharacters() {
    fetch('/api/characters')
        .then(response => response.json())
        .then(data => {
            availableCharacters = data.characters;
            updateCharacterList(data.characters);
            
            if (data.active_character) {
                activeCharacter = data.active_character;
                updateCharacterDisplay(data.active_character);
            }
        })
        .catch(error => console.error('Error fetching characters:', error));
}

function updateCharacterList(characters) {
    console.log('Updating character list with', characters);
    
    // Clear the list first
    characterListElement.innerHTML = '';
    
    // Add a "Create New Character" button at the top
    const createBtn = document.createElement('a');
    createBtn.className = 'list-group-item list-group-item-action d-flex justify-content-between align-items-center character-create-btn';
    createBtn.href = '/create-character';
    createBtn.innerHTML = '<i class="bi bi-plus-circle-fill me-2"></i> Create New Character';
    createBtn.style.backgroundColor = '#212529';
    createBtn.style.color = '#fff';
    createBtn.style.borderColor = '#17a2b8';
    characterListElement.appendChild(createBtn);
    
    // Add a divider after the create button
    const divider = document.createElement('div');
    divider.className = 'list-group-item p-1 bg-secondary opacity-50';
    divider.style.height = '2px';
    characterListElement.appendChild(divider);
    
    // Add the list of characters
    characters.forEach(char => {
        const item = document.createElement('div');
        item.className = 'list-group-item list-group-item-action character-item d-flex justify-content-between align-items-center';
        // Apply active class if this is the active character
        if (char === activeCharacter) {
            item.classList.add('active');
        }
        
        const nameSpan = document.createElement('span');
        nameSpan.textContent = char;
        nameSpan.style.cursor = 'pointer';
        nameSpan.addEventListener('click', () => activateCharacter(char));
        item.appendChild(nameSpan);
        
        const buttonGroup = document.createElement('div');
        buttonGroup.className = 'btn-group btn-group-sm';
        
        const editBtn = document.createElement('a');
        editBtn.className = 'btn btn-outline-primary btn-sm';
        editBtn.href = `/edit-character?name=${encodeURIComponent(char)}`;
        editBtn.innerHTML = '<i class="bi bi-pencil"></i>';
        editBtn.title = 'Edit character';
        buttonGroup.appendChild(editBtn);
        
        item.appendChild(buttonGroup);
        characterListElement.appendChild(item);
    });
}

function activateCharacter(characterName) {
    // First update the UI to show character as selected
    const items = characterListElement.querySelectorAll('.character-item');
    items.forEach(item => {
        const nameText = item.querySelector('span')?.textContent || item.textContent;
        if (nameText === characterName) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
    
    // Set loading state
    characterDetailsElement.innerHTML = '<p class="text-center"><div class="spinner-border spinner-border-sm text-primary" role="status"><span class="visually-hidden">Loading...</span></div> Activating character...</p>';
    
    // Use SocketIO to activate character instead of REST API
    socket.emit('activate_character', {
        character: characterName
    });
    
    // Update the character name in the header
    characterNameElement.textContent = characterName;
    
    // Fetch character details
    fetchCharacterDetails(characterName);
    
    // Fetch feedback summary
    fetchFeedbackSummary(characterName);
}

function updateCharacterDisplay(characterName) {
    characterNameElement.textContent = characterName;
    
    // Update the active item in the character list
    const items = characterListElement.querySelectorAll('.character-item');
    items.forEach(item => {
        const nameText = item.querySelector('span')?.textContent || item.textContent;
        if (nameText === characterName) {
            item.classList.add('active');
        } else {
            item.classList.remove('active');
        }
    });
    
    fetchCharacterDetails(characterName);
    fetchFeedbackSummary(characterName);
}

function fetchCharacterDetails(characterName) {
    fetch(`/api/character/${encodeURIComponent(characterName)}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                characterDetailsElement.innerHTML = `<p class="text-danger">${data.error}</p>`;
                return;
            }
            
            let html = '';
            if (data.title) {
                html += `<p><strong>Title:</strong> ${data.title}</p>`;
            }
            if (data.race) {
                html += `<p><strong>Race:</strong> ${data.race}</p>`;
            }
            if (data.class) {
                html += `<p><strong>Class:</strong> ${data.class}</p>`;
            }
            if (data.alignment) {
                html += `<p><strong>Alignment:</strong> ${data.alignment}</p>`;
            }
            if (data.description) {
                html += `<p><strong>Description:</strong> ${data.description}</p>`;
            }
            
            characterDetailsElement.innerHTML = html;
        })
        .catch(error => console.error('Error fetching character details:', error));
}

function appendChatMessage(message, isSelf, originalMessage) {
    console.log('appendChatMessage called with:', { message, isSelf, originalMessage });
    
    // Get the chat container element (again, to be sure)
    const chatContainer = document.getElementById('chat-messages');
    if (!chatContainer) {
        console.error('Chat container not found!');
        return null;
    }
    
    // Force clear any "waiting for messages" placeholder
    const waitingMsg = chatContainer.querySelector('.text-muted');
    if (waitingMsg) {
        console.log('Clearing waiting message placeholder');
        chatContainer.innerHTML = '';
    }
    
    const wasAtBottom = chatContainer.scrollHeight - chatContainer.clientHeight <= chatContainer.scrollTop + 10;
    
    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = `message ${isSelf ? 'message-self' : 'message-other'}`;
    
    // Set message content - DON'T use textContent as it removes HTML formatting
    messageElement.innerHTML = message;
    
    // Add timestamp
    const timestampElement = document.createElement('div');
    timestampElement.className = 'message-time';
    const timestamp = new Date().toLocaleTimeString();
    timestampElement.textContent = timestamp;
    messageElement.appendChild(timestampElement);
    
    // Add a debug indicator so we can verify the message was actually added
    const debugIndicator = document.createElement('span');
    debugIndicator.style.fontSize = '8px';
    debugIndicator.style.color = '#999';
    debugIndicator.textContent = ' [msg-id:' + Math.floor(Math.random() * 1000) + ']';
    timestampElement.appendChild(debugIndicator);
    
    // Extract name and text content for chat history
    let playerName = isSelf ? activeCharacter : "Player";
    let textContent = originalMessage || message;
    
    // Try to extract player name from HTML content
    const strongMatch = message.match(/<strong>(.*?)<\/strong>/);
    if (strongMatch && strongMatch[1]) {
        playerName = strongMatch[1].replace(':', '');
    }
    
    // Try to extract text content from the message
    if (strongMatch) {
        // Remove the strong tag and get the rest of the message
        textContent = message.replace(/<strong>.*?<\/strong>:?\s*/, '');
    }
    
    // Add to chat history for context
    addToChatHistory({
        speaker: playerName,
        text: textContent,
        isSelf: isSelf,
        timestamp: new Date().toISOString()
    });
    
    // Check for clickable message (player message)
    try {
        // Make all non-self messages clickable, regardless of whether they have originalMessage
        if (!isSelf) {
            messageElement.classList.add('selectable-message');
            messageElement.style.cursor = 'pointer'; // Add pointer cursor to indicate clickability
            
            // Store that data
            const messageData = {
                playerName: playerName,
                text: originalMessage || textContent,
                fullMessage: message
            };
            
            // Make message clickable
            messageElement.addEventListener('click', function() {
                console.log('Message clicked:', messageData);
                
                // Deselect any previously selected message
                document.querySelectorAll('.message.selected').forEach(el => {
                    el.classList.remove('selected');
                });
                
                // Mark this message as selected
                messageElement.classList.add('selected');
                
                // Store the selected message
                selectedMessage = messageData;
                
                // Update the display of the selected message
                incomingMessageElement.innerHTML = `<strong>${playerName}:</strong> ${messageData.text}`;
                
                // Show a "message selected" indicator
                const selectedBadge = document.createElement('span');
                selectedBadge.className = 'badge bg-primary ms-2';
                selectedBadge.textContent = 'Selected';
                incomingMessageElement.appendChild(selectedBadge);
                
                // Add context indicator if available
                const context = buildConversationContext(playerName);
                if (context && context.messages && context.messages.length > 0) {
                    const contextCount = context.messages.length;
                    const contextBadge = document.createElement('span');
                    contextBadge.className = 'badge bg-info ms-2';
                    contextBadge.title = `${contextCount} messages of context will be included`;
                    contextBadge.textContent = `+${contextCount} context`;
                    incomingMessageElement.appendChild(contextBadge);
                }
                
                // Clear any previous responses when selecting a new message
                responseOptionsElement.innerHTML = '<p class="text-center text-muted">Click "Generate Response" to create AI replies for this message</p>';
                
                // Enable the generate button
                generateResponseButton.disabled = false;
            });
        }
    } catch (error) {
        console.error('Error setting up clickable message:', error);
    }
    
    // Append the message
    chatContainer.appendChild(messageElement);
    console.log('Message element added to DOM', messageElement);
    
    // Force auto-scroll
    chatContainer.scrollTop = chatContainer.scrollHeight;
    
    // Return the element for debugging
    return messageElement;
}

function displayResponseOptions(responses) {
    responseOptionsElement.innerHTML = '';
    
    if (!responses || responses.length === 0) {
        responseOptionsElement.innerHTML = '<p class="text-center text-muted">No responses generated</p>';
        return;
    }
    
    // Add a header showing what message we're responding to
    const headerElement = document.createElement('div');
    headerElement.className = 'response-header mb-3';
    
    // Use selected message if available, otherwise use lastPlayerMessage
    const respondingTo = selectedMessage 
        ? `${selectedMessage.playerName}: ${selectedMessage.text}` 
        : (lastPlayerName ? `${lastPlayerName}: ${lastPlayerMessage}` : 'message');
    
    headerElement.innerHTML = `
        <div class="alert alert-info">
            <strong>Responding to:</strong> ${respondingTo}
        </div>
    `;
    responseOptionsElement.appendChild(headerElement);
    
    // Create container for options
    const optionsContainer = document.createElement('div');
    optionsContainer.className = 'response-options-container';
    
    const optionLabels = ['Positive', 'Neutral', 'Negative'];
    responses.forEach((response, index) => {
        // Clean any em dashes from responses
        const cleanedResponse = cleanEmDashes(response);
        
        const responseOption = document.createElement('div');
        responseOption.className = 'response-option';
        responseOption.innerHTML = `
            <div class="response-text">${cleanedResponse}</div>
            <div class="response-controls">
                <div class="d-flex">
                    <span class="badge bg-secondary me-2">${optionLabels[index] || `Option ${index + 1}`}</span>
                    <button class="btn btn-sm btn-outline-success me-1 btn-feedback" data-rating="1" data-index="${index}" title="This response is good"><i class="bi bi-hand-thumbs-up"></i></button>
                    <button class="btn btn-sm btn-outline-danger btn-feedback" data-rating="0" data-index="${index}" title="This response needs improvement"><i class="bi bi-hand-thumbs-down"></i></button>
                </div>
                <button class="btn btn-sm btn-primary btn-copy">Copy</button>
            </div>
        `;
        
        // Add feedback button handlers
        const feedbackButtons = responseOption.querySelectorAll('.btn-feedback');
        feedbackButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                const rating = parseInt(button.getAttribute('data-rating'));
                const responseIndex = parseInt(button.getAttribute('data-index'));
                
                submitFeedback(responses[responseIndex], rating);
                
                // Update button appearances
                feedbackButtons.forEach(btn => {
                    btn.classList.remove('active');
                    
                    if (btn.getAttribute('data-rating') === '1') {
                        btn.classList.remove('btn-success');
                        btn.classList.add('btn-outline-success');
                    } else {
                        btn.classList.remove('btn-danger');
                        btn.classList.add('btn-outline-danger');
                    }
                });
                
                // Highlight the selected button
                if (rating === 1) {
                    button.classList.remove('btn-outline-success');
                    button.classList.add('btn-success');
                } else {
                    button.classList.remove('btn-outline-danger');
                    button.classList.add('btn-danger');
                }
                button.classList.add('active');
            });
        });
        
        const copyButton = responseOption.querySelector('.btn-copy');
        copyButton.addEventListener('click', () => {
            navigator.clipboard.writeText(cleanedResponse)
                .then(() => {
                    // Show notification
                    const toastBody = notificationToast.querySelector('.toast-body');
                    toastBody.textContent = 'Response copied to clipboard!';
                    toast.show();
                    
                    // Clear the selection after copying
                    selectedMessage = null;
                    document.querySelectorAll('.message.selected').forEach(el => {
                        el.classList.remove('selected');
                    });
                    
                    // Update the message display
                    incomingMessageElement.innerHTML = '<span class="text-success">✓ Response copied!</span>';
                    
                    // After a delay, reset the message display
                    setTimeout(() => {
                        incomingMessageElement.textContent = 'No messages selected yet';
                        generateResponseButton.disabled = true;
                    }, 3000);
                })
                .catch(err => {
                    console.error('Failed to copy: ', err);
                });
        });
        
        responseOption.addEventListener('click', (e) => {
            if (!e.target.classList.contains('btn-copy')) {
                // Toggle selection
                const isSelected = responseOption.classList.contains('selected');
                
                // Remove selection from all options
                document.querySelectorAll('.response-option').forEach(option => {
                    option.classList.remove('selected');
                });
                
                // If it wasn't selected before, select it now
                if (!isSelected) {
                    responseOption.classList.add('selected');
                }
            }
        });
        
        optionsContainer.appendChild(responseOption);
    });
    
    responseOptionsElement.appendChild(optionsContainer);
}

function submitFeedback(response, rating) {
    // Prepare feedback data
    const feedbackData = {
        character: activeCharacter,
        rating: rating,
        response: response,
        message_data: currentMessageData || {
            message: selectedMessage ? selectedMessage.text : lastPlayerMessage,
            player_name: selectedMessage ? selectedMessage.playerName : lastPlayerName
        }
    };
    
    console.log('Submitting feedback:', feedbackData);
    
    // Send feedback to server
    socket.emit('submit_feedback', feedbackData);
}

function fetchFeedbackSummary(characterName) {
    fetch(`/api/feedback/${encodeURIComponent(characterName)}`)
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Error fetching feedback summary:', data.error);
                return;
            }
            
            updateFeedbackSummary(data);
        })
        .catch(error => {
            console.error('Error fetching feedback summary:', error);
        });
}

function updateFeedbackSummary(data) {
    // Show the feedback summary section
    feedbackSummaryElement.style.display = 'block';
    
    // Update the counts
    positiveCountElement.textContent = data.positive_feedback;
    negativeCountElement.textContent = data.negative_feedback;
    totalCountElement.textContent = data.total_responses;
    
    // Update the progress bar
    const ratio = data.feedback_ratio || 0;
    const percentage = Math.round(ratio * 100);
    feedbackProgressElement.style.width = `${percentage}%`;
    feedbackProgressElement.setAttribute('aria-valuenow', percentage);
    feedbackProgressElement.textContent = `${percentage}%`;
    
    // Update color based on feedback ratio
    if (percentage >= 70) {
        feedbackProgressElement.classList.remove('bg-danger', 'bg-warning');
        feedbackProgressElement.classList.add('bg-success');
    } else if (percentage >= 40) {
        feedbackProgressElement.classList.remove('bg-danger', 'bg-success');
        feedbackProgressElement.classList.add('bg-warning');
    } else {
        feedbackProgressElement.classList.remove('bg-success', 'bg-warning');
        feedbackProgressElement.classList.add('bg-danger');
    }
}

// New functions for context window

/**
 * Add a message to the chat history
 * @param {Object} message - The message to add
 */
function addToChatHistory(message) {
    // Add to the beginning so newest are first
    chatHistory.unshift(message);
    
    // Limit the number of messages in history
    if (chatHistory.length > MAX_CHAT_HISTORY) {
        chatHistory = chatHistory.slice(0, MAX_CHAT_HISTORY);
    }
    
    console.log('Chat history updated:', chatHistory);
}

/**
 * Build conversation context for a message from a specific player
 * @param {string} playerName - The name of the player to get context for
 * @returns {Object} - The context object
 */
function buildConversationContext(playerName) {
    if (chatHistory.length === 0) {
        return { messages: [] };
    }
    
    const context = {
        messages: [],
        summary: ""
    };
    
    // Get the last 3-4 messages from this player (character-specific context)
    const playerMessages = chatHistory
        .filter(msg => msg.speaker === playerName)
        .slice(0, 4);
    
    // Get the last 2-3 messages from the overall conversation (immediate context)
    const recentMessages = chatHistory.slice(0, 3);
    
    // Combine both sets of messages, removing duplicates
    const contextMessages = [...recentMessages];
    
    playerMessages.forEach(msg => {
        // Check if this message is already in contextMessages
        const isDuplicate = contextMessages.some(
            m => m.speaker === msg.speaker && m.text === msg.text
        );
        
        if (!isDuplicate) {
            contextMessages.push(msg);
        }
    });
    
    // Sort by timestamp (oldest first) for logical conversation flow
    contextMessages.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));
    
    // Format messages for context
    context.messages = contextMessages.map(msg => ({
        speaker: msg.speaker,
        text: msg.text
    }));
    
    // Create a brief summary of the conversation
    if (contextMessages.length > 0) {
        // Use first and last message to summarize the topic
        const firstMsg = contextMessages[0];
        const lastMsg = contextMessages[contextMessages.length - 1];
        
        context.summary = `Conversation between ${activeCharacter} and ${playerName} about ${firstMsg.text.substring(0, 30)}...`;
    }
    
    return context;
}

// Initial load
fetchCharacters();

// Periodically refresh character list (every 30 seconds)
setInterval(fetchCharacters, 30000); 

// Custom code to handle setting the OpenAI API token
document.addEventListener('DOMContentLoaded', function() {
    const saveTokenButton = document.getElementById('save-api-token');
    if (saveTokenButton) {
        saveTokenButton.addEventListener('click', function() {
            const tokenInput = document.getElementById('openai-token');
            const token = tokenInput.value.trim();
            if (token === "") {
                alert("Please enter a valid API token.");
                return;
            }
            fetch('/set_openai_token', {
                method: 'POST',
                credentials: 'same-origin',
                headers: {
                    'Content-Type': 'application/x-www-form-urlencoded'
                },
                body: 'openai_token=' + encodeURIComponent(token)
            })
            .then(response => response.json())
            .then(data => {
                if(data.success) {
                    alert("API token set successfully!");
                    window.location.reload();
                } else {
                    alert("Error: " + (data.error || "Unknown error"));
                }
            })
            .catch(error => {
                console.error("Error setting API token:", error);
                alert("Error setting API token: " + error);
            });
        });
    }
}); 