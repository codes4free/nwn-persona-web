"""Centralized settings and runtime paths."""

import os

CHARACTER_PROFILES_DIR = "character_profiles"
CHAT_HISTORY_DIR = "chat_history"
FEEDBACK_DIR = "feedback_data"
# No local log file path - we only receive logs via WebSocket/API
SYSTEM_PATTERN = r"\[Talk\] (?:What would you like to do\?|Please choose section:|<c>\[.*?\]</c>|Crafting Menu|Back|Cancel)"

USERS_FILE = "users.json"
UPLOAD_FOLDER = "uploads/character_json"


def env_flag(name: str, default: bool = False) -> bool:
    """Return a boolean setting from common environment flag values."""
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "on"}


def ensure_runtime_dirs() -> None:
    """Ensure runtime directories exist."""
    os.makedirs(CHAT_HISTORY_DIR, exist_ok=True)
    os.makedirs(CHARACTER_PROFILES_DIR, exist_ok=True)
    os.makedirs(FEEDBACK_DIR, exist_ok=True)
