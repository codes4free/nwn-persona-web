#define MyAppName "NWN Log Client"
#define MyAppVersion "1.0"
#define MyAppPublisher "d6lab"
#define MyAppURL "http://nwn-persona.online:5000/"
#define MyAppExeName "NWNLogClient.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application.
; Do not use the same AppId value in installers for other applications.
AppId={{D3826A45-8C98-40B9-9AAE-6F07418541B0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={pf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=NWNLogClient_Setup
;SetupIconFile=nwn_icon.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 0,6.1

[Files]
; Use simple file references without conditional checks
Source: "dist\NWNLogClient.exe"; DestDir: "{app}"; DestName: "NWNLogClient.exe"; Flags: ignoreversion
Source: "config.ini"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:ProgramOnTheWeb,{#MyAppName}}"; Filename: "{#MyAppURL}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
var
  ServerPage: TInputQueryWizardPage;
  LogPage: TInputFileWizardPage;
  AdvancedPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  // Create the Server Configuration page
  ServerPage := CreateInputQueryPage(wpWelcome,
    'Server Configuration',
    'Enter server connection details',
    'Please specify the details for connecting to the NWN:EE chatbot server');
  ServerPage.Add('Server URL (e.g., http://nwn-persona.online:5000/):', False);
  ServerPage.Add('Client Name (optional):', False);
  ServerPage.Values[0] := 'http://nwn-persona.online:5000/';
  ServerPage.Values[1] := GetComputerNameString();
  
  // Create the Log File Configuration page
  LogPage := CreateInputFilePage(ServerPage.ID,
    'NWN Log File Location',
    'Select the location of your Neverwinter Nights log file',
    'Please select the location of your nwclientLog1.txt file:');
  LogPage.Add('Log File:', 'Text files (*.txt)|*.txt', '.txt');
  
  // Try to find default log location
  if DirExists(ExpandConstant('{userprofile}\Documents\Neverwinter Nights\logs')) then
    LogPage.Values[0] := ExpandConstant('{userprofile}\Documents\Neverwinter Nights\logs\nwclientLog1.txt')
  else if DirExists(ExpandConstant('{userprofile}\OneDrive\Documents\Neverwinter Nights\logs')) then
    LogPage.Values[0] := ExpandConstant('{userprofile}\OneDrive\Documents\Neverwinter Nights\logs\nwclientLog1.txt')
  else
    LogPage.Values[0] := '';
  
  // Create the Advanced Configuration page
  AdvancedPage := CreateInputQueryPage(LogPage.ID,
    'Advanced Configuration',
    'Enter advanced configuration settings',
    'Leave these at default values unless you know what you are doing');
  AdvancedPage.Add('API Endpoint:', False);
  AdvancedPage.Add('WebSocket URL:', False);
  AdvancedPage.Add('Check Interval (seconds):', False);
  AdvancedPage.Values[0] := '/api/log_update';
  AdvancedPage.Values[1] := 'ws://nwn-persona.online:5000/socket.io/?EIO=4&transport=websocket';
  AdvancedPage.Values[2] := '0.5';
end;

function UpdateConfigFile(): Boolean;
var
  ConfigFile: String;
  ServerURL, ClientName, LogPath, APIEndpoint, WebSocketURL, CheckInterval: String;
  Lines: TArrayOfString;
  I: Integer;
begin
  Result := True;
  
  // Get values from wizard
  ServerURL := ServerPage.Values[0];
  ClientName := ServerPage.Values[1];
  LogPath := LogPage.Values[0];
  APIEndpoint := AdvancedPage.Values[0];
  WebSocketURL := AdvancedPage.Values[1];
  CheckInterval := AdvancedPage.Values[2];
  
  // Replace backslashes with double backslashes for the config file
  StringChangeEx(LogPath, '\', '\\', True);
  
  // Create the config file
  ConfigFile := ExpandConstant('{app}\config.ini');
  
  // Write the config file
  SaveStringToFile(ConfigFile, '[Client]' + #13#10, False);
  SaveStringToFile(ConfigFile, 'SERVER_URL = ' + ServerURL + #13#10, True);
  SaveStringToFile(ConfigFile, 'API_ENDPOINT = ' + APIEndpoint + #13#10, True);
  SaveStringToFile(ConfigFile, 'WEBSOCKET_URL = ' + WebSocketURL + #13#10, True);
  SaveStringToFile(ConfigFile, 'NWN_LOG_PATH = ' + LogPath + #13#10, True);
  SaveStringToFile(ConfigFile, 'CHECK_INTERVAL = ' + CheckInterval + #13#10, True);
  SaveStringToFile(ConfigFile, 'CLIENT_NAME = ' + ClientName + #13#10, True);
  
  Log('Config file updated at: ' + ConfigFile);
end;

// Verify that the executable exists before installation
function InitializeSetup(): Boolean;
begin
  Result := True;
  
  if not FileExists('dist\NWNLogClient.exe') then
  begin
    MsgBox('Cannot find dist\NWNLogClient.exe. Please run the build_installer.bat script first to create the executable.', mbError, MB_OK);
    Result := False;
  end;
end;

// Called after installation
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    UpdateConfigFile();
end; 