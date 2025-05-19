#!/usr/bin/env python3
import os
import re
import json
import time
import datetime
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
from dotenv import load_dotenv
import openai
import character_manager  # Import the character manager module

# Load environment variables
load_dotenv()

# Configuration
CHARACTER_PROFILES_DIR = "character_profiles"
CHAT_HISTORY_DIR = "chat_history"
FEEDBACK_DIR = "feedback_data"
# No local log file path - we only receive logs via WebSocket/API
USER_ACCOUNT = os.getenv("USER_ACCOUNT", "Fullgazz")
SYSTEM_PATTERN = r"\[Talk\] (?:What would you like to do\?|Please choose section:|<c>\[.*?\]</c>|Crafting Menu|Back|Cancel)"

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "nwnx-chatbot-secret")
socketio = SocketIO(app, cors_allowed_origins="*")

# OpenAI Configuration
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    print("WARNING: No OpenAI API key found in environment variables. Please set OPENAI_API_KEY.")
else:
    print(f"Using OpenAI API key: {api_key[:5]}...{api_key[-4:]}")
openai.api_key = api_key

# Global variables
active_character = None
character_profiles = {}  # Will be loaded from character_manager
chat_monitor_thread = None
running = True
last_position = 0

# Setup directories
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)
os.makedirs(CHARACTER_PROFILES_DIR, exist_ok=True)
os.makedirs(FEEDBACK_DIR, exist_ok=True)

# Load character profiles
# Detect character from log line
def detect_character(line):
    """Detect which character is active based on the log line"""
    global active_character
    character_pattern = re.compile(r"\[" + re.escape(USER_ACCOUNT) + r"\] ([^:]+)")
    match = character_pattern.search(line)
    
    if match:
        character_name = match.group(1)
        
        if character_name != active_character:
            active_character = character_name
            print(f"Switched to character: {character_name}")
            socketio.emit('character_change', {'character': character_name})
            
            # Set up chat history for this character
            setup_chat_history(character_name)
            
        return character_name
        
    return None

# Setup chat history
def setup_chat_history(character_name):
    """Set up chat history directory for a specific character"""
    try:
        # Create character-specific directory
        character_dir = os.path.join(CHAT_HISTORY_DIR, character_name.replace(' ', '_'))
        os.makedirs(character_dir, exist_ok=True)
        print(f"Chat history directory for {character_name}: {character_dir}")
    except Exception as e:
        print(f"Error setting up chat history: {e}")

# Save to chat history
def save_to_history(character_name, message, sender, timestamp=None):
    """Save a message to the character's chat history"""
    if not timestamp:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        character_dir = os.path.join(CHAT_HISTORY_DIR, character_name.replace(' ', '_'))
        history_file = f"{character_dir}/chat_history.json"
        
        # Load existing history or create new
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        else:
            history = []
        
        # Add new message
        history.append({
            "timestamp": timestamp,
            "sender": sender,
            "message": message
        })
        
        # Save updated history
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
        
    except Exception as e:
        print(f"Error saving to chat history: {e}")

# Chat monitor function
def monitor_chat():
    """Monitor for new messages (receiving via WebSocket/API only)"""
    global running
    
    print("Starting chat monitor - waiting for logs via WebSocket/API")
    print("No local file monitoring - all logs come from remote clients")
    
    # Just keep the thread alive to receive WebSocket messages
    while running:
        time.sleep(5)  # Just sleep, actual processing happens in socket handlers

# Process new messages
def process_new_messages(data):
    """Process new messages from the log file"""
    lines = data.strip().split('\n')
    
    print(f"Processing {len(lines)} new message lines")
    
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue
            
        # Skip lines with <c> tags - these are item/action notifications, not chat
        if "<c>" in line and "</c>" in line:
            print(f"Skipping system notification: {line[:30]}...")
            continue
            
        # Detect which character is active
        character_name = detect_character(line)
            
        # Check if this is our own character's message
        is_own_message = f"[{USER_ACCOUNT}]" in line
        
        # Check if this is likely a system menu message
        is_system_message = is_own_message and re.search(SYSTEM_PATTERN, line)
        
        if is_system_message:
            # This is a system message, we'll ignore it
            print(f"Skipping system menu message: {line[:30]}...")
            continue
            
        print(f"Processing chat message: {line[:50]}...")
        
        # Save the message
        if character_name:
            save_to_history(character_name, line, "self" if is_own_message else "other")
        
        # Parse the original message content for player messages
        original_message = None
        if not is_own_message:
            # Try to match [Account] Character: [Talk] message
            match = re.match(r"\[([^\]]+)\] ([^:]+): \[Talk\] (.*)", line)
            if match:
                account, char_name, player_message = match.groups()
                original_message = player_message
            else:
                # Fallback: Try to match Name: [Talk] message
                match = re.match(r"([^:]+): \[Talk\] (.*)", line)
                if match:
                    name, player_message = match.groups()
                    original_message = player_message
        
        # Format the message for display
        formatted_message = line
        # Check if this has Talk format, if so, make it more readable
        talk_match = re.match(r"\[([^\]]+)\] ([^:]+): \[Talk\] (.*)", line)
        if talk_match:
            account, speaker, text = talk_match.groups()
            formatted_message = f"<strong>{speaker}:</strong> {text}"
        else:
            simple_match = re.match(r"([^:]+): \[Talk\] (.*)", line)
            if simple_match:
                speaker, text = simple_match.groups()
                formatted_message = f"<strong>{speaker}:</strong> {text}"
        
        # Emit the message to websocket clients
        print(f"Broadcasting message to all clients via WebSocket")
        socketio.emit('new_message', {
            'character': character_name,
            'message': formatted_message,
            'raw_message': line,
            'is_own': is_own_message,
            'original_message': original_message
        })
            
        # Process NPC/player messages for auto-reply
        if not is_own_message:
            # Try to match [Account] Character: [Talk] message
            match = re.match(r"\[([^\]]+)\] ([^:]+): \[Talk\] (.*)", line)
            if match:
                account, char_name, player_message = match.groups()
                print(f"Broadcasting player message from {char_name} to all clients")
                socketio.emit('player_message', {
                    'character': active_character,
                    'player_name': char_name,
                    'message': player_message
                })
            else:
                # Fallback: Try to match Name: [Talk] message
                match = re.match(r"([^:]+): \[Talk\] (.*)", line)
                if match:
                    name, player_message = match.groups()
                    print(f"Broadcasting player message from {name} to all clients")
                    socketio.emit('player_message', {
                        'character': active_character,
                        'player_name': name,
                        'message': player_message
                    })

# Generate AI responses
def generate_in_character_reply(character_name, player_message, num_alternatives=3):
    """Generate AI responses for a character"""
    if not character_name or character_name not in character_profiles:
        return []
    
    persona = character_profiles[character_name]
    
    # Set character-specific parameters
    temperature = persona.get("temperature", 0.7)  # Get temperature from profile or use 0.7 as default
    
    # Note: Special case handling for Elvith is maintained but temperature modifier is reduced
    # as the user can now directly control temperature via the UI
    creativity_instruction = ""
    
    # Check if this is Elvith - if so, reduce creativity/poetry
    if "Elvith" in character_name:
        # Apply a small reduction to the user-defined temperature
        temperature = max(0.1, temperature * 0.9)  # Reduce by 10% but not below 0.1
        creativity_instruction = (
            f"\nIMPORTANT NOTE FOR ELVITH MA'FOR: Reduce poetic and flowery language by 30%. "
            f"Be more direct and straightforward in conversations. "
            f"Focus on clear communication rather than excessive metaphors or philosophical tangents. "
            f"While still maintaining your elegant and aristocratic tone, prioritize following the "
            f"conversation directly rather than being overly poetic or abstract."
        )
    
    system_prompt = (
        f"You are roleplaying as the following character in Neverwinter Nights EE. "
        f"Stay strictly in character, using the persona, background, and style below.\n\n"
        f"Persona: {persona.get('persona', '')}\n"
        f"Background: {persona.get('background', '')}\n"
        f"Appearance: {persona.get('appearance', '')}\n"
        f"Traits: {', '.join(persona.get('traits', []))}\n"
        f"Roleplay Prompt: {persona.get('roleplay_prompt', '')}\n"
        f"Interaction Constraints: {', '.join(persona.get('interaction_constraints', []))}\n"
        f"Mannerisms: {', '.join(persona.get('mannerisms', []))}\n"
        f"Example Dialogue: {persona.get('dialogue_examples', [])}\n"
        f"{creativity_instruction}\n"
        f"\nNever break character. Respond to the following as your character would.\n"
        f"\nImportant formatting notes: Never use em dashes (—) in your responses. Use regular hyphens (-) or just avoid them entirely.\n"
        f"\nGenerate three distinct in-character replies to the player message, each with a different style:"
        f"\n1. Fast, dry, and pointed (1 line)."
        f"\n2. Elegant but not long (2 lines)."
        f"\n3. Creative and elegant, with some flair (3 lines)."
        f"\nLabel each reply as '1.', '2.', and '3.' respectively."
    )
    user_prompt = f"Player says: {player_message}\nYour replies:"

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=400,
            temperature=temperature,
            n=1,
        )
        
        # Parse the single response into three options
        content = response.choices[0].message.content.strip()
        # Remove any em dashes in the response
        content = content.replace("—", "-")
        
        # Split by '1.', '2.', '3.'
        import re
        matches = re.split(r'\n?\s*\d\.\s*', content)
        # The first split part is before '1.', so ignore it
        options = [m.strip() for m in matches[1:4] if m.strip()]
        
        # Record AI responses in history
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for idx, reply in enumerate(options, 1):
            save_to_history(character_name, f"[AI Option {idx}] {reply}", "ai", timestamp)
        
        return options
    except Exception as e:
        print(f"Error generating AI response: {e}")
        return []

def translate_custom_message(character_name, portuguese_text):
    """Translate a custom Portuguese message to English using the character's persona"""
    if not character_name or character_name not in character_profiles:
        return {"error": "Character not found"}
    
    persona = character_profiles[character_name]
    
    # Set character-specific parameters
    temperature = persona.get("temperature", 0.7)  # Get temperature from profile or use 0.7 as default
    creativity_instruction = ""
    
    # Check if this is Elvith - if so, reduce creativity/poetry
    if "Elvith" in character_name:
        # Apply a small reduction to the user-defined temperature
        temperature = max(0.1, temperature * 0.9)  # Reduce by 10% but not below 0.1
        creativity_instruction = (
            f"\nIMPORTANT NOTE FOR ELVITH MA'FOR: Reduce poetic and flowery language by 30%. "
            f"Be more direct and straightforward in translations. "
            f"Focus on clear communication rather than excessive metaphors or philosophical tangents. "
            f"While still maintaining your elegant and aristocratic tone, prioritize direct communication "
            f"rather than being overly poetic or abstract."
        )
    
    system_prompt = (
        f"You are roleplaying as the following character in Neverwinter Nights EE. "
        f"Stay strictly in character, using the persona, background, and style below.\n\n"
        f"Persona: {persona.get('persona', '')}\n"
        f"Background: {persona.get('background', '')}\n"
        f"Appearance: {persona.get('appearance', '')}\n"
        f"Traits: {', '.join(persona.get('traits', []))}\n"
        f"Roleplay Prompt: {persona.get('roleplay_prompt', '')}\n"
        f"Interaction Constraints: {', '.join(persona.get('interaction_constraints', []))}\n"
        f"Mannerisms: {', '.join(persona.get('mannerisms', []))}\n"
        f"Example Dialogue: {persona.get('dialogue_examples', [])}\n"
        f"{creativity_instruction}\n"
        f"\nYou will receive a message in Portuguese. Your task is NOT to translate it literally, but to "
        f"understand the meaning and intent behind it, then express that intent as your character would naturally say it. "
        f"Always include one action between asterisks (*) that reflects your character's mannerisms and personality. "
        f"Then include your character's speech in quotes (\"\"). Use the character's unique vocabulary, "
        f"speech patterns, and mannerisms.\n"
        f"\nDo NOT attempt to preserve the exact wording or structure of the original Portuguese message. "
        f"Instead, understand what the user wants to express, and then create a NEW message that conveys "
        f"that same meaning but in your character's distinct voice and style.\n"
        f"\nImportant formatting notes: Never use em dashes (—) in your responses. Use regular hyphens (-) or just avoid them entirely."
    )
    user_prompt = f"I want to roleplay as your character and say something in Portuguese. Please understand what I mean and express it as your character would: \"{portuguese_text}\"\n\nRespond with an appropriate character action and speech that conveys this meaning."

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            max_tokens=250,
            temperature=temperature,
            n=1,
        )
        
        # Get the translated message
        translated = response.choices[0].message.content.strip()
        # Remove any em dashes in the response
        translated = translated.replace("—", "-")
        
        # Record the translation in history
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        save_to_history(
            character_name, 
            f"Custom message interpretation - Original: \"{portuguese_text}\" → As character: \"{translated}\"", 
            "system", 
            timestamp
        )
        
        return {
            "original": portuguese_text,
            "translated": translated,
            "character": character_name
        }
    except Exception as e:
        print(f"Error translating message: {e}")
        return {"error": str(e)}

# Helper function to clean em dashes from any text
def remove_em_dashes(text):
    """Replace em dashes with hyphens in text"""
    if text:
        return text.replace("—", "-")
    return text

@app.route('/api/translate', methods=['POST'])
def translate_message():
    """API endpoint to translate a custom message"""
    data = request.json
    character_name = data.get('character', active_character)
    portuguese_text = data.get('text', '')
    
    if not character_name:
        return jsonify({"error": "No active character selected"}), 400
        
    if not portuguese_text:
        return jsonify({"error": "No text provided"}), 400
    
    result = translate_custom_message(character_name, portuguese_text)
    return jsonify(result)

@socketio.on('translate_message')
def handle_translate_message(data):
    """WebSocket endpoint to translate a message"""
    character_name = data.get('character', active_character)
    portuguese_text = data.get('text', '')
    
    if not character_name or not portuguese_text:
        emit('translation_result', {'error': 'Missing character or text'})
        return
    
    result = translate_custom_message(character_name, portuguese_text)
    
    # Make sure translated text doesn't have em dashes
    if 'translated' in result:
        result['translated'] = remove_em_dashes(result['translated'])
    
    emit('translation_result', result)

# Flask routes
@app.route('/')
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/create-character')
def create_character_form():
    """Render the character creation form"""
    return render_template('create_character.html')

@app.route('/api/characters', methods=['GET'])
def get_characters():
    """Return list of available characters"""
    return jsonify({
        'active_character': active_character,
        'characters': list(character_profiles.keys())
    })

@app.route('/api/characters', methods=['POST'])
def create_character():
    """Create a new character profile"""
    data = request.json
    
    # Validate required fields
    if not data or 'name' not in data:
        return jsonify({'error': 'Character name is required'}), 400
    
    # Save character profile
    result = character_manager.save_profile(data)
    
    if 'error' in result:
        return jsonify(result), 400
    
    # Reload all character profiles
    global character_profiles
    character_profiles = character_manager.load_all_profiles()
    
    return jsonify(result)

@app.route('/api/characters/<name>', methods=['DELETE'])
def delete_character(name):
    """Delete a character profile"""
    global active_character, character_profiles
    
    # Check if character exists
    if name not in character_profiles:
        return jsonify({'error': 'Character not found'}), 404
    
    # If this is the active character, clear it
    if active_character == name:
        active_character = None
    
    # Delete the character
    result = character_manager.delete_profile(name)
    
    if 'error' in result:
        return jsonify(result), 400
    
    # Reload all character profiles
    character_profiles = character_manager.load_all_profiles()
    
    return jsonify(result)

@app.route('/api/character/<n>')
def get_character(n):
    """Return character profile"""
    if n in character_profiles:
        return jsonify(character_profiles[n])
    return jsonify({'error': 'Character not found'}), 404

@app.route('/api/character/<n>/activate', methods=['POST'])
def set_active_character(n):
    """Set a character as the active character"""
    global active_character
    
    if n not in character_profiles:
        return jsonify({'error': 'Character not found'}), 404
    
    active_character = n
    print(f"Manually activated character: {n}")
    
    # Set up chat history for this character
    setup_chat_history(n)
    
    # Emit the character change to all clients
    socketio.emit('character_change', {'character': n})
    
    return jsonify({'success': True, 'active_character': n})

@app.route('/api/history/<character>')
def get_history(character):
    """Return chat history for a character"""
    try:
        character_dir = os.path.join(CHAT_HISTORY_DIR, character.replace(' ', '_'))
        history_file = f"{character_dir}/chat_history.json"
        
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            return jsonify(history)
        return jsonify([])
    except Exception as e:
        print(f"Error retrieving history: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/debug')
def debug_info():
    """Return debug information"""
    debug_data = {
        'current_directory': os.getcwd(),
        'active_character': active_character,
        'characters_loaded': list(character_profiles.keys()),
        'monitor_thread_alive': chat_monitor_thread.is_alive() if chat_monitor_thread else False,
        'socketio_initialized': socketio is not None,
        'openai_key_available': api_key is not None
    }
    
    # Directory info
    try:
        # Get character_profiles directory info
        debug_data['character_profiles_dir'] = CHARACTER_PROFILES_DIR
        debug_data['character_profiles_exists'] = os.path.exists(CHARACTER_PROFILES_DIR)
        if os.path.exists(CHARACTER_PROFILES_DIR):
            debug_data['character_profiles_contents'] = os.listdir(CHARACTER_PROFILES_DIR)
            
        # Get chat_history directory info
        debug_data['chat_history_dir'] = CHAT_HISTORY_DIR
        debug_data['chat_history_exists'] = os.path.exists(CHAT_HISTORY_DIR)
        if os.path.exists(CHAT_HISTORY_DIR):
            debug_data['chat_history_contents'] = os.listdir(CHAT_HISTORY_DIR)
    except Exception as e:
        debug_data['dir_error'] = str(e)
    
    return jsonify(debug_data)

@app.route('/api/debug/send_test_message')
def send_test_message():
    """Send a test message to all connected clients"""
    test_message = "[D6lab] Test Character: [Talk] This is a test message from the debug endpoint"
    
    print(f"Sending test message to all clients: {test_message}")
    
    try:
        # Method 1: Process through normal message handling
        process_new_messages(test_message)
        
        # Method 2: Send direct system message for validation
        socketio.emit('system_message', {
            'message': f"Debug test at {datetime.datetime.now().strftime('%H:%M:%S')}",
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        # Method 3: Direct new_message event to bypass processing
        formatted_message = "<strong>Test Character:</strong> Direct test message"
        socketio.emit('new_message', {
            'character': 'Test Character',
            'message': formatted_message,
            'raw_message': test_message,
            'is_own': False,
            'original_message': "Direct test message"
        })
        
        return jsonify({
            'success': True,
            'message': 'Test message sent using multiple methods'
        })
    except Exception as e:
        print(f"Error sending test message: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/debug')
def debug_page():
    """Render the debug page for testing WebSocket connection"""
    return render_template('debug.html')

@app.route('/api/debug/simple_test')
def simple_test_message():
    """Send a simple formatted message to all clients"""
    try:
        # Send the simplest possible message directly to clients
        socketio.emit('new_message', {
            'character': 'Debug',
            'message': '<strong>Test:</strong> Simple message from server',
            'raw_message': 'Test: Simple message from server',
            'is_own': False,
            'original_message': 'Simple message from server'
        })
        
        print("Sent simple test message via new_message event")
        
        return jsonify({
            'success': True,
            'message': 'Simple test message sent'
        })
    except Exception as e:
        print(f"Error sending simple test message: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/debug/direct_test')
def direct_test_message():
    """Send a direct test message bypassing all processing logic"""
    try:
        message_content = "<strong>Direct Test:</strong> This is a direct test message at " + datetime.datetime.now().strftime("%H:%M:%S")
        
        print(f"Sending direct test message to all clients: {message_content}")
        
        # Send the simplest possible message directly to clients
        socketio.emit('new_message', {
            'character': 'Debug',
            'message': message_content,
            'raw_message': 'Direct test message',
            'is_own': False,
            'original_message': 'Direct test message content'
        })
        
        # Also try a system message which may have different handling
        socketio.emit('system_message', {
            'message': f"System test at {datetime.datetime.now().strftime('%H:%M:%S')}",
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
        print("Sent direct test message via new_message and system_message events")
        
        return jsonify({
            'success': True,
            'message': 'Direct test messages sent via both channels'
        })
    except Exception as e:
        print(f"Error sending direct test message: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/debug/test_player_message')
def test_player_message():
    """Send a test player message that can be selected for AI response"""
    try:
        # Create a test player message
        player_name = "Test Player"
        player_message = "Hello! This is a test message. You should be able to select this for an AI response."
        raw_message = f"[Test Account] {player_name}: [Talk] {player_message}"
        formatted_message = f"<strong>{player_name}:</strong> {player_message}"
        
        print(f"Sending test player message from {player_name}")
        
        # Send formatted message to chat
        socketio.emit('new_message', {
            'character': 'Debug',
            'message': formatted_message,
            'raw_message': raw_message,
            'is_own': False,
            'original_message': player_message
        })
        
        # Send player_message event for response generation
        socketio.emit('player_message', {
            'character': active_character,
            'player_name': player_name,
            'message': player_message
        })
        
        return jsonify({
            'success': True,
            'message': 'Test player message sent'
        })
    except Exception as e:
        print(f"Error sending test player message: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Socket.IO events
@socketio.on('connect')
def connect():
    """Handle client connection"""
    emit('connection_status', {'status': 'connected'})
    # Send current character info if available
    if active_character:
        emit('character_change', {'character': active_character})

# Add new socketio endpoint for activating a character
@socketio.on('activate_character')
def handle_activate_character(data):
    """Set active character through websocket"""
    global active_character
    
    character_name = data.get('character')
    if not character_name:
        emit('activation_result', {'error': 'No character specified'})
        return
        
    if character_name not in character_profiles:
        emit('activation_result', {'error': 'Character not found'})
        return
    
    active_character = character_name
    print(f"Manually activated character via websocket: {character_name}")
    
    # Set up chat history for this character
    setup_chat_history(character_name)
    
    # Emit the character change to all clients
    emit('character_change', {'character': character_name})
    emit('activation_result', {'success': True, 'active_character': character_name})

@socketio.on('request_ai_reply')
def handle_ai_reply_request(data):
    """Generate AI reply for a character"""
    character_name = data.get('character', active_character)
    player_message = data.get('message', '')
    player_name = data.get('player_name', 'Unknown')
    
    if not character_name or not player_message:
        emit('ai_reply', {'error': 'Missing character or message'})
        return
    
    # Log the request
    print(f"Generating AI reply for '{character_name}' responding to '{player_name}': '{player_message}'")
    
    responses = generate_in_character_reply(character_name, player_message)
    
    # Make sure responses don't have em dashes
    responses = [remove_em_dashes(response) for response in responses]
    
    # Save this interaction to history
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_to_history(
        character_name, 
        f"Request to respond to {player_name}: {player_message}", 
        "system", 
        timestamp
    )
    
    emit('ai_reply', {
        'character': character_name,
        'responses': responses,
        'original_message': player_message,
        'player_name': player_name
    })

# Add route for manual message response
@app.route('/api/respond', methods=['POST'])
def manual_respond():
    """Manually generate a response to a specific message"""
    data = request.json
    character_name = data.get('character', active_character)
    player_message = data.get('message', '')
    player_name = data.get('player_name', 'Unknown')
    
    if not character_name or not player_message:
        return jsonify({'error': 'Missing character or message'}), 400
    
    # Generate response
    responses = generate_in_character_reply(character_name, player_message)
    
    # Save to history
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    save_to_history(
        character_name, 
        f"Manual request to respond to {player_name}: {player_message}", 
        "system", 
        timestamp
    )
    
    return jsonify({
        'character': character_name,
        'responses': responses,
        'original_message': player_message,
        'player_name': player_name
    })

# Start chat monitor thread
def start_monitor():
    global chat_monitor_thread, running, character_profiles
    
    # Load character profiles from the manager module
    character_profiles = character_manager.load_all_profiles()
    print(f"Loaded {len(character_profiles)} character profiles")
    
    # Start the monitor thread
    running = True
    chat_monitor_thread = threading.Thread(target=monitor_chat)
    chat_monitor_thread.daemon = True
    chat_monitor_thread.start()

def save_feedback(character_name, message_data, response, rating, notes=""):
    """Save feedback on a character's response"""
    if not character_name:
        return {"error": "No character specified"}
    
    # Create character-specific feedback directory
    feedback_dir = os.path.join(FEEDBACK_DIR, character_name.replace(' ', '_'))
    os.makedirs(feedback_dir, exist_ok=True)
    
    # Create the feedback entry
    feedback_entry = {
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "message": message_data.get("message", ""),
        "player_name": message_data.get("player_name", "Unknown"),
        "response": response,
        "rating": rating,  # 1 = positive, 0 = negative
        "notes": notes,
    }
    
    # Generate a unique filename
    filename = f"feedback_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    filepath = os.path.join(feedback_dir, filename)
    
    # Save feedback to file
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(feedback_entry, f, indent=2)
        
        # Update feedback summary
        summary_file = os.path.join(feedback_dir, "feedback_summary.json")
        
        if os.path.exists(summary_file):
            with open(summary_file, 'r', encoding='utf-8') as f:
                summary = json.load(f)
        else:
            summary = {
                "total_responses": 0,
                "positive_feedback": 0,
                "negative_feedback": 0,
                "feedback_ratio": 0.0,
                "recent_feedbacks": []
            }
        
        # Update the summary stats
        summary["total_responses"] += 1
        if rating == 1:
            summary["positive_feedback"] += 1
        else:
            summary["negative_feedback"] += 1
            
        # Calculate ratio
        if summary["total_responses"] > 0:
            summary["feedback_ratio"] = summary["positive_feedback"] / summary["total_responses"]
            
        # Add to recent feedbacks (keep last 10)
        recent_entry = {
            "timestamp": feedback_entry["timestamp"],
            "message_snippet": feedback_entry["message"][:50] + "..." if len(feedback_entry["message"]) > 50 else feedback_entry["message"],
            "rating": rating,
            "filename": filename
        }
        
        summary["recent_feedbacks"].insert(0, recent_entry)
        summary["recent_feedbacks"] = summary["recent_feedbacks"][:10]
        
        # Save updated summary
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2)
            
        return {"success": True, "file": filepath}
    
    except Exception as e:
        print(f"Error saving feedback: {e}")
        return {"error": str(e)}

def get_character_feedback_summary(character_name):
    """Get the feedback summary for a character"""
    if not character_name:
        return {"error": "No character specified"}
    
    feedback_dir = os.path.join(FEEDBACK_DIR, character_name.replace(' ', '_'))
    summary_file = os.path.join(feedback_dir, "feedback_summary.json")
    
    if not os.path.exists(summary_file):
        return {
            "character": character_name,
            "total_responses": 0,
            "positive_feedback": 0,
            "negative_feedback": 0,
            "feedback_ratio": 0.0,
            "recent_feedbacks": []
        }
    
    try:
        with open(summary_file, 'r', encoding='utf-8') as f:
            summary = json.load(f)
        
        summary["character"] = character_name
        return summary
    
    except Exception as e:
        print(f"Error reading feedback summary: {e}")
        return {"error": str(e)}

@app.route('/api/feedback/<character>', methods=['POST'])
def submit_feedback(character):
    """Submit feedback for a character response"""
    data = request.json
    rating = data.get('rating', 0)  # 1 = positive, 0 = negative
    response = data.get('response', '')
    message_data = data.get('message_data', {})
    notes = data.get('notes', '')
    
    result = save_feedback(character, message_data, response, rating, notes)
    return jsonify(result)

@app.route('/api/feedback/<character>', methods=['GET'])
def get_feedback(character):
    """Get feedback summary for a character"""
    summary = get_character_feedback_summary(character)
    return jsonify(summary)

@socketio.on('submit_feedback')
def handle_feedback(data):
    """Handle feedback submission through websocket"""
    character = data.get('character', active_character)
    rating = data.get('rating', 0)
    response = data.get('response', '')
    message_data = data.get('message_data', {})
    notes = data.get('notes', '')
    
    result = save_feedback(character, message_data, response, rating, notes)
    emit('feedback_result', result)

@app.route('/api/log_update', methods=['POST'])
def receive_log_update():
    """Handle log updates from remote clients"""
    data = request.json
    client = data.get('client', 'unknown')
    lines = data.get('lines', [])
    
    if not lines:
        return jsonify({'error': 'No log lines provided'}), 400
    
    print(f"Received {len(lines)} log lines from client: {client}")
    
    # Process each line as if it came from local log file
    for line in lines:
        process_new_messages(line + '\n')
    
    return jsonify({'success': True, 'processed': len(lines)})

# Socket.IO endpoint for log updates
@socketio.on('log_update')
def handle_log_update(data):
    """Handle log updates via WebSocket"""
    client = data.get('client', 'unknown')
    lines = data.get('lines', [])
    
    if not lines:
        return
    
    print(f"Received {len(lines)} log lines via WebSocket from client: {client}")
    print(f"Lines: {lines}")
    
    # Process each line
    for line in lines:
        process_new_messages(line + '\n')
    
    # Send confirmation back to the client that sent the logs
    emit('log_update_result', {'success': True, 'processed': len(lines)})
    
    # Also broadcast a system message to all clients that logs were received
    socketio.emit('system_message', {
        'message': f"New logs received from client: {client}",
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

# Load server configuration
def load_server_config():
    """Load server configuration from config.ini"""
    host = '0.0.0.0'  # Default host
    port = 5000       # Default port
    
    try:
        import configparser
        config = configparser.ConfigParser()
        if os.path.exists('config.ini'):
            config.read('config.ini')
            if 'Server' in config:
                if 'HOST' in config['Server']:
                    host = config['Server']['HOST']
                if 'PORT' in config['Server']:
                    port = int(config['Server']['PORT'])
            print(f"Server will bind to {host}:{port}")
    except Exception as e:
        print(f"Error loading server config: {e}")
        print(f"Using default host:port {host}:{port}")
    
    return host, port

@app.route('/edit-character')
def edit_character_form():
    """Render the character edit form"""
    return render_template('edit_character.html')

@app.route('/api/character/<n>/update', methods=['POST'])
def update_character(n):
    """Update an existing character profile"""
    data = request.json
    
    # Validate required fields
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Ensure character exists
    if n not in character_profiles:
        return jsonify({'error': 'Character not found'}), 404
    
    # Update character profile
    result = character_manager.update_profile(n, data)
    
    if 'error' in result:
        return jsonify(result), 400
    
    # Reload all character profiles
    character_profiles.update(character_manager.load_all_profiles())
    
    return jsonify(result)

@app.route('/api/character/<n>/import-json', methods=['POST'])
def import_json_profile(n):
    """Import a character profile from JSON data"""
    # Check if the character exists
    if n not in character_profiles:
        return jsonify({'error': 'Character not found'}), 404

    # Check if there's a file in the request
    if 'json_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
        
    file = request.files['json_file']
    
    # Check if the file is empty
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    # Check if the file is a JSON file
    if not file.filename.lower().endswith('.json'):
        return jsonify({'error': 'File must be in JSON format'}), 400
    
    try:
        # Read the file content
        json_data = file.read().decode('utf-8')
        
        # Parse the JSON
        data = json.loads(json_data)
        
        # Ensure the name matches the current character
        data['name'] = n
        
        # Update the character profile
        result = character_manager.update_profile(n, data)
        
        if 'error' in result:
            return jsonify(result), 400
            
        # Reload character profiles
        character_profiles.update(character_manager.load_all_profiles())
        
        return jsonify({'success': True, 'message': f"Profile for {n} updated from JSON file"})
        
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON format'}), 400
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

# Main entry point
if __name__ == "__main__":
    start_monitor()
    host, port = load_server_config()
    socketio.run(app, host=host, port=port, debug=True)
else:
    # For gunicorn or other WSGI servers
    start_monitor() 