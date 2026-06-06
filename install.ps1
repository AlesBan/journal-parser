$ErrorActionPreference = "Stop"

function Fail([string]$msg) {
  Write-Host ""
  Write-Host "ERROR: $msg" -ForegroundColor Red
  exit 1
}

function Info([string]$msg) {
  Write-Host $msg -ForegroundColor Cyan
}

function Ensure-Dir([string]$path) {
  if (-not (Test-Path -LiteralPath $path)) {
    New-Item -ItemType Directory -Path $path | Out-Null
  }
}

function Download-File([string]$url, [string]$dest) {
  Info "Downloading: $url"
  try {
    Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $dest
  } catch {
    Fail "Failed to download: $url`n$($_.Exception.Message)"
  }
}

function Get-LatestZipUrl([string]$owner, [string]$repo, [string]$branch) {
  return "https://github.com/$owner/$repo/archive/refs/heads/$branch.zip"
}

function Get-InstallRoot() {
  $base = [Environment]::GetFolderPath("LocalApplicationData")
  return Join-Path $base "journal-parser"
}

function Get-DesktopShortcutPath() {
  $desktop = [Environment]::GetFolderPath("Desktop")
  return Join-Path $desktop "journal-parser.lnk"
}

function Ensure-Python() {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py) {
    Fail "Python не найден. Установите Python 3.11+ и убедитесь, что 'python' есть в PATH."
  }
}

function Run([string]$exe, [string]$args, [string]$cwd) {
  $p = Start-Process -FilePath $exe -ArgumentList $args -WorkingDirectory $cwd -Wait -PassThru -NoNewWindow
  if ($p.ExitCode -ne 0) {
    Fail "Command failed ($exe $args). ExitCode=$($p.ExitCode)"
  }
}

function Copy-IfMissing([string]$src, [string]$dst) {
  if (-not (Test-Path -LiteralPath $dst)) {
    Copy-Item -LiteralPath $src -Destination $dst -Force
  }
}

function Create-Shortcut([string]$shortcutPath, [string]$targetPath, [string]$workingDir, [string]$arguments, [string]$iconPath) {
  $wsh = New-Object -ComObject WScript.Shell
  $sc = $wsh.CreateShortcut($shortcutPath)
  $sc.TargetPath = $targetPath
  $sc.WorkingDirectory = $workingDir
  $sc.Arguments = $arguments
  if ($iconPath -and (Test-Path -LiteralPath $iconPath)) {
    $sc.IconLocation = $iconPath
  }
  $sc.Save()
}

# --- Config: update these to your GitHub repo ---
$OWNER  = "AlesBan"
$REPO   = "journal-parser"
$BRANCH = "main"
# ----------------------------------------------

Ensure-Python

$installRoot = Get-InstallRoot
Ensure-Dir $installRoot

$tmpDir = Join-Path $installRoot "_tmp"
if (Test-Path -LiteralPath $tmpDir) { Remove-Item -Recurse -Force -LiteralPath $tmpDir }
Ensure-Dir $tmpDir

$zipUrl = Get-LatestZipUrl $OWNER $REPO $BRANCH
$zipPath = Join-Path $tmpDir "src.zip"
Download-File $zipUrl $zipPath

Info "Extracting..."
Expand-Archive -LiteralPath $zipPath -DestinationPath $tmpDir -Force

$extracted = Get-ChildItem -LiteralPath $tmpDir -Directory | Where-Object { $_.Name -like "$REPO-*" } | Select-Object -First 1
if (-not $extracted) { Fail "Unexpected archive layout (cannot find extracted folder)." }

# Preserve user's filters/ if exist.
$userFilters = Join-Path $installRoot "filters"
Ensure-Dir $userFilters

$srcFilters = Join-Path $extracted.FullName "filters"
if (Test-Path -LiteralPath $srcFilters) {
  Copy-IfMissing (Join-Path $srcFilters "include.txt") (Join-Path $userFilters "include.txt")
  Copy-IfMissing (Join-Path $srcFilters "exclude.txt") (Join-Path $userFilters "exclude.txt")
}

# Copy app files (overlay update, but keep user filters).
Info "Installing files..."
Get-ChildItem -LiteralPath $extracted.FullName -Force | ForEach-Object {
  $name = $_.Name
  if ($name -eq ".git" -or $name -eq ".github") { return }
  if ($name -eq "filters") { return }
  $dst = Join-Path $installRoot $name
  if (Test-Path -LiteralPath $dst) {
    Remove-Item -Recurse -Force -LiteralPath $dst
  }
  Copy-Item -Recurse -Force -LiteralPath $_.FullName -Destination $dst
}

# Ensure filters are from user space.
if (Test-Path -LiteralPath (Join-Path $installRoot "filters")) {
  Remove-Item -Recurse -Force -LiteralPath (Join-Path $installRoot "filters")
}
New-Item -ItemType Directory -Path (Join-Path $installRoot "filters") | Out-Null
Copy-Item -Recurse -Force -LiteralPath $userFilters\* -Destination (Join-Path $installRoot "filters")

# venv + deps
Info "Creating venv..."
Run "python" "-m venv .venv" $installRoot

Info "Installing dependencies..."
Run (Join-Path $installRoot ".venv\\Scripts\\python.exe") "-m pip install --upgrade pip" $installRoot
Run (Join-Path $installRoot ".venv\\Scripts\\python.exe") "-m pip install -r requirements.txt" $installRoot

# Create launcher in install root (double click)
$launcher = Join-Path $installRoot "journal-parser.bat"
@"
@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m journal_parser.gui_app
) else (
  start "" pythonw -m journal_parser.gui_app
)
endlocal
"@ | Set-Content -Encoding ASCII -LiteralPath $launcher

# Create update launcher (reinstaller)
$updateBat = Join-Path $installRoot "update.bat"
@"
@echo off
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1"
endlocal
"@ | Set-Content -Encoding ASCII -LiteralPath $updateBat

# Write update.ps1 (calls install.ps1 logic by re-running from installed folder)
$updatePs1 = Join-Path $installRoot "update.ps1"
@"
\$ErrorActionPreference = 'Stop'
\$here = Split-Path -Parent \$MyInvocation.MyCommand.Path
Write-Host 'Updating journal-parser...' -ForegroundColor Cyan
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path \$here 'install.ps1')
Write-Host 'Done.' -ForegroundColor Green
"@ | Set-Content -Encoding UTF8 -LiteralPath $updatePs1

# Copy install.ps1 into install root for updates
Copy-Item -Force -LiteralPath $PSCommandPath -Destination (Join-Path $installRoot "install.ps1")

# Desktop shortcut
$shortcutPath = Get-DesktopShortcutPath
Info "Creating desktop shortcut: $shortcutPath"
Create-Shortcut $shortcutPath $launcher $installRoot "" ""

# Cleanup temp
Remove-Item -Recurse -Force -LiteralPath $tmpDir

Write-Host ""
Write-Host "Installed to: $installRoot" -ForegroundColor Green
Write-Host "Run: $launcher" -ForegroundColor Green
Write-Host "Update later: $updateBat" -ForegroundColor Green
