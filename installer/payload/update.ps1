$ErrorActionPreference = "Stop"

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here "install.ps1") -ForceUpdate -InstallRoot $here

