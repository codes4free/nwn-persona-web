#!/usr/bin/env bash
# Simple script to run the NWNX:EE Chatbot app and automatically restart if it
# stops. Creates a local virtual environment if dependencies are missing.

set -e
cd "$(dirname "$0")" || exit 1

PYTHON="python3"

  echo "Setting up virtual environment and installing dependencies..."
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv
  fi
  PYTHON=".venv/bin/python"
  "$PYTHON" -m pip install -q -r requirements.txt
else
  echo "Dependencies already installed."
  "$PYTHON" app.py
  python3 -m pip install -q -r requirements.txt
fi

=======
#master
while true; do
  echo "Starting app..."
  python3 app.py
  exit_code=$?
  echo "App exited with status $exit_code. Restarting in 5 seconds..."
  sleep 5
done
