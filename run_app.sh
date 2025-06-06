#!/usr/bin/env bash
# Simple script to run the NWNX:EE Chatbot app and restart it whenever it
# stops. Creates a local virtual environment and installs dependencies when
# needed.

set -e
cd "$(dirname "$0")" || exit 1

PYTHON="python3"

if ! python3 -c "import eventlet" >/dev/null 2>&1; then
  echo "Setting up virtual environment and installing dependencies..."
  if [ ! -d ".venv" ]; then
    python3 -m venv .venv
  fi
  if [ ! -x ".venv/bin/pip" ]; then
    .venv/bin/python -m ensurepip --upgrade
  fi
  PYTHON=".venv/bin/python"
  "$PYTHON" -m pip install -q -r requirements.txt
else
  echo "Dependencies already installed."
fi

while true; do
  echo "Starting app..."
  set +e
  "$PYTHON" app.py
  exit_code=$?
  set -e
  echo "App exited with status $exit_code. Restarting in 5 seconds..."
  sleep 5
done
