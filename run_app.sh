#!/usr/bin/env bash
# Simple script to run the NWNX:EE Chatbot app and automatically restart
# if it stops. Useful for basic development or testing environments.

# Always run from the script's directory
cd "$(dirname "$0")" || exit 1

while true; do
  echo "Starting app..."
  python3 app.py
  exit_code=$?
  echo "App exited with status $exit_code. Restarting in 5 seconds..."
  sleep 5
done
