#!/usr/bin/env python3
# Configure eventlet at the very top - before ANY other imports
import eventlet

eventlet.monkey_patch(socket=True, os=True, select=True, thread=True, time=True)

import datetime
import json
import logging
import os
import re
import secrets
import threading
from typing import Optional

from dotenv import load_dotenv
from flask import (
    Flask,
    abort,
    jsonify,
    render_template,
    request,
    send_from_directory,
    session,
)
from flask_socketio import SocketIO
from werkzeug.utils import secure_filename

import character_manager  # Import the character manager module
from nwn_persona_web import chat_processing
from nwn_persona_web.auth import login_required, register_auth_routes
from nwn_persona_web.settings import (
    CHAT_HISTORY_DIR,
    FEEDBACK_DIR,
    UPLOAD_FOLDER,
    ensure_runtime_dirs,
)
from nwn_persona_web.socketio_server import register_socketio_handlers
from nwn_persona_web.storage import load_users

# Set up more detailed logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Debug: capture last log_update payload for quick verification
LAST_LOG_UPDATE = {
    "timestamp": None,
    "source": None,
    "client": None,
    "lines_preview": None,
}

# Enable detailed Socket.IO and Engine.IO logging
engineio_logger = logging.getLogger("engineio")
engineio_logger.setLevel(logging.DEBUG)
socketio_logger = logging.getLogger("socketio")
socketio_logger.setLevel(logging.DEBUG)

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    secret_key = secrets.token_hex(32)
    logger.warning(
        "SECRET_KEY is not set. Using an ephemeral development key; "
        "set SECRET_KEY in production so sessions survive restarts."
    )
app.config["SECRET_KEY"] = secret_key


def _socketio_cors_origins():
    origins = os.getenv("SOCKETIO_CORS_ORIGINS", "").strip()
    if not origins:
        return None
    if origins == "*":
        logger.warning("SOCKETIO_CORS_ORIGINS is set to '*'. Use only for trusted LANs.")
        return "*"
    return [origin.strip() for origin in origins.split(",") if origin.strip()]


app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE=os.getenv("SESSION_COOKIE_SAMESITE", "Lax"),
    SESSION_COOKIE_SECURE=os.getenv("SESSION_COOKIE_SECURE", "").lower()
    in ("1", "true", "yes"),
    MAX_CONTENT_LENGTH=int(os.getenv("MAX_UPLOAD_BYTES", str(2 * 1024 * 1024))),
)

# Initialize SocketIO with proper configuration
socketio = SocketIO(
    app,
    async_mode="eventlet",
    cors_allowed_origins=_socketio_cors_origins(),
    manage_session=False,
    ping_timeout=20,
    ping_interval=10,
    logger=True,
    engineio_logger=True,
    always_connect=True,
    transports=["polling", "websocket"],
    cookie=False,
    upgrade_timeout=20000,
    max_http_buffer_size=1e7,
    http_compression=True,
    allow_upgrades=False,  # Disable transport upgrades to prevent session issues
    json=None,  # Don't rely on a specific JSON implementation
    max_cookie_size=0,  # Disable cookie size limiting
)

#####################################
## Authentication Routes
#####################################
users = load_users()
register_auth_routes(app, users)


@app.route("/favicon.ico")
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, "static"),
        "favicon.ico",
        mimetype="image/vnd.microsoft.icon",
    )


# OpenAI Configuration: Token will now be provided per session via API Token Configuration.
def get_openai_api_key() -> str:
    """Retrieve the OpenAI API token from the session."""
    token = session.get("openai_token")
    if not token:
        logger.error("OpenAI API token not found in session.")
        abort(
            400,
            description="Missing OpenAI API token. Please set your token using the API Token Configuration.",
        )
    return token


# Global variables
active_character = None
character_profiles = {}  # Will be loaded from character_manager
chat_monitor_thread = None
running = True
last_position = 0
online_users = set()

# Setup directories
ensure_runtime_dirs()


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
    current_user = session.get("user", "")
    if not current_user:
        return None
    character_pattern = re.compile(r"\[" + re.escape(current_user) + r"\] ([^:]+)")
    match = character_pattern.search(line)

    if match:
        character_name = match.group(1)

        if character_name != active_character:
            logger.info(f"Switched to character: {character_name}")
            active_character = character_name
            socketio.emit("character_change", {"character": character_name})

            # Set up chat history for this character
            chat_processing.setup_chat_history(character_name, logger=logger)

        return character_name

    return None


@app.route("/api/translate", methods=["POST"])
@login_required
def translate_message():
    """API endpoint to translate a custom message"""
    data = request.json
    character_name = data.get("character", active_character)
    portuguese_text = data.get("text", "")
    context = data.get("context", None)

    if not character_name:
        return jsonify({"error": "No active character selected"}), 400

    if not portuguese_text:
        return jsonify({"error": "No text provided"}), 400

    result = chat_processing.translate_custom_message(
        character_name,
        portuguese_text,
        context=context,
        character_profiles=character_profiles,
        get_openai_api_key=get_openai_api_key,
        save_to_history_func=lambda *args, **kwargs: chat_processing.save_to_history(
            *args, **kwargs, logger=logger
        ),
        logger=logger,
    )
    return jsonify(result)


@app.route("/")
@login_required
def index():
    """Render the main page"""
    return render_template("index.html")


@app.route("/create-character")
@login_required
def create_character_form():
    """Render the character creation form"""
    return render_template("create_character.html")


@app.route("/api/characters", methods=["GET"])
@login_required
def get_characters():
    """Return list of characters owned by the current user"""
    current_user = session.get("user")
    user_characters = {
        name: profile
        for name, profile in character_profiles.items()
        if profile.get("owner") == current_user
    }
    return jsonify(
        {
            "active_character": session.get("active_character"),
            "characters": list(user_characters.keys()),
        }
    )


@app.route("/api/characters", methods=["POST"])
@login_required
def create_character():
    """Create a new character profile for the current user"""
    data = request.json

    if not data or "name" not in data:
        return jsonify({"error": "Character name is required"}), 400

    # Set the owner to the current user
    data["owner"] = session.get("user")

    result = character_manager.save_profile(data)

    if "error" in result:
        return jsonify(result), 400

    global character_profiles
    character_profiles = character_manager.load_all_profiles()

    return jsonify(result)


@app.route("/api/characters/<name>", methods=["DELETE"])
@login_required
def delete_character(name):
    """Delete a character profile if owned by the current user"""
    global character_profiles
    # First, try to load the profile from disk (handles stale in-memory cache)
    profile = character_manager.get_profile(name)
    if not profile:
        return jsonify({"error": "Character not found"}), 404

    # Check ownership (profile may be on disk but not in-memory)
    if profile.get("owner") != session.get("user"):
        return jsonify({"error": "Unauthorized"}), 403

    if session.get("active_character") == name:
        session.pop("active_character", None)

    # Attempt deletion
    result = character_manager.delete_profile(name)
    if "error" in result:
        return jsonify(result), 400

    # Refresh in-memory cache
    character_profiles = character_manager.load_all_profiles()
    return jsonify(result)


@app.route("/api/character/<n>")
@login_required
def get_character(n):
    """Return character profile if owned by current user"""
    if n in character_profiles:
        if character_profiles[n].get("owner") != session.get("user"):
            return jsonify({"error": "Unauthorized"}), 403
        return jsonify(character_profiles[n])
    return jsonify({"error": "Character not found"}), 404


@app.route("/api/character/<n>/activate", methods=["POST"])
@login_required
def set_active_character(n):
    """Set a character as the active character if owned by current user"""
    if n not in character_profiles:
        return jsonify({"error": "Character not found"}), 404

    if character_profiles[n].get("owner") != session.get("user"):
        return jsonify({"error": "Unauthorized"}), 403

    session["active_character"] = n
    logger.info(f"Manually activated character: {n}")

    chat_processing.setup_chat_history(n, logger=logger)
    socketio.emit("character_change", {"character": n})
    return jsonify({"success": True, "active_character": n})


@app.route("/api/history/<character>")
@login_required
def get_history(character):
    """Return chat history for a character"""
    try:
        user = session.get("user", "default")
        character_dir = os.path.join(
            CHAT_HISTORY_DIR, user, character.replace(" ", "_")
        )
        history_file = os.path.join(character_dir, "chat_history.json")

        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
            return jsonify(history)
        return jsonify([])
    except Exception as e:
        logger.error(f"Error retrieving history: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/character/upload-json", methods=["POST"])
@login_required
def upload_character_json():
    """Endpoint to upload a JSON file for character profile and return its content."""
    if "json_file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
    file = request.files["json_file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if not file.filename.lower().endswith(".json"):
        return jsonify({"error": "File must be in JSON format"}), 400
    try:
        user = session.get("user")
        # Create user-specific upload directory
        user_upload_folder = os.path.join(UPLOAD_FOLDER, user)
        os.makedirs(user_upload_folder, exist_ok=True)
        # Generate a secure filename using timestamp
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = secure_filename(f"{user}_{timestamp}.json")
        file_path = os.path.join(user_upload_folder, filename)
        file.save(file_path)
        # Read and parse file content
        file.seek(0)
        file_content = file.read().decode("utf-8")
        data = json.loads(file_content)
        return (
            jsonify(
                {
                    "success": True,
                    "message": "File uploaded successfully",
                    "data": data,
                    "file_path": file_path,
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Socket.IO events
@app.route("/api/respond", methods=["POST"])
@login_required
def manual_respond():
    """Manually generate a response to a specific message"""
    data = request.json
    character_name = data.get("character", session.get("active_character"))
    player_message = data.get("message", "")
    player_name = data.get("player_name", "Unknown")
    context = data.get("context", None)

    if not character_name or not player_message:
        return jsonify({"error": "Missing character or message"}), 400

    # Generate response with context if available
    responses = chat_processing.generate_in_character_reply(
        character_name,
        player_message,
        context=context,
        character_profiles=character_profiles,
        get_openai_api_key=get_openai_api_key,
        save_to_history_func=lambda *args, **kwargs: chat_processing.save_to_history(
            *args, **kwargs, logger=logger
        ),
        logger=logger,
    )

    # Save to history
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    chat_processing.save_to_history(
        character_name,
        f"Manual request to respond to {player_name}: {player_message}",
        "system",
        timestamp,
        logger=logger,
    )

    return jsonify(
        {
            "character": character_name,
            "responses": responses,
            "original_message": player_message,
            "player_name": player_name,
        }
    )


# Start chat monitor thread
def start_monitor():
    global chat_monitor_thread, running, character_profiles

    # Load character profiles from the manager module
    character_profiles = character_manager.load_all_profiles()
    logger.info(f"Loaded {len(character_profiles)} character profiles")

    # Start the monitor thread
    running = True
    chat_monitor_thread = threading.Thread(
        target=chat_processing.monitor_chat,
        kwargs={"is_running": lambda: running, "logger": logger},
    )
    chat_monitor_thread.daemon = True
    chat_monitor_thread.start()


def save_feedback(character_name, message_data, response, rating, notes=""):
    """Save feedback on a character's response"""
    if not character_name:
        return {"error": "No character specified"}

    # Create character-specific feedback directory
    user = session.get("user", "default")
    feedback_dir = os.path.join(FEEDBACK_DIR, user, character_name.replace(" ", "_"))
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
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(feedback_entry, f, indent=2)

        # Update feedback summary
        summary_file = os.path.join(feedback_dir, "feedback_summary.json")

        if os.path.exists(summary_file):
            with open(summary_file, "r", encoding="utf-8") as f:
                summary = json.load(f)
        else:
            summary = {
                "total_responses": 0,
                "positive_feedback": 0,
                "negative_feedback": 0,
                "feedback_ratio": 0.0,
                "recent_feedbacks": [],
            }

        # Update the summary stats
        summary["total_responses"] += 1
        if rating == 1:
            summary["positive_feedback"] += 1
        else:
            summary["negative_feedback"] += 1

        # Calculate ratio
        if summary["total_responses"] > 0:
            summary["feedback_ratio"] = (
                summary["positive_feedback"] / summary["total_responses"]
            )

        # Add to recent feedbacks (keep last 10)
        recent_entry = {
            "timestamp": feedback_entry["timestamp"],
            "message_snippet": (
                feedback_entry["message"][:50] + "..."
                if len(feedback_entry["message"]) > 50
                else feedback_entry["message"]
            ),
            "rating": rating,
            "filename": filename,
        }

        summary["recent_feedbacks"].insert(0, recent_entry)
        summary["recent_feedbacks"] = summary["recent_feedbacks"][:10]

        # Save updated summary
        with open(summary_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        return {"success": True, "file": filepath}

    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        return {"error": str(e)}


def get_character_feedback_summary(character_name):
    """Get the feedback summary for a character"""
    if not character_name:
        return {"error": "No character specified"}

    user = session.get("user", "default")
    feedback_dir = os.path.join(FEEDBACK_DIR, user, character_name.replace(" ", "_"))
    summary_file = os.path.join(feedback_dir, "feedback_summary.json")

    if not os.path.exists(summary_file):
        return {
            "character": character_name,
            "total_responses": 0,
            "positive_feedback": 0,
            "negative_feedback": 0,
            "feedback_ratio": 0.0,
            "recent_feedbacks": [],
        }

    try:
        with open(summary_file, "r", encoding="utf-8") as f:
            summary = json.load(f)

        summary["character"] = character_name
        return summary

    except Exception as e:
        logger.error(f"Error reading feedback summary: {e}")
        return {"error": str(e)}


register_socketio_handlers(
    socketio,
    logger=logger,
    get_character_profiles=lambda: character_profiles,
    online_users=online_users,
    chat_processing=chat_processing,
    get_openai_api_key=get_openai_api_key,
    save_feedback=save_feedback,
    last_log_update=LAST_LOG_UPDATE,
)


@app.route("/api/feedback/<character>", methods=["POST"])
@login_required
def submit_feedback(character):
    """Submit feedback for a character response"""
    data = request.json
    rating = data.get("rating", 0)  # 1 = positive, 0 = negative
    response = data.get("response", "")
    message_data = data.get("message_data", {})
    notes = data.get("notes", "")

    result = save_feedback(character, message_data, response, rating, notes)
    return jsonify(result)


@app.route("/api/feedback/<character>", methods=["GET"])
@login_required
def get_feedback(character):
    """Get feedback summary for a character"""
    summary = get_character_feedback_summary(character)
    return jsonify(summary)


@app.route("/api/log_update", methods=["POST"])
def log_update():
    """Endpoint to receive log updates from NWN Log Client."""
    try:
        data = request.get_json() or request.form.to_dict()
        app.logger.info("Received log update: %s", data)
        try:
            if isinstance(data, dict) and "lines" in data:
                preview_lines = (
                    data["lines"][:5]
                    if isinstance(data["lines"], list)
                    else data["lines"]
                )
                app.logger.info("log_update lines preview (up to 5): %s", preview_lines)
                LAST_LOG_UPDATE.update(
                    {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "source": "http",
                        "client": (
                            data.get("client", "default")
                            if isinstance(data, dict)
                            else None
                        ),
                        "lines_preview": (
                            preview_lines
                            if isinstance(preview_lines, list)
                            else [preview_lines]
                        ),
                    }
                )
        except Exception as log_err:
            app.logger.warning("Failed to log line preview: %s", log_err)

        if "lines" in data:
            log_text = "\n".join(data["lines"])
            client = data.get("client", "default")

            # Get the user's characters
            user_characters = {
                name: profile
                for name, profile in character_profiles.items()
                if profile.get("owner") == client
            }

            # Process messages with global broadcast
            chat_processing.process_new_messages(
                log_text,
                client=client,
                user_characters=user_characters,
                character_profiles=character_profiles,
                socketio=socketio,
                logger=logger,
            )

        return jsonify(success=True), 200
    except Exception as e:
        app.logger.error("Error processing log update: %s", e)
        return jsonify(success=False, error=str(e)), 500


@app.route("/debug_last_log")
@login_required
def debug_last_log():
    """Quick sanity check to see last log_update received."""
    return jsonify(LAST_LOG_UPDATE)


# Load server configuration
def load_server_config():
    """Load server configuration from config.ini"""
    host = "0.0.0.0"  # Default host for IPv4 (all interfaces)
    port = 5000  # Default port

    try:
        import configparser

        config = configparser.ConfigParser()
        if os.path.exists("config.ini"):
            config.read("config.ini")
            if "Server" in config:
                if "HOST" in config["Server"]:
                    host = config["Server"]["HOST"]
                if "PORT" in config["Server"]:
                    port = int(config["Server"]["PORT"])
            logger.info(f"Server will bind to {host}:{port}")
    except Exception as e:
        logger.error(f"Error loading server config: {e}")
        logger.error(f"Using default host:port {host}:{port}")

    return host, port


@app.route("/edit-character")
@login_required
def edit_character_form():
    """Render the character edit form"""
    return render_template("edit_character.html")


@app.route("/api/character/<n>/update", methods=["POST"])
@login_required
def update_character(n):
    """Update an existing character profile if owned by current user"""
    data = request.json

    if not data:
        return jsonify({"error": "No data provided"}), 400

    if n not in character_profiles:
        return jsonify({"error": "Character not found"}), 404

    if character_profiles[n].get("owner") != session.get("user"):
        return jsonify({"error": "Unauthorized"}), 403

    result = character_manager.update_profile(n, data)

    if "error" in result:
        return jsonify(result), 400

    character_profiles.update(character_manager.load_all_profiles())

    return jsonify(result)


@app.route("/api/character/<n>/import-json", methods=["POST"])
@login_required
def import_json_profile(n):
    """Import a character profile from JSON data if owned by current user"""
    if n not in character_profiles:
        return jsonify({"error": "Character not found"}), 404

    if "json_file" not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files["json_file"]

    if file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    if not file.filename.lower().endswith(".json"):
        return jsonify({"error": "File must be in JSON format"}), 400

    try:
        json_data = file.read().decode("utf-8")
        data = json.loads(json_data)

        data["name"] = n

        if character_profiles[n].get("owner") != session.get("user"):
            return jsonify({"error": "Unauthorized"}), 403

        result = character_manager.update_profile(n, data)

        if "error" in result:
            return jsonify(result), 400

        character_profiles.update(character_manager.load_all_profiles())

        return jsonify(
            {"success": True, "message": f"Profile for {n} updated from JSON file"}
        )

    except json.JSONDecodeError:
        return jsonify({"error": "Invalid JSON format"}), 400
    except Exception as e:
        return jsonify({"error": f"Error processing file: {str(e)}"}), 500


# New endpoint to set the OpenAI API token for the session
@app.route("/set_openai_token", methods=["POST"])
@login_required
def set_openai_token():
    token = request.form.get("openai_token")
    if not token:
        return jsonify({"error": "Missing token"}), 400
    session["openai_token"] = token
    return jsonify({"success": True, "message": "Token set successfully"})


# --- Multi-tone response generation endpoint ---
@app.route("/generate_response", methods=["POST"])
@login_required
def generate_response():
    try:
        # Get the latest user message from the request payload
        data = request.get_json(force=True)
        user_message = data.get("message", "")

        # Retrieve or initialize the chat history from session
        chat_history = session.get("chat_history", [])
        chat_history.append({"role": "User", "message": user_message})

        # Build the conversation text from history
        conversation_text = ""
        for entry in chat_history:
            conversation_text += f"{entry['role']}: {entry['message']}\n"

        # Append instructions for three single-line alternatives
        conversation_text += (
            "\nBased on the above conversation, provide three distinct in-character responses.\n"
            "Each response must be a single line with no line breaks.\n"
            "Label them as:\n"
            "1. \n"
            "2. \n"
            "3. \n"
        )

        # Call the OpenAI API (ensure OPENAI_API_KEY is set in environment variables)
        import os
        import re

        import openai

        openai.api_key = os.getenv("OPENAI_API_KEY")
        response = openai.Completion.create(
            engine="text-davinci-003",
            prompt=conversation_text,
            max_tokens=150,
            temperature=0.7,
            n=1,
        )
        response_text = response.choices[0].text.strip()

        # Parse the response to extract three numbered answers
        matches = re.split(r"\n?\s*\d\.\s*", response_text)
        options = [m.strip() for m in matches[1:4] if m.strip()]
        options = [re.sub(r"\s*\n\s*", " ", opt).strip() for opt in options]
        while len(options) < 3:
            options.append("")

        # Save the updated chat history back to the session
        session["chat_history"] = chat_history
        return jsonify(
            {
                "responses": options,
                "positive": options[0],
                "neutral": options[1],
                "negative": options[2],
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)})


# Debug endpoint to get current server state
@app.route("/debug")
@login_required
def debug_info():
    import datetime

    # If no active character is set, default to the first character owned by the current user
    if not session.get("active_character"):
        current_user = session.get("user")
        for name, profile in character_profiles.items():
            if profile.get("owner") == current_user:
                session["active_character"] = name
                logger.info(f"Default active_character set to {name} in /debug")
                socketio.emit("character_change", {"character": name})
                break

    debug_data = {
        "server_time": datetime.datetime.now().isoformat(),
        "active_character": session.get("active_character"),
        "user": session.get("user"),
        "character_profiles": list(character_profiles.keys()),
    }
    return jsonify(debug_data)


# WebSocket debug page
@app.route("/debug_websocket")
@login_required
def debug_websocket():
    return render_template("debug_websocket.html")


# Add route for context window documentation
@app.route("/context-window")
def context_window_docs():
    """Render the context window documentation page"""
    return render_template("context_window.html")


# Add route for SVG test
@app.route("/svg-test")
def svg_test():
    """Render the SVG test page"""
    return render_template("svg_test.html")


# Add route for embedded SVG version
@app.route("/context-window-embed")
def context_window_embed():
    """Render the context window documentation with embedded SVG"""
    return render_template("context_window_embed.html")


# Health check endpoint
@app.route("/health")
def health_check():
    """Simple health check endpoint to verify server is responsive"""
    return jsonify(
        {
            "status": "ok",
            "timestamp": datetime.datetime.now().isoformat(),
            "socket_io_enabled": True,
            "transport_modes": [
                "polling",
                "websocket",
            ],  # Hardcoded to match initialization
        }
    )


# Socket.IO specific health check endpoint that doesn't require auth
@app.route("/socket_health")
def socket_health_check():
    """Socket.IO specific health check that doesn't require authentication"""
    # Get basic info that should be available, or provide defaults
    async_mode = getattr(socketio, "async_mode", "eventlet")

    # Return a simplified health check response
    return jsonify(
        {
            "status": "ok",
            "timestamp": datetime.datetime.now().isoformat(),
            "async_mode": async_mode,
            "transports": ["polling", "websocket"],  # Hardcoded to match initialization
            "socket_io_enabled": True,
        }
    )


# Test message endpoint for debugging
@app.route("/debug_send_message", methods=["POST"])
@login_required
def debug_send_message():
    """Endpoint to manually send a test message to all clients"""
    try:
        data = request.get_json()
        if not data or "message" not in data:
            return jsonify({"error": "No message provided"}), 400

        test_message = data["message"]
        client = data.get("client", "test_client")
        character = data.get("character", "Test Character")

        # Format a test message like it would come from the game
        test_line = f"[{client}] {character}: [Talk] {test_message}"

        logger.info(f"Sending test message: {test_line}")

        # Create a test user_characters dict
        user_characters = {character: {"owner": client}}

        # Process the message
        chat_processing.process_new_messages(
            test_line,
            client=client,
            user_characters=user_characters,
            character_profiles=character_profiles,
            socketio=socketio,
            logger=logger,
        )

        return jsonify({"success": True, "message": "Test message sent"}), 200
    except Exception as e:
        logger.error(f"Error sending test message: {e}")
        return jsonify({"error": str(e)}), 500


# Simple authenticated Socket.IO test page
@app.route("/socket_test")
@login_required
def socket_test():
    """Simple Socket.IO test page for authenticated operators."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Socket.IO Test - External Mode</title>
        <script src="https://cdn.socket.io/4.6.0/socket.io.min.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; }
            #status { padding: 10px; margin: 10px 0; }
            .success { background-color: #dff0d8; color: #3c763d; }
            .error { background-color: #f2dede; color: #a94442; }
            .pending { background-color: #fcf8e3; color: #8a6d3b; }
            pre { background-color: #f5f5f5; padding: 10px; overflow: auto; }
            table { border-collapse: collapse; width: 100%; margin-top: 20px; }
            th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
            th { background-color: #f5f5f5; }
        </style>
    </head>
    <body>
        <h1>Socket.IO External Connection Test</h1>
        <div id="status" class="pending">Initializing...</div>
        <div>
            <button id="connect">Connect</button>
            <button id="disconnect">Disconnect</button>
            <button id="ping">Ping Server</button>
            <button id="polling">Use Polling Only</button>
        </div>
        <h2>Connection Details</h2>
        <table id="connectionDetails">
            <tr><th>Property</th><th>Value</th></tr>
            <tr><td>Socket ID</td><td id="socketId">-</td></tr>
            <tr><td>Connected</td><td id="isConnected">No</td></tr>
            <tr><td>Transport</td><td id="transport">-</td></tr>
            <tr><td>Client IP</td><td id="clientIp">-</td></tr>
        </table>

        <h2>Connection Log</h2>
        <pre id="log"></pre>

        <script>
            const statusEl = document.getElementById('status');
            const logEl = document.getElementById('log');
            const connectBtn = document.getElementById('connect');
            const disconnectBtn = document.getElementById('disconnect');
            const pingBtn = document.getElementById('ping');
            const pollingBtn = document.getElementById('polling');

            // Connection details elements
            const socketIdEl = document.getElementById('socketId');
            const isConnectedEl = document.getElementById('isConnected');
            const transportEl = document.getElementById('transport');
            const clientIpEl = document.getElementById('clientIp');

            // Log helper
            function log(msg, type) {
                const timestamp = new Date().toISOString();
                logEl.textContent = `[${timestamp}] ${msg}\\n` + logEl.textContent;
                console.log(`[${type || 'info'}] ${msg}`);
            }

            let socket;
            let usePollingOnly = false;

            function initSocket() {
                log('Initializing Socket.IO connection...');
                statusEl.className = 'pending';
                statusEl.textContent = 'Connecting...';

                // Extremely simplified config for external connections
                const opts = {
                    transports: usePollingOnly ? ['polling'] : ['polling', 'websocket'],
                    forceNew: true,
                    timeout: 20000,
                    auth: { username: 'external_user' }
                };

                log(`Using transports: ${opts.transports.join(', ')}`);

                // Create socket
                socket = io(opts);

                socket.on('connect', () => {
                    log('Connected!', 'success');
                    statusEl.className = 'success';
                    statusEl.textContent = 'Connected';
                    socketIdEl.textContent = socket.id || '-';
                    isConnectedEl.textContent = 'Yes';
                    transportEl.textContent = socket.io.engine.transport.name || '-';

                    connectBtn.disabled = true;
                    disconnectBtn.disabled = false;
                    pingBtn.disabled = false;
                });

                socket.on('disconnect', (reason) => {
                    log(`Disconnected: ${reason}`, 'error');
                    statusEl.className = 'error';
                    statusEl.textContent = `Disconnected: ${reason}`;
                    socketIdEl.textContent = '-';
                    isConnectedEl.textContent = 'No';
                    transportEl.textContent = '-';

                    connectBtn.disabled = false;
                    disconnectBtn.disabled = true;
                    pingBtn.disabled = true;
                });

                socket.on('connect_error', (error) => {
                    log(`Connection error: ${error.message}`, 'error');
                    statusEl.className = 'error';
                    statusEl.textContent = `Error: ${error.message}`;
                });

                socket.on('connection_status', (data) => {
                    log(`Server confirmed connection: ${JSON.stringify(data)}`, 'success');
                    if (data.client_ip) {
                        clientIpEl.textContent = data.client_ip;
                    }
                });

                socket.on('socket_pong', (data) => {
                    log(`Received pong: ${JSON.stringify(data)}`, 'success');
                });

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

            pollingBtn.addEventListener('click', () => {
                usePollingOnly = !usePollingOnly;
                pollingBtn.textContent = usePollingOnly ? 'Use All Transports' : 'Use Polling Only';
                log(`Set transport mode to: ${usePollingOnly ? 'polling only' : 'all available'}`);

                if (socket && socket.connected) {
                    log('Disconnecting to apply new transport settings...');
                    socket.disconnect();
                    setTimeout(() => {
                        socket = initSocket();
                    }, 500);
                }
            });

            // Start on page load
            disconnectBtn.disabled = true;
            pingBtn.disabled = true;

            // Initialize with a slight delay
            setTimeout(() => {
                socket = initSocket();
            }, 500);
        </script>
    </body>
    </html>
    """


@app.route("/external_test")
@login_required
def external_test():
    """Ultra-simplified Socket.IO test page for authenticated operators."""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>External Connection Test</title>
        <script src="https://cdn.socket.io/4.6.0/socket.io.min.js"></script>
        <style>
            body { font-family: Arial, sans-serif; margin: 20px; padding: 20px; }
            #log { background-color: #f5f5f5; padding: 10px; height: 300px; overflow: auto; margin-top: 20px; font-family: monospace; }
            button { padding: 10px; margin: 5px; }
            .status { padding: 10px; margin: 10px 0; border-radius: 4px; }
            .success { background-color: #d4edda; color: #155724; }
            .error { background-color: #f8d7da; color: #721c24; }
            .warning { background-color: #fff3cd; color: #856404; }
        </style>
    </head>
    <body>
        <h1>External Connection Test</h1>
        <div id="status" class="status warning">Initializing...</div>

        <div>
            <button id="pollingBtn">Connect (Polling Only)</button>
            <button id="wsBtn">Connect (WebSocket)</button>
            <button id="disconnectBtn">Disconnect</button>
            <button id="pingBtn">Send Ping</button>
            <button id="clearBtn">Clear Log</button>
        </div>

        <div id="log"></div>

        <script>
            // Elements
            const statusEl = document.getElementById('status');
            const logEl = document.getElementById('log');
            const pollingBtn = document.getElementById('pollingBtn');
            const wsBtn = document.getElementById('wsBtn');
            const disconnectBtn = document.getElementById('disconnectBtn');
            const pingBtn = document.getElementById('pingBtn');
            const clearBtn = document.getElementById('clearBtn');

            // Logging
            function log(message, type = 'info') {
                const now = new Date().toISOString();
                const entry = document.createElement('div');
                entry.textContent = `[${now}] ${message}`;
                entry.className = type;
                logEl.insertBefore(entry, logEl.firstChild);
                console.log(`[${type}] ${message}`);
            }

            // Socket reference
            let socket = null;

            // Connect function with specific transport
            function connect(transportType) {
                // Disconnect existing socket if any
                if (socket) {
                    log('Disconnecting existing socket', 'warning');
                    socket.disconnect();
                    socket = null;
                }

                // Update status
                statusEl.className = 'status warning';
                statusEl.textContent = 'Connecting...';

                // Log connection attempt
                log(`Attempting connection with transport: ${transportType}`, 'info');

                // Basic configuration - absolute minimum
                const opts = {
                    transports: transportType === 'polling' ? ['polling'] : ['websocket', 'polling'],
                    forceNew: true,
                    reconnection: false,
                    timeout: 10000
                };

                // Create socket - use '/' as namespace, not the full URL
                try {
                    // Just use empty URL to connect to current server
                    socket = io('', opts);

                    // Connection events
                    socket.on('connect', () => {
                        log(`Connected successfully! ID: ${socket.id}`, 'success');
                        statusEl.className = 'status success';
                        statusEl.textContent = `Connected (${socket.io.engine.transport.name})`;

                        // Update buttons
                        pollingBtn.disabled = true;
                        wsBtn.disabled = true;
                        disconnectBtn.disabled = false;
                        pingBtn.disabled = false;
                    });

                    socket.on('disconnect', (reason) => {
                        log(`Disconnected: ${reason}`, 'error');
                        statusEl.className = 'status error';
                        statusEl.textContent = `Disconnected: ${reason}`;

                        // Update buttons
                        pollingBtn.disabled = false;
                        wsBtn.disabled = false;
                        disconnectBtn.disabled = true;
                        pingBtn.disabled = true;
                    });

                    socket.on('connect_error', (error) => {
                        log(`Connection error: ${error.message}`, 'error');
                        statusEl.className = 'status error';
                        statusEl.textContent = `Error: ${error.message}`;
                    });

                    socket.on('error', (error) => {
                        log(`Socket error: ${error}`, 'error');
                    });

                    // Custom event listeners
                    socket.on('connection_status', (data) => {
                        log(`Server sent status: ${JSON.stringify(data)}`, 'info');
                    });

                    socket.on('socket_pong', (data) => {
                        log(`Received pong: ${JSON.stringify(data)}`, 'success');
                    });

                    // Log transport type
                    log(`Using transport config: ${JSON.stringify(opts.transports)}`, 'info');

                } catch (e) {
                    log(`Error creating socket: ${e.message}`, 'error');
                    statusEl.className = 'status error';
                    statusEl.textContent = `Connection error: ${e.message}`;
                }
            }

            // Button event listeners
            pollingBtn.addEventListener('click', () => connect('polling'));
            wsBtn.addEventListener('click', () => connect('websocket'));

            disconnectBtn.addEventListener('click', () => {
                if (socket) {
                    socket.disconnect();
                    log('Manually disconnected', 'warning');
                }
            });

            pingBtn.addEventListener('click', () => {
                if (socket && socket.connected) {
                    log('Sending ping...', 'info');
                    socket.emit('socket_ping');
                } else {
                    log('Not connected, cannot ping', 'error');
                }
            });

            clearBtn.addEventListener('click', () => {
                logEl.innerHTML = '';
                log('Log cleared', 'info');
            });

            // Initial setup
            disconnectBtn.disabled = true;
            pingBtn.disabled = true;
            log('Page loaded. Click a connect button to start.', 'info');
        </script>
    </body>
    </html>
    """


@app.route("/api/external/ping", methods=["GET"])
def external_ping():
    """Simple endpoint for external clients to test connectivity with no auth"""
    return jsonify(
        {
            "status": "ok",
            "timestamp": datetime.datetime.now().isoformat(),
            "message": "External API endpoint is working",
            "server_info": {
                "socketio_enabled": True,
                "ip": request.remote_addr,
                "cors_allowed": "*",
            },
        }
    )


# --- New Route for Downloading nwnclientlog ---
@app.route("/download/nwnclientlog")
def download_nwnclientlog():
    import os

    from flask import abort, send_from_directory

    # Define the directory where the log file is stored (updated to use the 'download' folder)
    log_directory = os.path.join(app.root_path, "download")
    # Define the log filename; adjust the filename if needed
    log_filename = "NWN Log Client.zip"
    try:
        return send_from_directory(log_directory, log_filename, as_attachment=True)
    except FileNotFoundError:
        abort(404)


# --- End of nwnclientlog download route ---

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
    run_kwargs = {
        "debug": False,
        "allow_unsafe_werkzeug": True,
        "log_output": True,
        "use_reloader": False,
    }
    # Default to HTTP behind Caddy; enable TLS only if explicitly requested.
    if os.getenv("APP_TLS", "").lower() in ("1", "true", "yes"):
        run_kwargs["certfile"] = "/home/d6lab/nwn-persona-web/certs/local.pem"
        run_kwargs["keyfile"] = "/home/d6lab/nwn-persona-web/certs/local-key.pem"

    socketio.run(
        app,
        host=host,
        port=port,
        **run_kwargs,
    )
else:
    # For gunicorn or other WSGI servers
    start_monitor()
