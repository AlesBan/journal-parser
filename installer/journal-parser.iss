[Setup]
AppId={{A7F6A0E2-4F88-4B5D-9C3D-0C9E2AB9A2B1}
AppName=journal-parser
AppVersion=0.1.0
AppPublisher=journal-parser
DefaultDirName={localappdata}\journal-parser
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64
OutputDir=output
OutputBaseFilename=journal-parser-setup
Compression=lzma2
SolidCompression=yes
Uninstallable=yes

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"; Flags: checkedonce

[Files]
Source: "..\install.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\update.ps1"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\install.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\update.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\start_gui.bat"; DestDir: "{app}"; Flags: ignoreversion
Source: "journal-parser-bootstrap.bat"; DestDir: "{app}"; Flags: ignoreversion

; Keep user filters on uninstall/reinstall (filters are created by install.ps1).
[UninstallDelete]
Type: filesandordirs; Name: "{app}\_tmp"

[Icons]
Name: "{autoprograms}\journal-parser"; Filename: "{app}\journal-parser-bootstrap.bat"
Name: "{autodesktop}\journal-parser"; Filename: "{app}\journal-parser-bootstrap.bat"; Tasks: desktopicon

[Run]
Filename: "{app}\journal-parser-bootstrap.bat"; Description: "Запустить journal-parser"; Flags: postinstall skipifsilent runhidden

