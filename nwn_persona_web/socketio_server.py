"""Socket.IO event handlers."""

import datetime
from typing import Callable, Dict

from flask import request, session
from flask_socketio import emit, join_room


def register_socketio_handlers(
    socketio,
    *,
    logger,
    get_character_profiles: Callable[[], Dict],
    online_users: set,
    chat_processing,
    get_openai_api_key,
    save_feedback,
    last_log_update: Dict,
) -> None:
    """Register all Socket.IO handlers."""

    @socketio.on("translate_message")
    def handle_translate_message(data):
        """WebSocket endpoint to translate a message"""
        character_name = data.get("character", session.get("active_character"))
        portuguese_text = data.get("text", "")
        context = data.get("context", None)

        if not character_name or not portuguese_text:
            emit("translation_result", {"error": "Missing character or text"})
            return

        result = chat_processing.translate_custom_message(
            character_name,
            portuguese_text,
            context=context,
            character_profiles=get_character_profiles(),
            get_openai_api_key=get_openai_api_key,
            save_to_history_func=lambda *args, **kwargs: (
                chat_processing.save_to_history(*args, **kwargs, logger=logger)
            ),
            logger=logger,
        )

        # Make sure translated text doesn't have em dashes
        if "translated" in result:
            result["translated"] = chat_processing.remove_em_dashes(
                result["translated"]
            )

        emit("translation_result", result)

    @socketio.on("connect")
    def connect(auth):
        """Handle client connection with more reliable approach"""
        try:
            # Get client IP for logging
            client_ip = request.remote_addr
            logger.info(f"Client connecting from IP: {client_ip}")

            # Store connection info in a more reliable way
            # Use socket ID as identifier instead of session
            socket_id = request.sid

            # Create a default room based on the client's IP or socket ID
            # This avoids relying on Flask sessions
            room_name = f"room_{socket_id}"
            join_room(room_name)
            logger.info(f"Client {socket_id} joined room {room_name}")

            # Check if user credentials are provided in auth param
            username = None
            if auth and isinstance(auth, dict) and "username" in auth:
                username = auth["username"]
                logger.info(f"User identified as: {username}")
                if username:
                    online_users.add(username)
                    socketio.emit("active_users", list(online_users))

            # Always emit connection status to this specific client
            emit(
                "connection_status",
                {
                    "status": "connected",
                    "client_ip": client_ip,
                    "socket_id": socket_id,
                    "username": username,
                },
            )

            # If there's session data, try to use it as fallback
            # But don't rely on it for core functionality
            try:
                if "user" in session and session.get("active_character"):
                    emit(
                        "character_change",
                        {"character": session.get("active_character")},
                    )
            except Exception as e:
                logger.warning(f"Session access failed (non-critical): {e}")

            return True  # Return True to approve the connection
        except Exception as e:
            logger.error(f"Error in connection handler: {e}")
            # Still approve the connection even if there was an error
            return True

    @socketio.on("disconnect")
    def disconnect():
        """Handle client disconnection"""
        if "user" in session:
            online_users.discard(session["user"])
            socketio.emit("active_users", list(online_users))

    @socketio.on("activate_character")
    def handle_activate_character(data):
        """Set active character through websocket"""
        character_name = data.get("character")
        if not character_name:
            emit("activation_result", {"error": "No character specified"})
            return
        if character_name not in get_character_profiles():
            emit("activation_result", {"error": "Character not found"})
            return
        session["active_character"] = character_name
        logger.info(f"Manually activated character via websocket: {character_name}")
        chat_processing.setup_chat_history(character_name, logger=logger)
        emit("character_change", {"character": character_name})
        emit("activation_result", {"success": True, "active_character": character_name})

    @socketio.on("request_ai_reply")
    def handle_ai_reply_request(data):
        """Generate AI reply for a character"""
        character_name = data.get("character", session.get("active_character"))
        player_message = data.get("message", "")
        player_name = data.get("player_name", "Unknown")
        context = data.get("context", None)

        if not character_name or not player_message:
            emit("ai_reply", {"error": "Missing character or message"})
            return

        # Log the request
        logger.info(
            "Generating AI reply for '%s' responding to '%s': '%s'",
            character_name,
            player_name,
            player_message,
        )
        if context and context.get("messages"):
            logger.info(
                "Using context window with %s messages",
                len(context.get("messages", [])),
            )

        # Generate responses with context if available
        responses = chat_processing.generate_in_character_reply(
            character_name,
            player_message,
            context=context,
            character_profiles=get_character_profiles(),
            get_openai_api_key=get_openai_api_key,
            save_to_history_func=lambda *args, **kwargs: (
                chat_processing.save_to_history(*args, **kwargs, logger=logger)
            ),
            logger=logger,
        )

        # Make sure responses don't have em dashes
        responses = [
            chat_processing.remove_em_dashes(response) for response in responses
        ]

        # Save this interaction to history
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        chat_processing.save_to_history(
            character_name,
            f"Request to respond to {player_name}: {player_message}",
            "system",
            timestamp,
            logger=logger,
        )

        emit(
            "ai_reply",
            {
                "character": character_name,
                "responses": responses,
                "original_message": player_message,
                "player_name": player_name,
            },
        )

    @socketio.on("submit_feedback")
    def handle_feedback(data):
        """Handle feedback submission through websocket"""
        character = data.get("character", session.get("active_character"))
        rating = data.get("rating", 0)
        response = data.get("response", "")
        message_data = data.get("message_data", {})
        notes = data.get("notes", "")

        result = save_feedback(character, message_data, response, rating, notes)
        emit("feedback_result", result)

    @socketio.on("log_update")
    def handle_log_update_socket(data):
        """Receive log updates over Socket.IO from NWN Log Client."""
        try:
            logger.info("Received log_update via Socket.IO: %s", data)
            if not isinstance(data, dict):
                logger.warning("log_update payload is not a dict: %s", type(data))
                return

            client = (
                data.get("client")
                or data.get("client_name")
                or data.get("username")
                or "default"
            )
            lines = data.get("lines")
            if lines is None:
                logger.warning("log_update payload missing 'lines'")
                return

            if isinstance(lines, str):
                lines_list = lines.splitlines()
            elif isinstance(lines, list):
                lines_list = lines
            else:
                logger.warning(
                    "log_update 'lines' has unexpected type: %s", type(lines)
                )
                return

            if lines_list:
                logger.info(
                    "log_update (socket) lines preview (up to 5): %s", lines_list[:5]
                )
                last_log_update.update(
                    {
                        "timestamp": datetime.datetime.now().isoformat(),
                        "source": "socketio",
                        "client": client,
                        "lines_preview": lines_list[:5],
                    }
                )
                log_text = "\n".join(lines_list)
                user_characters = {
                    name: profile
                    for name, profile in get_character_profiles().items()
                    if profile.get("owner") == client
                }
                chat_processing.process_new_messages(
                    log_text,
                    client=client,
                    user_characters=user_characters,
                    character_profiles=get_character_profiles(),
                    socketio=socketio,
                    logger=logger,
                )
        except Exception as e:
            logger.error("Error processing Socket.IO log_update: %s", e)

    @socketio.on("socket_ping")
    def handle_socket_ping():
        emit("socket_pong", {"time": datetime.datetime.now().isoformat()})

    @socketio.on("ping")
    def ping():
        """Respond to ping requests"""
        emit(
            "pong",
            {
                "timestamp": datetime.datetime.now().isoformat(),
                "message": "pong",
            },
        )
