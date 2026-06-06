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
InstallPrompt=%InstallPrompt%
DisplayLicense=%DisplayLicense%
FinishMessage=%FinishMessage%
TargetName=%TargetName%
FriendlyName=%FriendlyName%
AppLaunched=%AppLaunched%
PostInstallCmd=%PostInstallCmd%
AdminQuietInstCmd=%AdminQuietInstCmd%
UserQuietInstCmd=%UserQuietInstCmd%
SourceFiles=SourceFiles



[Strings]
InstallPrompt=
DisplayLicense=
FinishMessage=
TargetName=Installer.exe
FriendlyName=journal-parser Installer
AppLaunched=cmd /c "powershell -NoProfile -ExecutionPolicy Bypass -File install.ps1 -Machine -CreateShortcuts -Launch"
PostInstallCmd=<None>
AdminQuietInstCmd=
UserQuietInstCmd=
FILE0="install.ps1"
FILE1="update.ps1"
FILE2="run_gui.bat"
[SourceFiles]
SourceFiles0=payload\
[SourceFiles0]
%FILE0%=
%FILE1%=
%FILE2%=
