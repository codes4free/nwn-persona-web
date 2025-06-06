#!/usr/bin/env bash
# Simple script to run the NWNX:EE Chatbot app and automatically restart
# if it stops. Useful for basic development or testing environments.

# Always run from the script's directory
cd "$(dirname "$0")" || exit 1

# Install dependencies if required
if ! python3 -c "import eventlet" >/dev/null 2>&1; then
  echo "Installing Python dependencies..."
  python3 -m pip install -q -r requirements.txt
fi

while true; do
  echo "Starting app..."
  python3 app.py
  exit_code=$?
  echo "App exited with status $exit_code. Restarting in 5 seconds..."
  sleep 5
done
