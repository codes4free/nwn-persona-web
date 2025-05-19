@echo off
echo Starting NWN Log Client...

REM Check if virtual environment exists and use it
if exist venv\Scripts\activate.bat (
    echo Using virtual environment...
    call venv\Scripts\activate.bat
    python nwn_log_client.py
    call venv\Scripts\deactivate.bat
) else (
    echo No virtual environment found, using system Python...
    python nwn_log_client.py
)

pause 