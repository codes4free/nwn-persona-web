# NWNX:EE Chatbot Web Interface

A web-based interface for the NWNX:EE Chatbot, allowing you to monitor game chat and generate AI responses through a browser.

## Features

- Real-time game chat monitoring
- Character profile management
- AI-generated character responses with GPT-4o
- Web interface for selecting and copying responses

## Requirements

- Python 3.8+
- Flask and Flask-SocketIO
- OpenAI API key
- Running instance of Neverwinter Nights Enhanced Edition

## Setup

1. **Clone the repository**

```bash
git clone https://github.com/your-username/nwnx-ee.git
cd nwnx-ee
```

2. **Create and configure environment file**

Create a `.env` file in the root directory with the following contents:

```
OPENAI_API_KEY=your_openai_api_key_here
LOG_FILE_PATH=/path/to/nwclientLog1.txt
USER_ACCOUNT=YourGameAccountName
SECRET_KEY=change_this_to_a_random_secure_string
```

3. **Install dependencies**

```bash
pip install -r requirements-web.txt
```

4. **Start the web application**

```bash
./start_web.sh
```

Or manually:

```bash
python app.py
```

5. **Access the web interface**

Open your browser and navigate to:
```
http://localhost:5000
```

## Usage

1. **Start Neverwinter Nights Enhanced Edition**

Make sure your game is running and logging chat messages to the configured log file.

2. **Monitor Chat**

The web interface will automatically monitor the chat log and display messages in real-time.

3. **Generate Responses**

When a player message is detected, click the "Generate Response" button to create AI character responses.

4. **Copy and Use Responses**

Click the "Copy" button next to any response option to copy it to your clipboard, then paste it into the game chat.

## Configuration

- **Character Profiles**: Character profiles are stored in JSON format in the `character_profiles` directory.
- **Chat History**: Chat logs are saved in the `chat_history` directory.
- **Log File**: The path to the NWN log file is configurable in the `.env` file.

## Troubleshooting

- **Log File Not Found**: Ensure the `LOG_FILE_PATH` in your `.env` file points to the correct location of your NWN client log.
- **No Characters Detected**: Check that your `USER_ACCOUNT` in the `.env` file matches your in-game account name.
- **API Key Issues**: Verify your OpenAI API key has sufficient credits and permissions.

## License

[MIT License](LICENSE) 