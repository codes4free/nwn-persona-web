#!/bin/bash

# Check if xdotool is installed
if ! command -v xdotool &> /dev/null; then
    echo "xdotool is not installed. Installing..."
    sudo apt update
    sudo apt install -y xdotool
    
    if [ $? -ne 0 ]; then
        echo "Failed to install xdotool. Please install it manually."
        exit 1
    fi
    
    echo "xdotool installed successfully."
fi

# Check if F: drive is mounted
if [ ! -d "/mnt/f" ]; then
    echo "F: drive not mounted. Attempting to mount..."
    sudo mkdir -p /mnt/f
    sudo mount -t drvfs F: /mnt/f
    
    if [ $? -ne 0 ]; then
        echo "Failed to mount F: drive. Please mount it manually."
        exit 1
    fi
    
    echo "F: drive mounted successfully."
fi

# Check if log directory exists
if [ ! -d "/mnt/f/OneDrive/Documentos/Neverwinter Nights/logs" ]; then
    echo "Warning: Log directory not found. Make sure the path is correct."
    echo "Expected: /mnt/f/OneDrive/Documentos/Neverwinter Nights/logs"
fi

# Make sure the script is executable
chmod +x nwnx_chatbot.py

# Check if colorama is installed
pip show colorama > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "Installing required Python packages..."
    pip install -r requirements.txt
fi

# Run the chatbot
echo "Starting NWNX:EE Chatbot..."
python3 nwnx_chatbot.py 