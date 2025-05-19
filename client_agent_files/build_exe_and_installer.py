#!/usr/bin/env python3
import os
import sys
import subprocess
import shutil

# Make sure required packages are installed
def ensure_dependencies():
    print("Ensuring required packages are installed...")
    packages = [
        "pyinstaller",
        "pywin32",  # Required for Windows functionality
        "watchdog",  # Required for file monitoring
        "requests"   # Required for HTTP requests
    ]
    
    for package in packages:
        subprocess.run([sys.executable, "-m", "pip", "install", package])
    
    print("Dependencies installed successfully")

# Build standalone EXE using PyInstaller
def build_exe():
    print("Building standalone EXE with PyInstaller...")
    
    # Clean any previous builds
    if os.path.exists("dist"):
        shutil.rmtree("dist")
    if os.path.exists("build"):
        shutil.rmtree("build")
    
    # Check if nwn_log_client.py exists
    if not os.path.exists("nwn_log_client.py"):
        print("ERROR: nwn_log_client.py not found in the current directory!")
        print("Make sure you're running this script from the same directory as nwn_log_client.py")
        return False
    
    # Create a spec file for more control
    spec_content = """
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['nwn_log_client.py'],
    pathex=[],
    binaries=[],
    datas=[('config.ini', '.')],
    hiddenimports=['requests', 'json', 'socket', 'websocket', 'threading', 'configparser', 'argparse', 'watchdog.observers', 'watchdog.events'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NWNLogClient',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='nwn_icon.ico' if os.path.exists('nwn_icon.ico') else None,
)
"""
    
    with open("NWNLogClient.spec", "w") as f:
        f.write(spec_content)
    
    # Run PyInstaller using the spec file
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "NWNLogClient.spec",
        "--clean"
    ]
    
    print("Running command:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error building executable:")
        print(result.stdout)
        print(result.stderr)
        return False
    
    print("EXE build complete! Output in dist/NWNLogClient.exe")
    
    # Create an empty batch file to start the application
    with open("dist/Start_NWNLogClient.bat", "w") as f:
        f.write("""@echo off
echo Starting NWN Log Client...
start "" "%~dp0NWNLogClient.exe"
""")
        
    return True

# Create a blank nwn_icon.ico file if it doesn't exist
def create_icon_file():
    if not os.path.exists("nwn_icon.ico"):
        print("Icon file not found. Using a default icon...")
        try:
            # Try to download NWN icon from the web
            import requests
            response = requests.get("https://neverwintervault.org/sites/all/themes/nwvault/favicon.ico")
            if response.status_code == 200:
                with open("nwn_icon.ico", "wb") as f:
                    f.write(response.content)
                print("Downloaded NWN icon successfully")
            else:
                # Create a simple blank icon file
                with open("nwn_icon.ico", "wb") as f:
                    f.write(b"")
                print("Created blank icon file")
        except:
            # Create a simple blank icon file
            with open("nwn_icon.ico", "wb") as f:
                f.write(b"")
            print("Created blank icon file")

# Run Inno Setup to create installer
def build_installer():
    print("Building installer with Inno Setup...")
    
    # Check if Inno Setup is installed
    inno_setup_path = None
    possible_paths = [
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe"
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            inno_setup_path = path
            break
    
    if not inno_setup_path:
        print("Error: Inno Setup not found. Please install Inno Setup 6.")
        print("Download from: https://jrsoftware.org/isdl.php")
        return False
    
    # Check if the inno_setup_script.iss exists
    if not os.path.exists("inno_setup_script.iss"):
        print("Creating Inno Setup script...")
        with open("inno_setup_script.iss", "w") as f:
            f.write("""#define MyAppName "NWN Log Client"
#define MyAppVersion "1.0"
#define MyAppPublisher "NWN Community"
#define MyAppExeName "NWNLogClient.exe"

[Setup]
AppId={{E8F7BAED-05CB-4BDC-881A-B517B6F3F3D7}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=.
OutputBaseFilename=NWNLogClient_Setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "config.ini"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"
Name: "{group}\\Edit Configuration"; Filename: "notepad.exe"; Parameters: "{app}\\config.ini"
Name: "{autodesktop}\\{#MyAppName}"; Filename: "{app}\\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
""")
    
    # Run Inno Setup Compiler
    cmd = [inno_setup_path, "inno_setup_script.iss"]
    print("Running command:", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("Error building installer:")
        print(result.stdout)
        print(result.stderr)
        return False
    
    print("Installer build complete! Output: NWNLogClient_Setup.exe")
    return True

# Main function
def main():
    print("=======================================")
    print("NWN Log Client - EXE and Installer Builder")
    print("=======================================")
    
    # Create sample config.ini if it doesn't exist
    if not os.path.exists("config.ini"):
        print("Creating sample config.ini...")
        with open("config.ini", "w") as f:
            f.write("""[Client]
SERVER_URL = https://your-domain.com
API_ENDPOINT = /api/log_update
CLIENT_NAME = default-client
POLL_INTERVAL = 5
""")
    
    # Ensure we have an icon file
    create_icon_file()
    
    # Make sure required packages are installed
    ensure_dependencies()
    
    # Build EXE
    if not build_exe():
        print("Failed to build executable. Aborting.")
        return
    
    # Create Windows installer
    if sys.platform == "win32":
        if not build_installer():
            print("Failed to build installer.")
    else:
        print("Installer creation is only supported on Windows.")
    
    print("\nBuild process complete!")
    print("You can find the executable in the 'dist' folder.")
    if sys.platform == "win32":
        print("The installer is in the current directory (NWNLogClient_Setup.exe).")

if __name__ == "__main__":
    main() 