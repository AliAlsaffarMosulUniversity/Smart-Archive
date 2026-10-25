[Setup]
AppId=SmartArchive.LocalDesktop
AppName=Smart Archive
AppVersion=0.1.0
DefaultDirName={localappdata}\SmartArchive
DefaultGroupName=Smart Archive
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=SmartArchive-Setup
Compression=lzma2
SolidCompression=yes
[Files]
Source: "..\dist\SmartArchive\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\Smart Archive"; Filename: "{app}\SmartArchive.exe"
Name: "{autodesktop}\Smart Archive"; Filename: "{app}\SmartArchive.exe"
[Run]
Filename: "{app}\SmartArchive.exe"; Description: "Open Smart Archive"; Flags: nowait postinstall skipifsilent
