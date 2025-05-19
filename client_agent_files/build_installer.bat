@echo off
echo =======================================
echo NWN Log Client - Installer Builder
echo =======================================

REM Check if required files exist
if not exist nwn_log_client.py (
    echo ERROR: nwn_log_client.py not found in current directory.
    echo Please place this batch file in the same directory as nwn_log_client.py
    pause
    exit /b
)

REM Create config.ini if it doesn't exist
if not exist config.ini (
    echo Creating config.ini...
    echo [Client] > config.ini
    echo SERVER_URL = http://nwn-persona.online:5000/ >> config.ini
    echo API_ENDPOINT = /api/log_update >> config.ini
    echo WEBSOCKET_URL = ws://nwn-persona.online:5000/socket.io/?EIO=4^&transport=websocket >> config.ini
    echo NWN_LOG_PATH = C:\Users\YourUser\Documents\Neverwinter Nights\logs\nwclientLog1.txt >> config.ini
    echo CHECK_INTERVAL = 0.5 >> config.ini
    echo CLIENT_NAME = default-client >> config.ini
)

REM Create empty icon file if needed
if not exist nwn_icon.ico (
    echo Creating empty icon file...
    type nul > nwn_icon.ico
)

REM Remove previous builds to avoid confusion
if exist dist (
    echo Removing previous dist folder...
    rmdir /s /q dist
)
if exist build (
    echo Removing previous build folder...
    rmdir /s /q build
)

REM Install required packages
echo Installing required packages...
python -m pip install pyinstaller pywin32

REM Build the executable
echo Building executable with PyInstaller...
python -m PyInstaller --onefile --name NWNLogClient --icon=nwn_icon.ico --add-data "config.ini;." nwn_log_client.py

if not exist dist\NWNLogClient.exe (
    echo ERROR: Failed to build executable
    pause
    exit /b
)

REM Copy the executable to the current directory for easier access by Inno Setup
echo Copying executable to current directory...
copy dist\NWNLogClient.exe .

echo.
echo Build successful! 
echo.
echo The executable has been created in:
echo - .\NWNLogClient.exe (current directory)
echo - .\dist\NWNLogClient.exe (dist folder)
echo.
echo To create a full installer with customization options:
echo 1. Download and install Inno Setup from: https://jrsoftware.org/isinfo.php
echo 2. Open inno_setup_script.iss with Inno Setup Compiler
echo 3. Click Build -^> Compile
echo.
echo IMPORTANT: If you encounter an error that NWNLogClient.exe cannot be found
echo when running the installed application, make sure to:
echo - Run this batch file first to create the executable
echo - If error persists, try running both build_installer.bat and Inno Setup as Administrator
echo.

pause 