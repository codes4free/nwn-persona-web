# NWN Windows Log Client

This client allows Windows users to monitor their local Neverwinter Nights logs and send them to the NWNX-EE chatbot server. Since the server cannot directly access your local NWN logs, this client bridges the gap by monitoring and sending log updates.

## Requirements

- Windows operating system
- Python 3.8+ installed
- Neverwinter Nights Enhanced Edition installed

## Installation

1. Download the files:
   - `nwn_log_client.py`
   - `requirements-windows-client.txt`
   - `start_windows_client.bat`

2. Install the required dependencies:
   ```
   pip install -r requirements-windows-client.txt
   ```

   Recommended: Use a virtual environment to avoid dependency conflicts:
   ```
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements-windows-client.txt
   ```

   If you see warnings about dependency conflicts, you can typically ignore them as long as the installation completes successfully.

3. Configure the client:
   
   When you first run the client, it will create a `config.ini` file with default settings.
   Edit this file to configure your connection:

   ```ini
   [Client]
   SERVER_URL = https://your-domain.com
   API_ENDPOINT = /api/log_update
   WEBSOCKET_URL = wss://your-domain.com/socket.io/?EIO=4&transport=websocket
   NWN_LOG_PATH = C:\Users\YourUser\Documents\Neverwinter Nights\logs\nwclientLog1.txt
   CHECK_INTERVAL = 0.5
   CLIENT_NAME = your-computer-name
   ```

   Alternatively, you can set configuration via command line arguments:
   ```
   python nwn_log_client.py --server https://your-domain.com --log-path "C:\path\to\nwclientLog1.txt"
   ```

   Or use environment variables prefixed with `NWN_CLIENT_`:
   ```
   set NWN_CLIENT_SERVER_URL=https://your-domain.com
   python nwn_log_client.py
   ```

## Usage

1. Make sure your NWNX-EE server is running.

2. Run the client:
   ```
   python nwn_log_client.py
   ```

   Or simply double-click the `start_windows_client.bat` file.

3. Start Neverwinter Nights Enhanced Edition.

4. The client will:
   - Connect to the server via WebSocket (if available)
   - Watch for changes in your NWN log file
   - Send new log entries to the server
   - Automatically reconnect if the connection is lost

## Configuration Options

| Setting | Description | Default |
|---------|-------------|---------|
| SERVER_URL | The base URL of your NWNX-EE server | https://your-domain.com |
| API_ENDPOINT | The API endpoint for log updates | /api/log_update |
| WEBSOCKET_URL | WebSocket URL for real-time updates | wss://your-domain.com/socket.io/?EIO=4&transport=websocket |
| NWN_LOG_PATH | Path to your NWN log file | C:\Users\YourUser\Documents\Neverwinter Nights\logs\nwclientLog1.txt |
| CHECK_INTERVAL | How often to check for log changes (seconds) | 0.5 |
| CLIENT_NAME | Name to identify this client to the server | [your computer name] |

## Troubleshooting

- **Log file not found**: Check that the `NWN_LOG_PATH` in config.ini is correct for your installation
- **Connection errors**: Verify that your server URL is correct and the server is running
- **WebSocket errors**: Check if your server supports WebSocket connections
- **Dependency conflicts**: If you see warnings about dependencies during installation, try using a virtual environment as described above

## Creating a Windows Shortcut

To make it easier to start the client:

1. Right-click in a folder and select "New" → "Shortcut"
2. Enter: `pythonw.exe "C:\path\to\nwn_log_client.py"`
3. Name the shortcut "NWN Log Client"
4. Right-click the shortcut, select "Properties"
5. Add the Start In directory: `C:\path\to\client_folder`
6. Click "OK"

Now you can double-click this shortcut to start the client without showing a console window. 