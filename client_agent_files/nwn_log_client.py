#!/usr/bin/env python3
import os
import time
import requests
import json
import socket
import threading
import argparse
import configparser
import sys

# Default configuration
DEFAULT_CONFIG = {
    "SERVER_URL": "http://nwn-persona.online:5000/",
    "API_ENDPOINT": "/api/log_update",
    "CLIENT_NAME": socket.gethostname(),
    "POLL_INTERVAL": "5"  # Seconds between polling server for updates
}

# Load configuration
def load_config():
    config = DEFAULT_CONFIG.copy()
    
    # Try to load from config.ini file
    parser = configparser.ConfigParser()
    if os.path.exists('config.ini'):
        try:
            parser.read('config.ini')
            if 'Client' in parser:
                for key in config:
                    if key in parser['Client']:
                        config[key] = parser['Client'][key]
            print("Loaded configuration from config.ini")
        except Exception as e:
            print(f"Error loading config.ini: {e}")
    
    # Override with environment variables if set
    for key in config:
        env_value = os.environ.get(f"NWN_CLIENT_{key}")
        if env_value:
            config[key] = env_value
    
    # Override with command line arguments
    parser = argparse.ArgumentParser(description='NWN Log Client')
    parser.add_argument('--server', help='Server URL (e.g., https://your-domain.com)')
    parser.add_argument('--api-endpoint', help='API endpoint (e.g., /api/log_update)')
    parser.add_argument('--client-name', help='Client name to report to server')
    parser.add_argument('--poll-interval', help='Polling interval in seconds')
    
    args = parser.parse_args()
    if args.server:
        config['SERVER_URL'] = args.server
    if args.api_endpoint:
        config['API_ENDPOINT'] = args.api_endpoint
    if args.client_name:
        config['CLIENT_NAME'] = args.client_name
    if args.poll_interval:
        config['POLL_INTERVAL'] = args.poll_interval
    
    # Convert interval to integer
    try:
        config['POLL_INTERVAL'] = int(config['POLL_INTERVAL'])
    except ValueError:
        print(f"Invalid polling interval: {config['POLL_INTERVAL']}, using default 5")
        config['POLL_INTERVAL'] = 5
    
    return config

# Configuration
config = load_config()
SERVER_URL = config['SERVER_URL']
API_ENDPOINT = config['API_ENDPOINT']
CLIENT_NAME = config['CLIENT_NAME']
POLL_INTERVAL = config['POLL_INTERVAL']

# Exit event
exit_event = threading.Event()

# Create a sample config file if it doesn't exist
def create_sample_config():
    if not os.path.exists('config.ini'):
        try:
            with open('config.ini', 'w') as f:
                f.write("[Client]\n")
                for key, value in DEFAULT_CONFIG.items():
                    f.write(f"{key} = {value}\n")
            print("Created sample config.ini file. Please edit it with your actual settings.")
        except Exception as e:
            print(f"Error creating config.ini: {e}")

# Send log lines to the server
def send_log_lines(lines):
    if not lines:
        return False
        
    try:
        # Send via HTTP
        response = requests.post(
            f"{SERVER_URL}{API_ENDPOINT}",
            json={
                "client": CLIENT_NAME,
                "lines": lines
            }
        )
        if response.status_code != 200:
            print(f"Error sending update: {response.text}")
            return False
        else:
            print(f"Sent {len(lines)} lines via HTTP")
            return True
    except Exception as e:
        print(f"Error sending update: {e}")
        return False

# Poll server for messages
def poll_server():
    while not exit_event.is_set():
        try:
            # Get messages from characters endpoint
            response = requests.get(f"{SERVER_URL}/api/characters")
            if response.status_code == 200:
                characters = response.json()
                print(f"Available characters: {', '.join(characters)}")
            else:
                print(f"Error polling server: {response.status_code}")
        except Exception as e:
            print(f"Error polling server: {e}")
        
        # Wait for the next polling interval
        for _ in range(POLL_INTERVAL * 2):  # Check for exit twice per second
            if exit_event.is_set():
                break
            time.sleep(0.5)

# Main application
def main():
    global exit_event
    
    print("NWN Chat Log Client (HTTP Mode)")
    print(f"Configuration:")
    print(f"  Server URL: {SERVER_URL}")
    print(f"  API Endpoint: {API_ENDPOINT}")
    print(f"  Client Name: {CLIENT_NAME}")
    print(f"  Poll Interval: {POLL_INTERVAL} seconds")
    
    # Create sample config.ini if it doesn't exist
    create_sample_config()
    
    # Test server connection
    try:
        response = requests.get(f"{SERVER_URL}/api/characters")
        if response.status_code == 200:
            print("Successfully connected to server!")
            characters = response.json()
            print(f"Available characters: {', '.join(characters)}")
        else:
            print(f"Error connecting to server: {response.status_code}")
            print("Please check your connection settings and try again.")
            return 1
    except Exception as e:
        print(f"Error connecting to server: {e}")
        print("Please check your connection settings and try again.")
        return 1
    
    # Start polling thread
    polling_thread = threading.Thread(target=poll_server)
    polling_thread.daemon = True
    polling_thread.start()
    
    print("Client is now running and connected to the server.")
    print("Press Ctrl+C to exit.")
    
    # Example log lines to send as test
    test_lines = [
        "Norfind: [Talk] Hello, testing the client!",
        "[Account] Character: [Talk] This is an example message"
    ]
    
    # Send example log lines as a test
    print("Sending test log messages...")
    send_log_lines(test_lines)
    
    try:
        # Keep the main thread alive
        while not exit_event.is_set():
            time.sleep(1)
    except KeyboardInterrupt:
        print("Shutting down...")
        exit_event.set()
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 