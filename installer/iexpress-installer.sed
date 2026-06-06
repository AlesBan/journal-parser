[Version]
Class=IEXPRESS
SEDVersion=3

[Options]
PackagePurpose=InstallApp
ShowInstallProgramWindow=0
HideExtractAnimation=1
UseLongFileName=1
InsideCompressed=0
CAB_FixedSize=0
CAB_ResvCodeSigning=0
RebootMode=I
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=Installer.exe
FriendlyName=journal-parser Installer
AppLaunched=cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -CreateShortcuts -Launch"
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
SourceFiles=SourceFiles

[SourceFiles]
SourceFiles0=payload

[SourceFiles0]
%FILE0%=install.ps1
%FILE1%=update.ps1
%FILE2%=run_gui.bat

[Strings]
FILE0=install.ps1
FILE1=update.ps1
FILE2=run_gui.bat
