"""Persistence helpers (users, history, feedback)."""

import json
import logging
import os
from typing import Any, Dict

from .settings import USERS_FILE

logger = logging.getLogger(__name__)


def load_users() -> Dict[str, Any]:
    """Load user accounts from a JSON file."""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading users: {e}")
            return {}
    return {}


def save_users(users: Dict[str, Any]) -> None:
    """Save user accounts to a JSON file."""
    try:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)
    except Exception as e:
        logger.error(f"Error saving users: {e}")
