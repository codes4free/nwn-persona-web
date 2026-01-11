#!/usr/bin/env bash
set -e

# Run from the script's directory
cd "$(dirname "$0")" || exit 1

PYTHON="python3"

# If eventlet isn't importable, create a local venv and install requirements
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
