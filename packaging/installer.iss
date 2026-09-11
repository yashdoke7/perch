; Inno Setup script for PERCH: a per-user installer, no admin rights needed.
;
;   ISCC.exe /DAppVersion=0.8.0 packaging\installer.iss
;
; packaging\build.ps1 runs this after PyInstaller. Installs to
; %LOCALAPPDATA%\Programs\PERCH, adds Start-menu entries and an uninstaller,
; and optionally starts PERCH at sign-in using the SAME Run-key value the
; Settings screen writes -- so the two can never disagree about it.
;
; Memory lives in %USERPROFILE%\.perch and is NOT removed on uninstall: it is
; the user's data, not the program's.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{B6F3D2A4-5C1E-4F7A-9D2B-3E8C7A1F0D95}
AppName=PERCH
AppVersion={#AppVersion}
AppVerName=PERCH {#AppVersion}
AppPublisher=Yash Doke
AppComments=A personal AI agent that lives where your desktop lives. Memory stays on this machine.
DefaultDirName={localappdata}\Programs\PERCH
DefaultGroupName=PERCH
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=PERCH-Setup-{#AppVersion}
SetupIconFile=perch.ico
UninstallDisplayIcon={app}\PERCH.exe
UninstallDisplayName=PERCH
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "startup"; Description: "Start PERCH when I sign in (runs quietly in the tray)"
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "..\dist\PERCH\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PERCH"; Filename: "{app}\PERCH.exe"; Parameters: "open"; Comment: "Open PERCH"
Name: "{group}\Uninstall PERCH"; Filename: "{uninstallexe}"
Name: "{autodesktop}\PERCH"; Filename: "{app}\PERCH.exe"; Parameters: "open"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "PERCH"; ValueData: """{app}\PERCH.exe"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\PERCH.exe"; Parameters: "open"; Description: "Open PERCH now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/IM PERCH.exe /F"; Flags: runhidden; RunOnceId: "StopPERCH"

[UninstallDelete]
Type: dirifempty; Name: "{app}"
