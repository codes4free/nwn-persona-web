#!/usr/bin/env python3
"""Optional entrypoint.

This keeps app.py as the primary entry during refactor, but allows running:
    python run.py
"""

from app import app, socketio

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
