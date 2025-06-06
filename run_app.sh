#!/usr/bin/env bash
# ld0mdw-codex/create-script-to-run-and-restart-app
# Simple script to run the NWNX:EE Chatbot app and automatically restart if it
# stops. Creates a local virtual environment if dependencies are missing.

set -e
cd "$(dirname "$0")" || exit 1

PYTHON="python3"

if ! python3 -c "import eventlet" >/dev/null 2>&1; then
  echo "Setting up virtual environment and installing dependencies..."
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv
  fi
  PYTHON=".venv/bin/python"
  "$PYTHON" -m pip install -q -r requirements.txt
else
  echo "Dependencies already installed."
fi

while true; do
  echo "Starting app..."
  "$PYTHON" app.py
=======
# Simple script to run the NWNX:EE Chatbot app and automatically restart
# if it stops. Useful for basic development or testing environments.

# Always run from the script's directory
cd "$(dirname "$0")" || exit 1

#nb6znh-codex/create-script-to-run-and-restart-app
# Install dependencies if required
if ! python3 -c "import eventlet" >/dev/null 2>&1; then
  echo "Installing Python dependencies..."
  python3 -m pip install -q -r requirements.txt
fi

=======
#master
while true; do
  echo "Starting app..."
  python3 app.py
#master
  exit_code=$?
  echo "App exited with status $exit_code. Restarting in 5 seconds..."
  sleep 5
done
