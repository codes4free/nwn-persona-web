# NWNX:EE Chatbot

A Python-based chatbot for Neverwinter Nights Enhanced Edition that monitors chat logs and helps send messages to the game.

## Features

- Real-time monitoring of NWN chat logs
- Message sending with previews and confirmation
- System message filtering
- Multi-character support with automatic detection
- Character-specific chat history logging
- Character persona profiles to maintain character personalities
- Color-coded message display
- Windows log client for remote monitoring support

## Prerequisites

- WSL Ubuntu installed on Windows
- Python 3.7+ installed in WSL
- Neverwinter Nights Enhanced Edition configured to output chat logs
- X server running on Windows (for xdotool to work)

## Setup

1. Make sure Neverwinter Nights is set to log chat to: `{userdocs}\Neverwinter Nights\logs\nwclientLog1.txt`

2. Install the required packages:
   ```
   sudo apt install -y xdotool
   pip install -r requirements.txt
   ```

3. If WSL cannot access your Windows F: drive, you need to mount it:
   ```
   sudo mkdir -p /mnt/f
   sudo mount -t drvfs F: /mnt/f
   ```

4. Make sure you have an X server running on Windows for xdotool to work. 
   Some options include:
   - VcXsrv (https://sourceforge.net/projects/vcxsrv/)
   - Xming (https://sourceforge.net/projects/xming/)
   
   After installing one of these, make sure to set your DISPLAY variable:
   ```
   export DISPLAY=:0
   ```
   
## Remote Windows Client

For players who can't access the chatbot server directly from their Windows machines, we provide a Windows client that can:

1. Monitor NWN log files on a Windows machine
2. Send logs to a remote server via HTTP or WebSocket
3. Allow the server to process chat logs as if they were local

See the `README-windows-client.md` file for installation and setup instructions.

## Usage

1. Make sure Neverwinter Nights is running and you're logged in with your character.

2. Run the chatbot:
   ```
   ./start_chatbot.sh
   ```

3. The chatbot will monitor the chat log file and display incoming messages.

4. To send a message:
   - Enter your message when prompted
   - Review the message banner
   - Confirm sending with 'y'
   - When prompted, quickly focus on the Neverwinter Nights window (you have 3 seconds)

5. To view chat history:
   - Type 'h' at the message prompt to view the last 20 messages for the current character
   - Chat history is saved in character-specific folders within the 'chat_history' directory

6. To manage character personas:
   - Type 'p' to view or edit the current character's persona
   - Type 'c' to list all characters with profiles
   - Type 'show [character name]' to view a specific character's persona

7. To exit the program, type 'q' at the message prompt or press Ctrl+C.

8. To generate an AI-powered in-character reply:
   - Type `a <player message>` at the prompt (e.g., `a What do you think of Barovia?`)
   - The AI will generate a reply using the current character's persona and offer to send it in-game.

## Multi-Character Support

The chatbot now automatically detects which character you're playing and maintains separate:

1. **Chat logs** - Each character has their own chat history folder with timestamped log files
2. **Persona profiles** - Define and maintain unique personalities for each character

When you play with a new character for the first time, the chatbot will:
- Detect the character name from the chat logs
- Create a new persona profile for that character
- Prompt you to customize the character's persona
- Create character-specific chat logs

## Character Personas

Each character can have a detailed persona that includes:

- **Persona** - A brief description of their personality and mannerisms
- **Background** - Character history and lore
- **Appearance** - Physical description
- **Traits** - Key personality traits
- **Notes** - Any additional information you want to record

Character profiles are stored as JSON files in the `character_profiles` directory.

## Configuration

Edit the following variables in `nwnx_chatbot.py` to match your setup:

- `LOG_FILE_PATH`: Path to your NWN chat log file
- `USER_ACCOUNT`: Your game account name (used to identify your characters)
- `SYSTEM_PATTERN`: Regex pattern to identify system messages
- `CHAT_HISTORY_ENABLED`: Set to True/False to enable/disable chat history
- `CHAT_HISTORY_DIR`: Directory to store chat history files
- `CHAT_HISTORY_FORMAT`: Timestamp format for chat history filenames
- `CHARACTER_PROFILES_DIR`: Directory to store character profile JSON files
- `DEFAULT_PROFILE`: Default template for new character profiles

## Chat History

Chat history is automatically saved to timestamped files in character-specific folders within the `chat_history` directory. Each chat message is recorded with:

- Timestamp
- [SELF] prefix for your own messages
- Complete message text

## Web Interface

To start the web interface:

```
./start_web.sh
```

This will start a Flask web server that allows you to:
- View chat logs for each character
- Generate AI replies through the browser
- Submit feedback on AI responses 

## OpenAI API Token Configuration

This application uses OpenAI's API (via the GPT-4 model) to generate in-character responses and translate custom messages. For security reasons, each user must provide their own OpenAI API token using the provided UI on the main page.

To obtain an API token, visit [OpenAI API Keys](https://platform.openai.com/account/api-keys) and generate a new token.

For development purposes, you can set the environment variable `OPENAI_API_KEY` in your `.env` file. However, this is not recommended for production as it exposes your personal token.

## Troubleshooting

1. **Log file not found**: Make sure the Windows path is correctly mounted in WSL

2. **xdotool not working**: 
   - Make sure an X server is running on your Windows system
   - Check that your DISPLAY environment variable is set correctly
   - Try running: `xdotool getactivewindow` to test if X11 is working

3. **Game not receiving input**: Make sure the game window is active when sending messages

4. **Chat history errors**: Make sure you have write permissions in the directory where the script is running

5. **Character not detected**: Make sure your account name in the configuration matches your in-game account 

6. **Windows client issues**:
   - Make sure the server URL is correct
   - Check that the log file path is correct
   - See `README-windows-client.md` for specific troubleshooting 