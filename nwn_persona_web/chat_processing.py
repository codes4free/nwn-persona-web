"""Chat processing and AI response helpers."""

import datetime
import json
import os
import re
import time
from typing import Any, Dict, Optional, Tuple

import openai
from flask import session

from .settings import CHAT_HISTORY_DIR, SYSTEM_PATTERN

CONTEXT_SUMMARY_CACHE: Dict[Tuple[str, str], Dict[str, Any]] = {}
CONTEXT_SUMMARY_MAX_MESSAGES = 16
CONTEXT_SUMMARY_REFRESH_TURNS = 4


def setup_chat_history(
    character_name: str, *, user: Optional[str] = None, logger=None
) -> None:
    """Set up directory for character chat history."""
    user = user or session.get("user", "default")
    character_dir = os.path.join(
        CHAT_HISTORY_DIR, user, character_name.replace(" ", "_")
    )
    os.makedirs(character_dir, exist_ok=True)

    # Create empty history file if it doesn't exist
    history_file = os.path.join(character_dir, "chat_history.json")
    if not os.path.exists(history_file):
        with open(history_file, "w", encoding="utf-8") as f:
            json.dump([], f)

    if logger:
        logger.info(f"Set up chat history at: {history_file}")


def save_to_history(
    character_name: str,
    message: str,
    sender: str,
    timestamp: str,
    *,
    user: Optional[str] = None,
    logger=None,
) -> None:
    """Save a message to character chat history."""
    if not character_name:
        return

    user = user or session.get("user", "default")
    character_dir = os.path.join(
        CHAT_HISTORY_DIR, user, character_name.replace(" ", "_")
    )
    os.makedirs(character_dir, exist_ok=True)

    history_file = os.path.join(character_dir, "chat_history.json")

    try:
        if os.path.exists(history_file):
            with open(history_file, "r", encoding="utf-8") as f:
                history = json.load(f)
        else:
            history = []

        history.append({"timestamp": timestamp, "sender": sender, "message": message})

        with open(history_file, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)

    except Exception as e:
        if logger:
            logger.error(f"Error saving to chat history: {e}")


def _extract_player_name(message: str) -> str:
    account_match = re.search(r"\[([^\]]+)\] ([^:]+):", message)
    if account_match:
        return account_match.group(2)

    simple_match = re.match(r"^([^:]+):", message)
    if simple_match:
        return simple_match.group(1)

    return "Unknown"


def _extract_message_text(message: str) -> str:
    talk_match = re.search(r"\[Talk\] (.*)", message)
    if talk_match:
        return talk_match.group(1)

    name_match = re.match(r"^[^:]+: (.*)", message)
    if name_match:
        return name_match.group(1)

    return message


def _load_history_entries(
    character_name: str, *, user: Optional[str] = None, logger=None
) -> list:
    user = user or session.get("user", "default")
    character_dir = os.path.join(
        CHAT_HISTORY_DIR, user, character_name.replace(" ", "_")
    )
    history_file = os.path.join(character_dir, "chat_history.json")
    if not os.path.exists(history_file):
        return []
    try:
        with open(history_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        if logger:
            logger.error(f"Error loading chat history: {e}")
        return []


def _build_recent_context_messages(
    history_entries: list,
    *,
    character_name: str,
    max_messages: int = CONTEXT_SUMMARY_MAX_MESSAGES,
) -> list:
    messages = []
    for entry in reversed(history_entries):
        sender = entry.get("sender")
        if sender not in {"self", "other"}:
            continue
        raw_message = entry.get("message", "")
        if not raw_message:
            continue
        speaker = (
            character_name if sender == "self" else _extract_player_name(raw_message)
        )
        text = _extract_message_text(raw_message).strip()
        if not text:
            continue
        messages.append(
            {
                "speaker": speaker,
                "text": text,
                "timestamp": entry.get("timestamp"),
            }
        )
        if len(messages) >= max_messages:
            break
    messages.reverse()
    return messages


def _summarize_context(
    *,
    messages: list,
    persona: Dict[str, Any],
    get_openai_api_key,
    logger=None,
) -> Dict[str, str]:
    if not messages:
        return {"persona_notes": "", "scene_summary": ""}

    system_prompt = (
        "You summarize roleplay conversations for in-character responses. "
        "Return JSON only with fields: persona_notes, scene_summary. "
        "persona_notes = the character's current tone, commitments, relationships, and "
        "any stated preferences or constraints. "
        "scene_summary = the current topic, recent events, goals, locations, and named entities. "
        "Prioritize factual continuity and commitments first, then tone and style. "
        "Do not invent facts. Keep each field under 80 words. "
        "Use plain sentences, no bullet lists."
    )
    persona_hint = (
        f"Character Persona: {persona.get('persona', '')}\n"
        f"Traits: {', '.join(persona.get('traits', []))}\n"
        f"Mannerisms: {', '.join(persona.get('mannerisms', []))}\n"
    )
    conversation = "\n".join(
        [f"{m.get('speaker')}: {m.get('text')}" for m in messages]
    )
    user_prompt = (
        f"{persona_hint}\nConversation:\n{conversation}\n\nReturn JSON now."
    )

    try:
        openai.api_key = get_openai_api_key()
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=200,
            temperature=0.2,
            n=1,
        )
        content = response.choices[0].message.content.strip()
        parsed = json.loads(content)
        if isinstance(parsed, dict):
            return {
                "persona_notes": str(parsed.get("persona_notes", "")).strip(),
                "scene_summary": str(parsed.get("scene_summary", "")).strip(),
            }
    except Exception as e:
        if logger:
            logger.error(f"Error summarizing context: {e}")
    return {"persona_notes": "", "scene_summary": ""}


def get_context_summary_from_history(
    character_name: str,
    *,
    persona: Dict[str, Any],
    get_openai_api_key,
    user: Optional[str] = None,
    logger=None,
) -> Dict[str, Any]:
    user = user or session.get("user", "default")
    history_entries = _load_history_entries(
        character_name, user=user, logger=logger
    )
    context_messages = _build_recent_context_messages(
        history_entries, character_name=character_name
    )
    history_len = len(history_entries)

    cache_key = (user, character_name)
    cache_entry = CONTEXT_SUMMARY_CACHE.get(cache_key)
    if cache_entry:
        cached_len = cache_entry.get("history_len", 0)
        if history_len >= cached_len and (
            history_len - cached_len < CONTEXT_SUMMARY_REFRESH_TURNS
        ):
            return {
                "summary": cache_entry.get("summary", {}),
                "messages": context_messages,
            }

    summary = _summarize_context(
        messages=context_messages,
        persona=persona,
        get_openai_api_key=get_openai_api_key,
        logger=logger,
    )
    CONTEXT_SUMMARY_CACHE[cache_key] = {
        "summary": summary,
        "history_len": history_len,
        "updated_at": time.time(),
    }
    return {"summary": summary, "messages": context_messages}


def monitor_chat(*, is_running, logger=None) -> None:
    """Monitor chat via WebSocket/API (no local file monitoring)."""
    if logger:
        logger.info("Starting chat monitor - waiting for logs via WebSocket/API")
        logger.info("No local file monitoring - all logs come from remote clients")

    # Just keep the thread alive to receive WebSocket messages
    while is_running():
        time.sleep(5)  # Just sleep, actual processing happens in socket handlers


def process_new_messages(
    data: str,
    *,
    client=None,
    user_characters=None,
    override_character: Optional[str] = None,
    character_profiles: Dict[str, Any],
    socketio,
    logger=None,
) -> None:
    """Process incoming chat messages and emit events to clients."""
    lines = data.strip().split("\n")
    if logger:
        logger.info(f"Processing {len(lines)} new message lines")
        logger.info(
            "process_new_messages: client=%s user_characters=%s override_character=%s",
            client,
            len(user_characters) if user_characters else 0,
            override_character,
        )

    active_char = None

    # Use provided characters or get all if not provided
    if not user_characters and client:
        user_characters = {
            name: profile
            for name, profile in character_profiles.items()
            if profile.get("owner") == client
        }

    # If no active character is set but we have user characters, use the first one
    if user_characters:
        # Get the first character for this user if they have any
        if not active_char and len(user_characters) > 0:
            active_char = next(iter(user_characters.keys()))
            if logger:
                logger.info(
                    "Default active_character set to %s for client %s",
                    active_char,
                    client,
                )

    for line in lines:
        # Skip empty lines
        if not line.strip():
            continue

        # Skip lines with <c> tags - these are item/action notifications, not chat
        if "<c>" in line and "</c>" in line:
            if logger:
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
            if logger:
                logger.info(f"Skipping system menu message: {line[:30]}...")
            continue

        if logger:
            logger.info(f"Processing chat message: {line[:50]}...")

        # Save the message if we have a character
        if character_name:
            # Create in-memory record only - don't rely on session
            try:
                user = client or "default"
                character_dir = os.path.join(
                    CHAT_HISTORY_DIR, user, character_name.replace(" ", "_")
                )
                os.makedirs(character_dir, exist_ok=True)

                history_file = os.path.join(character_dir, "chat_history.json")

                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                if os.path.exists(history_file):
                    with open(history_file, "r", encoding="utf-8") as f:
                        history = json.load(f)
                else:
                    history = []

                history.append(
                    {
                        "timestamp": timestamp,
                        "sender": "self" if is_own_message else "other",
                        "message": line,
                    }
                )

                with open(history_file, "w", encoding="utf-8") as f:
                    json.dump(history, f, indent=2)
            except Exception as e:
                if logger:
                    logger.error(f"Error saving to chat history: {e}")

        # Parse the original message content for player messages
        original_message = None
        if not is_own_message:
            # Only accept full format: [username] char name: [mode] msg
            match = re.match(r"^\[([^\]]+)\] ([^:]+): \[([^\]]+)\] (.*)$", line)
            if match:
                account, char_name, mode, player_message = match.groups()
                if mode == "Talk":
                    original_message = player_message

        # Only display accepted conversation format: [username] char name: [Talk] msg
        talk_match = re.match(r"^\[([^\]]+)\] ([^:]+): \[([^\]]+)\] (.*)$", line)
        if not talk_match:
            # Not a standard chat line; skip without aborting the batch.
            if logger:
                logger.info(f"Skipping non-chat line: {line[:120]}")
            continue
        account, speaker, mode, text = talk_match.groups()
        if mode != "Talk":
            # Only show Talk lines, but keep processing other lines in this batch.
            if logger:
                logger.info(f"Skipping non-Talk line: {line[:120]}")
            continue
        formatted_message = f"<strong>{speaker}:</strong> {text}"

        # Emit the new_message event to all clients
        if logger:
            logger.info("Broadcasting message to all clients")
        socketio.emit(
            "new_message",
            {
                "character": character_name,
                "message": formatted_message,
                "raw_message": line,
                "is_own": is_own_message,
                "original_message": original_message,
                "client": client,
            },
        )

        # Process NPC/player messages for auto-reply
        if not is_own_message:
            # Only accept full format: [username] char name: [mode] msg
            match = re.match(r"^\[([^\]]+)\] ([^:]+): \[([^\]]+)\] (.*)$", line)
            if match:
                account, char_name, mode, player_message = match.groups()
                if mode == "Talk":
                    if logger:
                        logger.info(
                            "Broadcasting player message from %s to all clients",
                            char_name,
                        )
                    socketio.emit(
                        "player_message",
                        {
                            "character": character_name,
                            "player_name": char_name,
                            "message": player_message,
                            "client": client,
                        },
                    )


# Generate AI responses
def generate_in_character_reply(
    character_name,
    player_message,
    num_alternatives=3,
    context=None,
    *,
    character_profiles: Dict[str, Any],
    get_openai_api_key,
    save_to_history_func,
    logger=None,
):
    """Generate AI responses for a character"""
    if not character_name or character_name not in character_profiles:
        return []

    persona = character_profiles[character_name]

    # Set character-specific parameters
    temperature = persona.get(
        "temperature", 0.7
    )  # Get temperature from profile or use 0.7 as default

    # Note: Special case handling for Elvith is maintained but temperature modifier is reduced
    # as the user can now directly control temperature via the UI
    creativity_instruction = ""

    # Check if this is Elvith - if so, reduce creativity/poetry
    if "Elvith" in character_name:
        # Apply a small reduction to the user-defined temperature
        temperature = max(0.1, temperature * 0.9)  # Reduce by 10% but not below 0.1
        creativity_instruction = (
            "\nIMPORTANT NOTE FOR ELVITH MA'FOR: Reduce poetic and flowery language by 30%. "
            "Be more direct and straightforward in conversations. "
            "Focus on clear communication rather than excessive metaphors or philosophical tangents. "
            "While still maintaining your elegant and aristocratic tone, prioritize following the "
            "conversation directly rather than being overly poetic or abstract."
        )

    system_prompt = (
        "You are roleplaying as the following character in Neverwinter Nights EE. "
        "Stay strictly in character, using the persona, background, and style below.\n\n"
        f"Persona: {persona.get('persona', '')}\n"
        f"Background: {persona.get('background', '')}\n"
        f"Appearance: {persona.get('appearance', '')}\n"
        f"Traits: {', '.join(persona.get('traits', []))}\n"
        f"Roleplay Prompt: {persona.get('roleplay_prompt', '')}\n"
        f"Interaction Constraints: {', '.join(persona.get('interaction_constraints', []))}\n"
        f"Mannerisms: {', '.join(persona.get('mannerisms', []))}\n"
        f"Example Dialogue: {persona.get('dialogue_examples', [])}\n"
        f"{creativity_instruction}\n"
        "\nNever break character. Respond to the following as your character would.\n"
        "\nImportant formatting notes: Never use em dashes (—) in your responses. "
        "Use regular hyphens (-) or just avoid them entirely.\n"
        "\nGenerate three distinct, varied in-character replies to the player message."
        "\nEach reply must be a single line (no line breaks)."
        "\nDo not label them as positive/neutral/negative or by length."
        "\nLabel each reply as '1.', '2.', and '3.' respectively."
    )

    # Build messages array with context if available
    messages = [{"role": "system", "content": system_prompt}]

    context_payload = get_context_summary_from_history(
        character_name,
        persona=persona,
        get_openai_api_key=get_openai_api_key,
        logger=logger,
    )
    context_summary = context_payload.get("summary", {}) if context_payload else {}
    if context_summary and (
        context_summary.get("persona_notes") or context_summary.get("scene_summary")
    ):
        summary_text = (
            "Conversation summary for context:\n"
            f"Persona continuity: {context_summary.get('persona_notes', '')}\n"
            f"Scene context: {context_summary.get('scene_summary', '')}"
        )
        messages.append({"role": "system", "content": summary_text})

    # Add conversation context if available
    if context and context.get("messages") and len(context.get("messages", [])) > 0:
        # Log context being used
        if logger:
            logger.info(
                f"Using context with {len(context.get('messages', []))} messages"
            )

        # Add context messages to conversation history
        for msg in context.get("messages", []):
            if msg.get("speaker") and msg.get("text"):
                role = "assistant" if msg.get("speaker") == character_name else "user"
                messages.append(
                    {
                        "role": role,
                        "content": f"{msg.get('speaker')}: {msg.get('text')}",
                    }
                )

        # Add a separator after context
        messages.append(
            {
                "role": "system",
                "content": "The above messages provide context for the conversation. Now respond to the following message:",
            }
        )

    # Add the current message
    messages.append(
        {"role": "user", "content": f"Player says: {player_message}\nYour replies:"}
    )

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
        matches = re.split(r"\n?\s*\d\.\s*", content)
        # The first split part is before '1.', so ignore it
        options = [m.strip() for m in matches[1:4] if m.strip()]
        options = [re.sub(r"\s*\n\s*", " ", opt).strip() for opt in options]

        # Record AI responses in history
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for idx, reply in enumerate(options, 1):
            save_to_history_func(
                character_name, f"[AI Option {idx}] {reply}", "ai", timestamp
            )

        return options
    except Exception as e:
        if logger:
            logger.error(f"Error generating AI response: {e}")
        return []


def translate_custom_message(
    character_name,
    portuguese_text,
    *,
    context=None,
    character_profiles: Dict[str, Any],
    get_openai_api_key,
    save_to_history_func,
    logger=None,
):
    """Translate a custom Portuguese message to English using the character's persona"""
    if not character_name or character_name not in character_profiles:
        return {"error": "Character not found"}

    persona = character_profiles[character_name]

    # Set character-specific parameters
    temperature = persona.get(
        "temperature", 0.7
    )  # Get temperature from profile or use 0.7 as default
    creativity_instruction = ""

    # Check if this is Elvith - if so, reduce creativity/poetry
    if "Elvith" in character_name:
        # Apply a small reduction to the user-defined temperature
        temperature = max(0.1, temperature * 0.9)  # Reduce by 10% but not below 0.1
        creativity_instruction = (
            "\nIMPORTANT NOTE FOR ELVITH MA'FOR: Reduce poetic and flowery language by 30%. "
            "Be more direct and straightforward in translations. "
            "Focus on clear communication rather than excessive metaphors or philosophical tangents. "
            "While still maintaining your elegant and aristocratic tone, prioritize direct communication "
            "rather than being overly poetic or abstract."
        )

    system_prompt = (
        "You are roleplaying as the following character in Neverwinter Nights EE. "
        "Use the persona, background and style below to speak as that character, but "
        "prioritize an accurate, concise translation of the meaning.\n\n"
        f"Persona: {persona.get('persona', '')}\n"
        f"Background: {persona.get('background', '')}\n"
        f"Appearance: {persona.get('appearance', '')}\n"
        f"Traits: {', '.join(persona.get('traits', []))}\n"
        f"Roleplay Prompt: {persona.get('roleplay_prompt', '')}\n"
        f"Interaction Constraints: {', '.join(persona.get('interaction_constraints', []))}\n"
        f"Mannerisms: {', '.join(persona.get('mannerisms', []))}\n"
        f"Example Dialogue: {persona.get('dialogue_examples', [])}\n"
        f"{creativity_instruction}\n"
        "\nYou will receive a short message in Portuguese. Your task: produce a faithful, "
        "concise English rendering of the message as this character would say it — "
        "preserve the original meaning and intent, but express it in the character's "
        "voice. Keep the result brief and focused (one to three short sentences).\n"
        "Include ONE physical action (enclosed in asterisks, e.g. *smiles*) and the "
        "spoken line in quotes.\n"
        "Return your answer as JSON with two fields: 'action' (a short action string, "
        "without surrounding whitespace) and 'speech' (the translated English speech). "
        'Example: {"action":"*nods*","speech":"I understand, we will proceed."}\n'
        "Do NOT include extra commentary outside the JSON object. Never use em dashes (—); "
        "use hyphens (-) if needed."
    )
    user_prompt = (
        "I want to roleplay as your character and say something in Portuguese. Please "
        "understand what I mean and express it as your character would: "
        f'"{portuguese_text}"\n\nRespond with an appropriate character action and speech that conveys this meaning.'
    )

    try:
        context_payload = get_context_summary_from_history(
            character_name,
            persona=persona,
            get_openai_api_key=get_openai_api_key,
            logger=logger,
        )
        context_summary = context_payload.get("summary", {}) if context_payload else {}

        messages = [{"role": "system", "content": system_prompt}]

        if context_summary and (
            context_summary.get("persona_notes")
            or context_summary.get("scene_summary")
        ):
            summary_text = (
                "Conversation summary for context:\n"
                f"Persona continuity: {context_summary.get('persona_notes', '')}\n"
                f"Scene context: {context_summary.get('scene_summary', '')}"
            )
            messages.append({"role": "system", "content": summary_text})

        if context and context.get("messages") and len(context.get("messages", [])) > 0:
            if logger:
                logger.info(
                    "Using context window with %s messages for translation",
                    len(context.get("messages", [])),
                )
            for msg in context.get("messages", []):
                if msg.get("speaker") and msg.get("text"):
                    role = (
                        "assistant"
                        if msg.get("speaker") == character_name
                        else "user"
                    )
                    messages.append(
                        {
                            "role": role,
                            "content": f"{msg.get('speaker')}: {msg.get('text')}",
                        }
                    )
            messages.append(
                {
                    "role": "system",
                    "content": "The above messages provide context for the conversation. Now respond to the following request:",
                }
            )

        messages.append({"role": "user", "content": user_prompt})

        openai.api_key = get_openai_api_key()
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            max_tokens=250,
            temperature=temperature,
            n=1,
        )

        # Get the translated message
        translated = response.choices[0].message.content.strip()
        # Remove any em dashes in the response
        translated = translated.replace("—", "-")

        # Try to parse JSON output from the model (preferred)
        parsed = None
        try:
            parsed = json.loads(translated)
        except Exception:
            parsed = None

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if isinstance(parsed, dict) and ("action" in parsed or "speech" in parsed):
            action = parsed.get("action", "").strip()
            speech = parsed.get("speech", "").strip()
            # Normalize action (ensure it's wrapped in asterisks)
            if action and not (action.startswith("*") and action.endswith("*")):
                action = f"*{action.strip('*').strip()}*"

            # Record the structured translation in history
            save_to_history_func(
                character_name,
                f'Custom message interpretation - Original: "{portuguese_text}" '
                f"→ Action: {action} Speech: {speech}",
                "system",
                timestamp,
            )

            return {
                "original": portuguese_text,
                "action": action,
                "speech": speech,
                "character": character_name,
            }
        else:
            # Fallback: try to extract speech from quoted text and action from asterisks or surrounding text
            speech = ""
            action = ""

            # Try to find the first quoted substring (double or single quotes)
            quote_match = re.search(r"[\"\'](.*?)[\"\']", translated)
            if quote_match:
                speech = quote_match.group(1).strip()

            # Try to find an action enclosed in asterisks
            action_match = re.search(r"\*(.*?)\*", translated)
            if action_match:
                action = f"*{action_match.group(1).strip()}*"
            else:
                # If no asterisk action, derive action from the non-quoted part
                non_quoted = re.sub(r"[\"\'].*?[\"\']", "", translated).strip()
                # Remove any trailing punctuation
                non_quoted = re.sub(r"^[\:\-\s]+|[\:\-\s]+$", "", non_quoted)
                if non_quoted:
                    # Use the first sentence or phrase as an action
                    first_sentence = re.split(r"[\.\!\?]\s+", non_quoted)[0].strip()
                    if first_sentence:
                        # Wrap in asterisks
                        action = f"*{first_sentence}*"

            # If we found both action and speech, record as structured translation
            if speech or action:
                save_to_history_func(
                    character_name,
                    f'Custom message interpretation - Original: "{portuguese_text}" '
                    f"→ Action: {action} Speech: {speech}",
                    "system",
                    timestamp,
                )

                return {
                    "original": portuguese_text,
                    "action": action,
                    "speech": speech,
                    "character": character_name,
                }

            # Otherwise, store the raw translated text and return it
            save_to_history_func(
                character_name,
                f'Custom message interpretation - Original: "{portuguese_text}" '
                f"→ As character: "
                f'"{translated}"',
                "system",
                timestamp,
            )

            return {
                "original": portuguese_text,
                "translated": translated,
                "character": character_name,
            }
    except Exception as e:
        if logger:
            logger.error(f"Error translating message: {e}")
        return {"error": str(e)}


# Helper function to clean em dashes from any text
def remove_em_dashes(text):
    """Replace em dashes with hyphens in text"""
    if text:
        return text.replace("—", "-")
    return text
