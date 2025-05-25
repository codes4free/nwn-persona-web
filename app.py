#!/usr/bin/env python3
# Configure eventlet at the very top - before ANY other imports
import eventlet
eventlet.monkey_patch(socket=True, os=True, select=True, thread=True, time=True)

import os
import re
import json
import time
import datetime
import threading
from flask import (Flask, render_template, request, jsonify, send_from_directory, session, redirect, url_for, flash, abort)
from flask_socketio import SocketIO, emit, join_room
from dotenv import load_dotenv
import openai
import character_manager  # Import the character manager module
from functools import wraps
from werkzeug.utils import secure_filename

import logging
from typing import Any, Dict, List, Optional

# Set up more detailed logging
logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Enable detailed Socket.IO and Engine.IO logging
engineio_logger = logging.getLogger('engineio')
engineio_logger.setLevel(logging.DEBUG)
socketio_logger = logging.getLogger('socketio')
socketio_logger.setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()

# Configuration
CHARACTER_PROFILES_DIR = "character_profiles"
CHAT_HISTORY_DIR = "chat_history"
FEEDBACK_DIR = "feedback_data"
# No local log file path - we only receive logs via WebSocket/API
SYSTEM_PATTERN = r"\[Talk\] (?:What would you like to do\?|Please choose section:|<c>\[.*?\]</c>|Crafting Menu|Back|Cancel)"

# Add persistent user storage at the top of the file (after other imports)
USERS_FILE = 'users.json'

UPLOAD_FOLDER = 'uploads/character_json'

def load_users() -> Dict[str, Any]:
    """Load user accounts from a JSON file."""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return {}
    return {}

def save_users(users: Dict[str, Any]) -> None:
    """Save user accounts to a JSON file."""
    try:
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving users: {e}")

# Initialize Flask app
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "nwnx-chatbot-secret")

# Initialize SocketIO with proper configuration
socketio = SocketIO(
    app, 
    async_mode='eventlet', 
    cors_allowed_origins="*", 
    manage_session=True,
    ping_timeout=10,  # Reduce ping timeout
    ping_interval=5,  # More frequent pings
    logger=True,
    engineio_logger=True,
    always_connect=True,  # Allow connections even if the initial transport isn't available
    transports=['polling', 'websocket'],  # Explicitly specify available transports, with polling first
    cookie=False,  # Disable cookies to avoid CORS issues with credentials
    upgrade_timeout=10000,  # Reduce upgrade timeout
    max_http_buffer_size=1e7,  # Increase buffer size
    http_compression=True  # Enable compression
)

#####################################
## Authentication Routes
#####################################
users = load_users()

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username in users and users[username] == password:
            session['user'] = username
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'error')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out', 'success')
    return redirect(url_for('login'))

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        if username in users:
            flash('Username already exists', 'error')
            return redirect(url_for('register'))
        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return redirect(url_for('register'))
        users[username] = password
        save_users(users)
        flash('Registration successful! Please log in.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# OpenAI Configuration: Token will now be provided per session via API Token Configuration.
def get_openai_api_key() -> str:
    """Retrieve the OpenAI API token from the session."""
    token = session.get("openai_token")
    if not token:
        logger.error("OpenAI API token not found in session.")
        abort(400, description="Missing OpenAI API token. Please set your token using the API Token Configuration.")
    return token

# Global variables
active_character = None
character_profiles = {}  # Will be loaded from character_manager
chat_monitor_thread = None
running = True
last_position = 0
online_users = set()

# Setup directories
os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)
os.makedirs(CHARACTER_PROFILES_DIR, exist_ok=True)
os.makedirs(FEEDBACK_DIR, exist_ok=True)

# Load character profiles
# Detect character from log line
def detect_character(line: str) -> Optional[str]:
    """Detect active character from a log line.

    Args:
        line (str): Log line to parse.

    Returns:
        Optional[str]: Detected character name or None.
    """
    global active_character
    current_user = session.get('user', '')
    if not current_user:
        return None
    character_pattern = re.compile(r"\[" + re.escape(current_user) + r"\] ([^:]+)")
    match = character_pattern.search(line)
    
    if match:
        character_name = match.group(1)
        
        if character_name != active_character:
            logger.info(f"Switched to character: {character_name}")
            active_character = character_name
            socketio.emit('character_change', {'character': character_name})
            
            # Set up chat history for this character
            setup_chat_history(character_name)
            
        return character_name
        
    return None

# Setup chat history
def setup_chat_history(character_name: str) -> None:
    """Set up directory for character chat history."""
    user = session.get('user', 'default')
    character_dir = os.path.join(CHAT_HISTORY_DIR, user, character_name.replace(' ', '_'))
    os.makedirs(character_dir, exist_ok=True)
    logger.info(f"Chat history directory for {character_name} of user {user}: {character_dir}")

# Save to chat history
def save_to_history(character_name: str, message: str, sender: str, timestamp: Optional[str] = None) -> None:
    """Save a message to the character's chat history."""
    if not timestamp:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    try:
        user = session.get('user', 'default')
        character_dir = os.path.join(CHAT_HISTORY_DIR, user, character_name.replace(' ', '_'))
        history_file = os.path.join(character_dir, 'chat_history.json')
        
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
        else:
            history = []
        
        history.append({
            "timestamp": timestamp,
            "sender": sender,
            "message": message
        })
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
        
    except Exception as e:
        logger.error(f"Error saving to chat history: {e}")

# Chat monitor function
def monitor_chat() -> None:
    """Monitor chat via WebSocket/API (no local file monitoring)."""
    logger.info("Starting chat monitor - waiting for logs via WebSocket/API")
    logger.info("No local file monitoring - all logs come from remote clients")
    
    # Just keep the thread alive to receive WebSocket messages
    while running:
        time.sleep(5)  # Just sleep, actual processing happens in socket handlers

# Process new messages
def process_new_messages(data: str, client=None, user_characters=None, override_character: Optional[str] = None) -> None:
    """Process incoming chat messages and emit events to clients."""
    lines = data.strip().split('\n')
    logger.info(f"Processing {len(lines)} new message lines")
    
    active_char = None
    
    # Use provided characters or get all if not provided
    if not user_characters and client:
        user_characters = {name: profile for name, profile in character_profiles.items() 
                          if profile.get('owner') == client}
    
    # If no active character is set but we have user characters, use the first one
    if user_characters:
        # Get the first character for this user if they have any
        if not active_char and len(user_characters) > 0:
            active_char = next(iter(user_characters.keys()))
            logger.info(f"Default active_character set to {active_char} for client {client}")
    
    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue
        
        # Skip lines with <c> tags - these are item/action notifications, not chat
        if "<c>" in line and "</c>" in line:
            logger.info(f"Skipping system notification: {line[:30]}...")
            continue
        
        # Use override_character if provided, otherwise detect from line
        character_name = override_character
        if not character_name:
            # For log API updates, use the client's active character
            character_name = active_char
            
            # Try to detect character from line
            for char_name in user_characters.keys():
                if f"[{client}] {char_name}" in line:
                    character_name = char_name
                    break
        
        if not character_name and not client:
            continue
        
        # Check if this is the client's own character's message
        is_own_message = client and f"[{client}]" in line
        
        # Check if this is likely a system menu message
        is_system_message = is_own_message and re.search(SYSTEM_PATTERN, line)
        
        if is_system_message:
            # This is a system message, we'll ignore it
            logger.info(f"Skipping system menu message: {line[:30]}...")
            continue
            
        logger.info(f"Processing chat message: {line[:50]}...")
        
        # Save the message if we have a character
        if character_name:
            # Create in-memory record only - don't rely on session
            try:
                user = client or 'default'
                character_dir = os.path.join(CHAT_HISTORY_DIR, user, character_name.replace(' ', '_'))
                os.makedirs(character_dir, exist_ok=True)
                
                history_file = os.path.join(character_dir, 'chat_history.json')
                
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if os.path.exists(history_file):
                    with open(history_file, 'r', encoding='utf-8') as f:
                        history = json.load(f)
                else:
                    history = []
                
                history.append({
                    "timestamp": timestamp,
                    "sender": "self" if is_own_message else "other",
                    "message": line
                })
                
                with open(history_file, 'w', encoding='utf-8') as f:
                    json.dump(history, f, indent=2)
            except Exception as e:
                logger.error(f"Error saving to chat history: {e}")
        
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
        
        # Emit the new_message event to all clients
        logger.info(f"Broadcasting message to all clients")
        socketio.emit('new_message', {
            'character': character_name,
            'message': formatted_message,
            'raw_message': line,
            'is_own': is_own_message,
            'original_message': original_message,
            'client': client
        })
            
        # Process NPC/player messages for auto-reply
        if not is_own_message:
            # Try to match [Account] Character: [Talk] message
            match = re.match(r"\[([^\]]+)\] ([^:]+): \[Talk\] (.*)", line)
            if match:
                account, char_name, player_message = match.groups()
                logger.info(f"Broadcasting player message from {char_name} to all clients")
                socketio.emit('player_message', {
                    'character': character_name,
                    'player_name': char_name,
                    'message': player_message,
                    'client': client
                })
            else:
                # Fallback: Try to match Name: [Talk] message
                match = re.match(r"([^:]+): \[Talk\] (.*)", line)
                if match:
                    name, player_message = match.groups()
                    logger.info(f"Broadcasting player message from {name} to all clients")
                    socketio.emit('player_message', {
                        'character': character_name,
                        'player_name': name,
                        'message': player_message,
                        'client': client
                    })

# Generate AI responses
def generate_in_character_reply(character_name, player_message, num_alternatives=3, context=None):
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
    
    # Build messages array with context if available
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation context if available
    if context and context.get("messages") and len(context.get("messages", [])) > 0:
        # Log context being used
        logger.info(f"Using context with {len(context.get('messages', []))} messages")
        
        # Add context messages to conversation history
        for msg in context.get("messages", []):
            if msg.get("speaker") and msg.get("text"):
                role = "assistant" if msg.get("speaker") == character_name else "user"
                messages.append({
                    "role": role,
                    "content": f"{msg.get('speaker')}: {msg.get('text')}"
                })
                
        # Add a separator after context
        messages.append({
            "role": "system", 
            "content": "The above messages provide context for the conversation. Now respond to the following message:"
        })
    
    # Add the current message
    messages.append({"role": "user", "content": f"Player says: {player_message}\nYour replies:"})

    try:
        openai.api_key = get_openai_api_key()
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
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
        logger.error(f"Error generating AI response: {e}")
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
        openai.api_key = get_openai_api_key()
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
        logger.error(f"Error translating message: {e}")
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
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please log in to access this page', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    """Render the main page"""
    return render_template('index.html')

@app.route('/create-character')
@login_required
def create_character_form():
    """Render the character creation form"""
    return render_template('create_character.html')

@app.route('/api/characters', methods=['GET'])
@login_required
def get_characters():
    """Return list of characters owned by the current user"""
    current_user = session.get('user')
    user_characters = {name: profile for name, profile in character_profiles.items() if profile.get('owner') == current_user}
    return jsonify({
        'active_character': session.get('active_character'),
        'characters': list(user_characters.keys())
    })

@app.route('/api/characters', methods=['POST'])
@login_required
def create_character():
    """Create a new character profile for the current user"""
    data = request.json
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Character name is required'}), 400
    
    # Set the owner to the current user
    data['owner'] = session.get('user')

    result = character_manager.save_profile(data)
    
    if 'error' in result:
        return jsonify(result), 400
    
    global character_profiles
    character_profiles = character_manager.load_all_profiles()
    
    return jsonify(result)

@app.route('/api/characters/<name>', methods=['DELETE'])
@login_required
def delete_character(name):
    """Delete a character profile if owned by the current user"""
    global character_profiles
    
    if name not in character_profiles:
        return jsonify({'error': 'Character not found'}), 404
    
    # Check ownership
    if character_profiles[name].get('owner') != session.get('user'):
        return jsonify({'error': 'Unauthorized'}), 403

    if session.get('active_character') == name:
        session.pop('active_character', None)
    
    result = character_manager.delete_profile(name)
    
    if 'error' in result:
        return jsonify(result), 400
    
    character_profiles = character_manager.load_all_profiles()
    return jsonify(result)

@app.route('/api/character/<n>')
@login_required
def get_character(n):
    """Return character profile if owned by current user"""
    if n in character_profiles:
        if character_profiles[n].get('owner') != session.get('user'):
            return jsonify({'error': 'Unauthorized'}), 403
        return jsonify(character_profiles[n])
    return jsonify({'error': 'Character not found'}), 404

@app.route('/api/character/<n>/activate', methods=['POST'])
@login_required
def set_active_character(n):
    """Set a character as the active character if owned by current user"""
    if n not in character_profiles:
        return jsonify({'error': 'Character not found'}), 404
    
    if character_profiles[n].get('owner') != session.get('user'):
        return jsonify({'error': 'Unauthorized'}), 403

    session['active_character'] = n
    logger.info(f"Manually activated character: {n}")
    
    setup_chat_history(n)
    socketio.emit('character_change', {'character': n})
    return jsonify({'success': True, 'active_character': n})

@app.route('/api/history/<character>')
def get_history(character):
    """Return chat history for a character"""
    try:
        user = session.get('user', 'default')
        character_dir = os.path.join(CHAT_HISTORY_DIR, user, character.replace(' ', '_'))
        history_file = os.path.join(character_dir, 'chat_history.json')
        
        if os.path.exists(history_file):
            with open(history_file, 'r', encoding='utf-8') as f:
                history = json.load(f)
            return jsonify(history)
        return jsonify([])
    except Exception as e:
        logger.error(f"Error retrieving history: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/character/upload-json', methods=['POST'])
@login_required
def upload_character_json():
    """Endpoint to upload a JSON file for character profile and return its content."""
    if 'json_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    file = request.files['json_file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
    if not file.filename.lower().endswith('.json'):
        return jsonify({'error': 'File must be in JSON format'}), 400
    try:
        user = session.get('user')
        # Create user-specific upload directory
        user_upload_folder = os.path.join(UPLOAD_FOLDER, user)
        os.makedirs(user_upload_folder, exist_ok=True)
        # Generate a secure filename using timestamp
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = secure_filename(f"{user}_{timestamp}.json")
        file_path = os.path.join(user_upload_folder, filename)
        file.save(file_path)
        # Read and parse file content
        file.seek(0)
        file_content = file.read().decode('utf-8')
        data = json.loads(file_content)
        return jsonify({'success': True, 'message': 'File uploaded successfully', 'data': data, 'file_path': file_path}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Socket.IO events
@socketio.on('connect')
def connect(auth):
    """Handle client connection"""
    if 'user' in session:
        room = session['user']
        join_room(room)
        online_users.add(session['user'])
        socketio.emit('active_users', list(online_users), room=room)
    emit('connection_status', {'status': 'connected'})
    if session.get('active_character'):
        emit('character_change', {'character': session.get('active_character')})

@socketio.on('disconnect')
def disconnect():
    """Handle client disconnection"""
    if 'user' in session:
        online_users.discard(session['user'])
        socketio.emit('active_users', list(online_users))

# Add new socketio endpoint for activating a character
@socketio.on('activate_character')
def handle_activate_character(data):
    """Set active character through websocket"""
    character_name = data.get('character')
    if not character_name:
        emit('activation_result', {'error': 'No character specified'})
        return
    if character_name not in character_profiles:
        emit('activation_result', {'error': 'Character not found'})
        return
    session['active_character'] = character_name
    logger.info(f"Manually activated character via websocket: {character_name}")
    setup_chat_history(character_name)
    emit('character_change', {'character': character_name})
    emit('activation_result', {'success': True, 'active_character': character_name})

@socketio.on('request_ai_reply')
def handle_ai_reply_request(data):
    """Generate AI reply for a character"""
    character_name = data.get('character', session.get('active_character'))
    player_message = data.get('message', '')
    player_name = data.get('player_name', 'Unknown')
    context = data.get('context', None)
    
    if not character_name or not player_message:
        emit('ai_reply', {'error': 'Missing character or message'})
        return
    
    # Log the request
    logger.info(f"Generating AI reply for '{character_name}' responding to '{player_name}': '{player_message}'")
    if context and context.get('messages'):
        logger.info(f"Using context window with {len(context.get('messages', []))} messages")
    
    # Generate responses with context if available
    responses = generate_in_character_reply(character_name, player_message, context=context)
    
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
    character_name = data.get('character', session.get('active_character'))
    player_message = data.get('message', '')
    player_name = data.get('player_name', 'Unknown')
    context = data.get('context', None)
    
    if not character_name or not player_message:
        return jsonify({'error': 'Missing character or message'}), 400
    
    # Generate response with context if available
    responses = generate_in_character_reply(character_name, player_message, context=context)
    
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
    logger.info(f"Loaded {len(character_profiles)} character profiles")
    
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
    user = session.get('user', 'default')
    feedback_dir = os.path.join(FEEDBACK_DIR, user, character_name.replace(' ', '_'))
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
        logger.error(f"Error saving feedback: {e}")
        return {"error": str(e)}

def get_character_feedback_summary(character_name):
    """Get the feedback summary for a character"""
    if not character_name:
        return {"error": "No character specified"}
    
    user = session.get('user', 'default')
    feedback_dir = os.path.join(FEEDBACK_DIR, user, character_name.replace(' ', '_'))
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
        logger.error(f"Error reading feedback summary: {e}")
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
    character = data.get('character', session.get('active_character'))
    rating = data.get('rating', 0)
    response = data.get('response', '')
    message_data = data.get('message_data', {})
    notes = data.get('notes', '')
    
    result = save_feedback(character, message_data, response, rating, notes)
    emit('feedback_result', result)

@app.route('/api/log_update', methods=['POST'])
def log_update():
    """Endpoint to receive log updates from NWN Log Client."""
    try:
        data = request.get_json() or request.form.to_dict()
        app.logger.info("Received log update: %s", data)
        
        if 'lines' in data:
            log_text = "\n".join(data['lines'])
            client = data.get('client', 'default')
            
            # Get the user's characters
            user_characters = {name: profile for name, profile in character_profiles.items() 
                              if profile.get('owner') == client}
            
            # Process messages with global broadcast
            process_new_messages(log_text, client=client, user_characters=user_characters)
            
        return jsonify(success=True), 200
    except Exception as e:
        app.logger.error("Error processing log update: %s", e)
        return jsonify(success=False, error=str(e)), 500

# Load server configuration
def load_server_config():
    """Load server configuration from config.ini"""
    host = '0.0.0.0'  # Default host for IPv4 (all interfaces)
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
            logger.info(f"Server will bind to {host}:{port}")
    except Exception as e:
        logger.error(f"Error loading server config: {e}")
        logger.error(f"Using default host:port {host}:{port}")
    
    return host, port

@app.route('/edit-character')
@login_required
def edit_character_form():
    """Render the character edit form"""
    return render_template('edit_character.html')

@app.route('/api/character/<n>/update', methods=['POST'])
@login_required
def update_character(n):
    """Update an existing character profile if owned by current user"""
    data = request.json
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    if n not in character_profiles:
        return jsonify({'error': 'Character not found'}), 404
    
    if character_profiles[n].get('owner') != session.get('user'):
        return jsonify({'error': 'Unauthorized'}), 403

    result = character_manager.update_profile(n, data)
    
    if 'error' in result:
        return jsonify(result), 400
    
    character_profiles.update(character_manager.load_all_profiles())
    
    return jsonify(result)

@app.route('/api/character/<n>/import-json', methods=['POST'])
@login_required
def import_json_profile(n):
    """Import a character profile from JSON data if owned by current user"""
    if n not in character_profiles:
        return jsonify({'error': 'Character not found'}), 404

    if 'json_file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
        
    file = request.files['json_file']
    
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    if not file.filename.lower().endswith('.json'):
        return jsonify({'error': 'File must be in JSON format'}), 400
    
    try:
        json_data = file.read().decode('utf-8')
        data = json.loads(json_data)
        
        data['name'] = n
        
        if character_profiles[n].get('owner') != session.get('user'):
            return jsonify({'error': 'Unauthorized'}), 403

        result = character_manager.update_profile(n, data)
        
        if 'error' in result:
            return jsonify(result), 400
            
        character_profiles.update(character_manager.load_all_profiles())
        
        return jsonify({'success': True, 'message': f"Profile for {n} updated from JSON file"})
        
    except json.JSONDecodeError:
        return jsonify({'error': 'Invalid JSON format'}), 400
    except Exception as e:
        return jsonify({'error': f'Error processing file: {str(e)}'}), 500

# New endpoint to set the OpenAI API token for the session
@app.route("/set_openai_token", methods=["POST"])
def set_openai_token():
    token = request.form.get("openai_token")
    if not token:
        return jsonify({"error": "Missing token"}), 400
    session["openai_token"] = token
    return jsonify({"success": True, "message": "Token set successfully"})

# --- Multi-tone response generation endpoint ---
@app.route('/generate_response', methods=['POST'])
def generate_response():
    try:
        # Get the latest user message from the request payload
        data = request.get_json(force=True)
        user_message = data.get('message', '')

        # Retrieve or initialize the chat history from session
        chat_history = session.get('chat_history', [])
        chat_history.append({'role': 'User', 'message': user_message})

        # Build the conversation text from history
        conversation_text = ""
        for entry in chat_history:
            conversation_text += f"{entry['role']}: {entry['message']}\n"

        # Append instructions for the multi-tone response
        conversation_text += ("\nBased on the above conversation, please provide three distinct responses with the following tones:\n"
                              "Positive Answer: \n"
                              "Neutral Answer: \n"
                              "Negative Answer: \n")

        # Call the OpenAI API (ensure OPENAI_API_KEY is set in environment variables)
        import openai, os, re
        openai.api_key = os.getenv('OPENAI_API_KEY')
        response = openai.Completion.create(
            engine='text-davinci-003',
            prompt=conversation_text,
            max_tokens=150,
            temperature=0.7,
            n=1
        )
        response_text = response.choices[0].text.strip()

        # Parse the response to extract the three tone answers
        pos_match = re.search(r"Positive Answer:\s*(.*?)\n(?:Neutral Answer:|Negative Answer:|$)", response_text, re.DOTALL)
        neu_match = re.search(r"Neutral Answer:\s*(.*?)\n(?:Negative Answer:|$)", response_text, re.DOTALL)
        neg_match = re.search(r"Negative Answer:\s*(.*)", response_text, re.DOTALL)

        positive = pos_match.group(1).strip() if pos_match else ""
        neutral = neu_match.group(1).strip() if neu_match else ""
        negative = neg_match.group(1).strip() if neg_match else ""

        # Save the updated chat history back to the session
        session['chat_history'] = chat_history
        return jsonify({
            'positive': positive,
            'neutral': neutral,
            'negative': negative
        })
    except Exception as e:
        return jsonify({'error': str(e)})

# Debug endpoint to get current server state
@app.route('/debug')
def debug_info():
    import datetime
    # If no active character is set, default to the first character owned by the current user
    if not session.get('active_character'):
        current_user = session.get('user')
        for name, profile in character_profiles.items():
            if profile.get('owner') == current_user:
                session['active_character'] = name
                logger.info(f"Default active_character set to {name} in /debug")
                socketio.emit('character_change', {'character': name})
                break

    debug_data = {
        "server_time": datetime.datetime.now().isoformat(),
        "active_character": session.get('active_character'),
        "user": session.get('user'),
        "character_profiles": list(character_profiles.keys())
    }
    return jsonify(debug_data)

# WebSocket debug page
@app.route('/debug_websocket')
def debug_websocket():
    return render_template('debug_websocket.html')

# Add route for context window documentation
@app.route('/context-window')
def context_window_docs():
    """Render the context window documentation page"""
    return render_template('context_window.html')

# Health check endpoint
@app.route('/health')
def health_check():
    """Simple health check endpoint to verify server is responsive"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.datetime.now().isoformat(),
        'socket_io_enabled': True,
        'transport_modes': socketio.transport_methods
    })

# Socket.IO specific health check endpoint that doesn't require auth
@app.route('/socket_health')
def socket_health_check():
    """Socket.IO specific health check that doesn't require authentication"""
    # Create a simple ping event handler if it doesn't exist
    if not hasattr(socketio.handlers[0], 'ping_pong_handler_added'):
        @socketio.on('socket_ping')
        def handle_socket_ping():
            emit('socket_pong', {'time': datetime.datetime.now().isoformat()})
        socketio.handlers[0].ping_pong_handler_added = True
        
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.datetime.now().isoformat(),
        'socket_io_version': socketio.socketio_version,
        'engineio_version': socketio.server.eio.engineio_version,
        'async_mode': socketio.async_mode,
        'cors_allowed_origins': socketio.server.cors_allowed_origins,
        'ping_interval': socketio.server.eio.ping_interval,
        'ping_timeout': socketio.server.eio.ping_timeout,
        'transports': socketio.transports
    })

# Test message endpoint for debugging
@app.route('/debug_send_message', methods=['POST'])
def debug_send_message():
    """Endpoint to manually send a test message to all clients"""
    try:
        data = request.get_json()
        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400
            
        test_message = data['message']
        client = data.get('client', 'test_client')
        character = data.get('character', 'Test Character')
        
        # Format a test message like it would come from the game
        test_line = f"[{client}] {character}: [Talk] {test_message}"
        
        logger.info(f"Sending test message: {test_line}")
        
        # Create a test user_characters dict
        user_characters = {character: {'owner': client}}
        
        # Process the message
        process_new_messages(test_line, client=client, user_characters=user_characters)
        
        return jsonify({'success': True, 'message': 'Test message sent'}), 200
    except Exception as e:
        logger.error(f"Error sending test message: {e}")
        return jsonify({'error': str(e)}), 500

# Ping handler for testing WebSocket connection
@socketio.on('ping')
def handle_ping(data=None):
    """Handle ping event for testing connection latency"""
    emit('pong', {'time': datetime.datetime.now().isoformat()})

# Simple Socket.IO test page (no auth required)
@app.route('/socket_test')
def socket_test():
    """Simple Socket.IO test page that doesn't require authentication"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Basic Socket.IO Test</title>
        <script src="https://cdn.socket.io/4.6.0/socket.io.min.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            #status { padding: 10px; margin: 10px 0; }
            .success { background-color: #dff0d8; color: #3c763d; }
            .error { background-color: #f2dede; color: #a94442; }
            .pending { background-color: #fcf8e3; color: #8a6d3b; }
            pre { background-color: #f5f5f5; padding: 10px; overflow: auto; }
        </style>
    </head>
    <body>
        <h1>Basic Socket.IO Test</h1>
        <div id="status" class="pending">Connecting...</div>
        <button id="connect">Connect</button>
        <button id="disconnect">Disconnect</button>
        <button id="ping">Ping Server</button>
        <h2>Connection Log</h2>
        <pre id="log"></pre>
        
        <script>
            const statusEl = document.getElementById('status');
            const logEl = document.getElementById('log');
            const connectBtn = document.getElementById('connect');
            const disconnectBtn = document.getElementById('disconnect');
            const pingBtn = document.getElementById('ping');
            
            // Log helper
            function log(msg, type) {
                const timestamp = new Date().toISOString();
                logEl.textContent += `[${timestamp}] ${msg}\\n`;
                console.log(`[${type || 'info'}] ${msg}`);
            }
            
            let socket;
            
            function initSocket() {
                log('Initializing Socket.IO with minimal config...');
                statusEl.className = 'pending';
                statusEl.textContent = 'Connecting...';
                
                // Most minimal Socket.IO config
                socket = io({
                    transports: ['polling'],
                    reconnectionAttempts: 3,
                    timeout: 5000,
                    forceNew: true,
                    upgrade: false
                });
                
                socket.on('connect', () => {
                    log('Connected!', 'success');
                    statusEl.className = 'success';
                    statusEl.textContent = 'Connected';
                    connectBtn.disabled = true;
                    disconnectBtn.disabled = false;
                    pingBtn.disabled = false;
                });
                
                socket.on('disconnect', (reason) => {
                    log(`Disconnected: ${reason}`, 'error');
                    statusEl.className = 'error';
                    statusEl.textContent = `Disconnected: ${reason}`;
                    connectBtn.disabled = false;
                    disconnectBtn.disabled = true;
                    pingBtn.disabled = true;
                });
                
                socket.on('connect_error', (error) => {
                    log(`Connection error: ${error.message}`, 'error');
                    statusEl.className = 'error';
                    statusEl.textContent = `Error: ${error.message}`;
                });
                
                socket.on('socket_pong', (data) => {
                    log(`Received pong: ${JSON.stringify(data)}`, 'success');
                });
                
                // Automatically try to connect
                return socket;
            }
            
            // Event listeners
            connectBtn.addEventListener('click', () => {
                if (socket && socket.connected) {
                    log('Already connected');
                    return;
                }
                socket = initSocket();
            });
            
            disconnectBtn.addEventListener('click', () => {
                if (socket) {
                    socket.disconnect();
                    log('Manually disconnected');
                }
            });
            
            pingBtn.addEventListener('click', () => {
                if (socket && socket.connected) {
                    log('Sending ping...');
                    socket.emit('socket_ping');
                } else {
                    log('Not connected, cannot ping', 'error');
                }
            });
            
            // Start on page load
            disconnectBtn.disabled = true;
            pingBtn.disabled = true;
            
            // Initialize on page load with a delay
            setTimeout(() => {
                socket = initSocket();
            }, 500);
        </script>
    </body>
    </html>
    '''

# Main entry point
if __name__ == "__main__":
    # Check if eventlet is properly patched
    logger.info("Checking eventlet monkey patching status:")
    import socket
    logger.info(f"socket.socket patched: {hasattr(socket.socket, '_eventlet_patched')}")
    
    # Start monitor thread
    start_monitor()
    
    # Load server configuration
    host, port = load_server_config()
    
    logger.info(f"Starting server on {host}:{port}")
    
    # Run with eventlet
    socketio.run(app, 
                 host=host, 
                 port=port, 
                 debug=True, 
                 allow_unsafe_werkzeug=True,
                 log_output=True)
else:
    # For gunicorn or other WSGI servers
    start_monitor() 