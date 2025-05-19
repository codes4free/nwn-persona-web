#!/bin/bash

# Start the NWNX:EE Chatbot Web Application

# Load environment variables
if [ -f .env ]; then
    echo "Loading environment from .env file"
    export $(grep -v '^#' .env | xargs)
fi

# Check for config.ini
if [ -f config.ini ]; then
    echo "Using configuration from config.ini"
else
    echo "WARNING: config.ini not found, using default settings"
fi

# Check for Python and required packages
if ! command -v python3 &> /dev/null; then
    echo "Python 3 is required but not installed. Please install Python 3."
    exit 1
fi

# Install required packages if needed
if [ ! -f ".packages_installed" ]; then
    echo "Installing required packages..."
    pip install -r requirements-web.txt
    touch .packages_installed
fi

# Create necessary directories
mkdir -p character_profiles chat_history static/css static/js templates feedback_data

# Start the application
echo "Starting NWNX:EE Chatbot Web Application..."
echo "The server is configured to receive logs ONLY via WebSocket/API"
echo "No local log file monitoring is active"
python3 app.py

# Keep the script running
echo "Web application exited. Press Ctrl+C to close this window."
read -r -d '' _ </dev/tty 