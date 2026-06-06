[Setup]
AppId={{A7F6A0E2-4F88-4B5D-9C3D-0C9E2AB9A2B1}
AppName=journal-parser
AppVersion=0.1.0
AppPublisher=journal-parser
DefaultDirName={pf}\journal-parser
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64
OutputDir=output
OutputBaseFilename=journal-parser-setup
Compression=lzma2
SolidCompression=yes
Uninstallable=yes
SetupIconFile=payload\app.ico

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"; Flags: checkedonce

[Files]
Source: "payload\install.ps1"; DestDir: "{app}"; DestName: "install.ps1"; Flags: ignoreversion
Source: "payload\update.ps1"; DestDir: "{app}"; DestName: "update.ps1"; Flags: ignoreversion
Source: "payload\run_gui.bat"; DestDir: "{app}"; DestName: "run_gui.bat"; Flags: ignoreversion
Source: "payload\app.ico"; DestDir: "{app}"; DestName: "app.ico"; Flags: ignoreversion
Source: "journal-parser-bootstrap.bat"; DestDir: "{app}"; Flags: ignoreversion

; Keep user filters on uninstall/reinstall (filters are created by install.ps1).
[UninstallDelete]
Type: filesandordirs; Name: "{app}\_tmp"

[Icons]
Name: "{autoprograms}\journal-parser"; Filename: "{app}\journal-parser-bootstrap.bat"
Name: "{autoprograms}\Обновить journal-parser"; Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\update.ps1"""; WorkingDir: "{app}"
Name: "{autodesktop}\journal-parser"; Filename: "{app}\journal-parser-bootstrap.bat"; Tasks: desktopicon

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\install.ps1"" -Machine -InstallRoot ""{app}"" -CreateShortcuts -Launch"; Flags: postinstall skipifsilent runhidden

