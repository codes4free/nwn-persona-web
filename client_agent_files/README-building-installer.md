# Building NWN Log Client Installer

This document provides instructions for building a standalone executable and MSI installer for the NWN Log Client.

## Method 1: Automatic Build (Recommended)

The easiest way to build the executable and installer is to use the provided build script:

1. Make sure you have Python installed with pip
2. Run the build script:
   ```
   python build_exe_and_installer.py
   ```
3. The script will:
   - Install required dependencies (PyInstaller, cx_Freeze, etc.)
   - Create a standalone executable
   - Build an MSI installer
4. Find the built files in the `dist` folder

## Method 2: Using Inno Setup (Better Installer)

For a more professional installer with configuration during installation:

1. First build the executable:
   ```
   python build_exe_and_installer.py
   ```

2. Download and install [Inno Setup](https://jrsoftware.org/isinfo.php)

3. Open `inno_setup_script.iss` with Inno Setup Compiler

4. Click "Build" → "Compile"

5. The installer will be created in the `dist` folder as `NWNLogClient_Setup.exe`

This installer will allow users to configure:
- Server URL
- Client name
- NWN log file location
- Advanced settings

## Method 3: Manual Build

If you prefer to build manually:

### Building the Executable

1. Install PyInstaller:
   ```
   pip install pyinstaller
   ```

2. Build the standalone executable:
   ```
   pyinstaller --onefile --name NWNLogClient --icon=nwn_icon.ico --add-data "config.ini;." --noconsole nwn_log_client.py
   ```

3. Find the executable in the `dist` folder

### Building the MSI Installer

1. Install cx_Freeze:
   ```
   pip install cx_Freeze
   ```

2. Create a setup.py file:
   ```python
   import sys
   from cx_Freeze import setup, Executable

   build_exe_options = {
       "packages": ["os", "requests", "websocket", "json", "configparser"],
       "include_files": ["config.ini"]
   }

   base = None
   if sys.platform == "win32":
       base = "Win32GUI"

   setup(
       name="NWN Log Client",
       version="1.0",
       description="Neverwinter Nights Log Client",
       options={"build_exe": build_exe_options},
       executables=[Executable("nwn_log_client.py", base=base)]
   )
   ```

3. Build the MSI installer:
   ```
   python setup.py bdist_msi
   ```

4. Find the MSI installer in the `dist` folder

## Distributing the Installer

1. Before distributing, make sure to update:
   - Branding information in the Inno Setup script
   - Default server URLs to match your actual server
   - Icon with your preferred image

2. Test the installer on a clean Windows machine to ensure it works correctly

## Troubleshooting

- **Missing modules**: If you get errors about missing modules, add them to the package list in build_exe_options
- **Icon issues**: Make sure nwn_icon.ico exists or remove the icon parameter
- **Config file not included**: Make sure to include config.ini as shown in include_files 