# NWNX-EE Chatbot Web Server

This document describes the server-side configuration for the NWNX-EE Chatbot system.

## Overview

The NWNX-EE Chatbot server is a Flask/SocketIO-based web application that:

1. Receives Neverwinter Nights (NWN) chat logs via WebSocket connections
2. Processes these logs to identify player and character messages
3. Generates AI responses using OpenAI's API based on character profiles
4. Provides a web interface for real-time management of conversations

## Important Notes

- **WebSocket Port**: The server listens on port **5000** by default for both HTTP and WebSocket connections
- **Remote Clients Only**: The server does NOT monitor local log files. All logs must be sent from remote Windows clients

## Configuration

### config.ini

The `config.ini` file contains server configuration:

```ini
[Server]
# WebSocket server port (default: 5000)
PORT = 5000
# Host to bind to (0.0.0.0 for all interfaces)
HOST = 0.0.0.0
```

### Environment Variables (.env)

Create a `.env` file with the following configuration:

```
# Required for AI responses
OPENAI_API_KEY=your_api_key_here

# For Flask session security
SECRET_KEY=change_this_to_a_random_string

# Default user account name
USER_ACCOUNT=YourAccountName
```

## Starting the Server

Run the server using:

```bash
./start_web.sh
```

## API Endpoints

### WebSocket Endpoints

- `/socket.io/`: Main WebSocket endpoint for real-time communication
  - Events:
    - `log_update`: Receives log lines from clients
    - `translate_message`: Translates messages
    - `request_ai_reply`: Requests AI-generated replies
    - `activate_character`: Activates a character profile

### HTTP REST API Endpoints

- `/api/log_update`: Receives log updates from remote clients (POST)
- `/api/characters`: Lists available character profiles (GET)
- `/api/character/<name>`: Gets profile for a specific character (GET)
- `/api/character/<name>/activate`: Activates a character profile (POST)
- `/api/history/<character>`: Gets chat history for a character (GET)
- `/api/feedback/<character>`: Submits/retrieves feedback for AI responses (POST/GET)

## Client Agent Files

All Windows client-related files have been moved to the `client_agent_files/` directory to separate client and server concerns. 