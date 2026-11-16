; Inno Setup recipe for the Windows installer: dist\Drive-Organizer-Setup.exe
; Build after PyInstaller has made dist\Drive Organizer\ :   iscc packaging\windows_installer.iss

[Setup]
AppId={{6C0E5B7B-52A4-4C0B-9D0E-3B7F1A2D9E41}
AppName=Drive Organizer
AppVersion=1.0
; Installs for this user only, so no administrator password is needed
PrivilegesRequired=lowest
DefaultDirName={autopf}\Drive Organizer
DisableProgramGroupPage=yes
; An update replaces the app while it is running in the background
CloseApplications=force
OutputDir=..\dist
OutputBaseFilename=Drive-Organizer-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern

[Tasks]
Name: "desktopicon"; Description: "Add a Drive Organizer shortcut to the Desktop"

[Files]
Source: "..\dist\Drive Organizer\*"; DestDir: "{app}"; Flags: recursesubdirs ignoreversion

[Icons]
Name: "{autoprograms}\Drive Organizer"; Filename: "{app}\Drive Organizer.exe"
Name: "{autodesktop}\Drive Organizer"; Filename: "{app}\Drive Organizer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Drive Organizer.exe"; Description: "Open Drive Organizer now"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; The app has no window; stop it so its files can be removed
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM ""Drive Organizer.exe"""; Flags: runhidden; RunOnceId: "StopApp"
