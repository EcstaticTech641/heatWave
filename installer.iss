[Setup]
AppName=heatWave
AppVersion=1.3.2
AppPublisher=ronlab
AppPublisherURL=https://github.com/EcstaticTech/heatWave
DefaultDirName={autopf}\heatWave
DefaultGroupName=heatWave
OutputDir=dist
OutputBaseFilename=heatWave_v1.3.2_setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64
DisableProgramGroupPage=yes
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\heatWave.exe

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\heatWave\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\heatWave"; Filename: "{app}\heatWave.exe"
Name: "{autodesktop}\heatWave"; Filename: "{app}\heatWave.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\heatWave.exe"; Description: "{cm:LaunchProgram,heatWave}"; Flags: nowait postinstall skipifsilent
