// Initialize the Socket.IO connection
const socket = io();

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

// Helper function to clean em dashes
function cleanEmDashes(text) {
    return text ? text.replace(/—/g, '-') : text;
}

// Connect to WebSocket
socket.on('connect', () => {
    console.log('Connected to server');
    chatMessagesElement.innerHTML = '<p class="text-center text-success">Connected to server</p>';
    // Request initial data
    fetchCharacters();
});

socket.on('disconnect', () => {
    console.log('Disconnected from server');
    chatMessagesElement.innerHTML += '<p class="text-center text-danger">Disconnected from server</p>';
});

// Listen for character change
socket.on('character_change', (data) => {
    console.log('Character changed:', data);
    if (data.character) {
        activeCharacter = data.character;
        updateCharacterDisplay(data.character);
    }
});

// Listen for new chat messages
socket.on('new_message', (data) => {
    console.log('New message:', data);
    appendChatMessage(data.message, data.is_own, data.original_message);
});

// Listen for player messages that may need a response
socket.on('player_message', (data) => {
    console.log('Player message:', data);
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
    const messageToRespond = selectedMessage || lastPlayerMessage;
    const messageSource = selectedMessage ? selectedMessage.playerName : lastPlayerName;
    
    if (activeCharacter && messageToRespond) {
        incomingMessageElement.innerHTML = `<strong>${messageSource}:</strong> ${messageToRespond.text || messageToRespond}`;
        responseOptionsElement.innerHTML = '<p class="text-center"><div class="spinner-border text-primary" role="status"><span class="visually-hidden">Loading...</span></div></p>';
        socket.emit('request_ai_reply', {
            character: activeCharacter,
            message: messageToRespond.text || messageToRespond,
            player_name: messageSource
        });
    }
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
    characterListElement.innerHTML = '';
    
    if (characters.length === 0) {
        characterListElement.innerHTML = '<p class="text-muted">No characters available</p>';
        return;
    }
    
    characters.forEach(character => {
        const item = document.createElement('a');
        item.href = '#';
        item.className = 'list-group-item';
        if (character === activeCharacter) {
            item.className += ' active';
        }
        item.textContent = character;
        item.addEventListener('click', (e) => {
            e.preventDefault();
            activateCharacter(character);
        });
        
        characterListElement.appendChild(item);
    });
}

function activateCharacter(characterName) {
    // First update the UI to show character as selected
    const items = characterListElement.querySelectorAll('.list-group-item');
    items.forEach(item => {
        if (item.textContent === characterName) {
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
    const items = characterListElement.querySelectorAll('.list-group-item');
    items.forEach(item => {
        if (item.textContent === characterName) {
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
    const wasAtBottom = chatMessagesElement.scrollHeight - chatMessagesElement.clientHeight <= chatMessagesElement.scrollTop + 10;
    
    // Try to parse player message from the chat line
    let playerName = "";
    let playerText = "";
    
    // Try to extract player name and message
    const playerMatch = message.match(/\[([^\]]+)\] ([^:]+): \[Talk\] (.*)/);
    if (playerMatch) {
        playerName = playerMatch[2];
        playerText = playerMatch[3];
    } else {
        // Fallback pattern
        const simpleTalkMatch = message.match(/([^:]+): \[Talk\] (.*)/);
        if (simpleTalkMatch) {
            playerName = simpleTalkMatch[1];
            playerText = simpleTalkMatch[2];
        }
    }
    
    // Create message element
    const messageElement = document.createElement('div');
    messageElement.className = `message ${isSelf ? 'message-self' : 'message-other'}`;
    
    // If this is a player message (not the character's message), make it clickable
    if (!isSelf && playerName && playerText) {
        messageElement.classList.add('selectable-message');
        
        // Store the message data for use when selected
        const messageData = {
            playerName: playerName,
            text: playerText,
            fullMessage: message
        };
        
        // Make message clickable
        messageElement.addEventListener('click', function() {
            // Deselect any previously selected message
            document.querySelectorAll('.message.selected').forEach(el => {
                el.classList.remove('selected');
            });
            
            // Mark this message as selected
            messageElement.classList.add('selected');
            
            // Store the selected message
            selectedMessage = messageData;
            
            // Update the display of the selected message
            incomingMessageElement.innerHTML = `<strong>${playerName}:</strong> ${playerText}`;
            
            // Show a "message selected" indicator
            const selectedBadge = document.createElement('span');
            selectedBadge.className = 'badge bg-primary ms-2';
            selectedBadge.textContent = 'Selected';
            incomingMessageElement.appendChild(selectedBadge);
            
            // Clear any previous responses when selecting a new message
            responseOptionsElement.innerHTML = '<p class="text-center text-muted">Click "Generate Response" to create AI replies for this message</p>';
            
            // Enable the generate button
            generateResponseButton.disabled = false;
        });
    }
    
    messageElement.textContent = message;
    
    // Add timestamp
    const timestampElement = document.createElement('div');
    timestampElement.className = 'message-time';
    const timestamp = new Date().toLocaleTimeString();
    timestampElement.textContent = timestamp;
    messageElement.appendChild(timestampElement);
    
    // Clear the "waiting for messages" text if it's there
    if (chatMessagesElement.querySelector('.text-muted')) {
        chatMessagesElement.innerHTML = '';
    }
    
    // Append the message
    chatMessagesElement.appendChild(messageElement);
    
    // Auto-scroll if the user was already at the bottom
    if (wasAtBottom) {
        chatMessagesElement.scrollTop = chatMessagesElement.scrollHeight;
    }
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
    
    responses.forEach((response, index) => {
        // Clean any em dashes from responses
        const cleanedResponse = cleanEmDashes(response);
        
        const responseOption = document.createElement('div');
        responseOption.className = 'response-option';
        responseOption.innerHTML = `
            <div class="response-text">${cleanedResponse}</div>
            <div class="response-controls">
                <div class="d-flex">
                    <span class="badge bg-secondary me-2">Option ${index + 1}</span>
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

// Initial load
fetchCharacters();

// Periodically refresh character list (every 30 seconds)
setInterval(fetchCharacters, 30000); 