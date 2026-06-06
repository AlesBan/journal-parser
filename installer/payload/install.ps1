param(
  [switch]$CreateShortcuts,
  [switch]$Launch,
  [switch]$ForceUpdate,
  [switch]$Machine,
  [string]$InstallRoot,
  [switch]$FullReinstall
)

$ErrorActionPreference = "Stop"

function Fail([string]$msg) {
  Write-Host ""
  Write-Host "ERROR: $msg" -ForegroundColor Red
  exit 1
}

function Info([string]$msg) {
  Write-Host $msg -ForegroundColor Cyan
}

function Get-StateDir() {
  $base = [Environment]::GetFolderPath("ApplicationData")
  return Join-Path $base "journal-parser"
}

function Write-InstallRootPointer([string]$installRoot) {
  try {
    $dir = Get-StateDir
    Ensure-Dir $dir
    Set-Content -Encoding UTF8 -LiteralPath (Join-Path $dir "install-root.txt") -Value $installRoot
  } catch { }
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

function Is-Administrator() {
  try {
    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p = New-Object Security.Principal.WindowsPrincipal($id)
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
  } catch {
    return $false
  }
}

function Get-InvokerExePath() {
  # Best-effort: walk up the process tree and try to find the original self-extracting EXE path
  # (useful for IExpress which runs the script from a temp extraction folder).
  try {
    $currentPid = $PID
    for ($i = 0; $i -lt 12; $i++) {
      $p = Get-CimInstance Win32_Process -Filter "ProcessId=$currentPid" -ErrorAction SilentlyContinue
      if (-not $p) { break }

      $candidates = @()
      if ($p.ExecutablePath) { $candidates += [string]$p.ExecutablePath }

      $cmd = [string]$p.CommandLine
      if ($cmd) {
        $rx = '(?i)(?:^|\\s)(\"(?<q>[A-Z]:\\\\[^\\\"]+\\.exe)\"|(?<p>[A-Z]:\\\\[^\\s]+\\.exe))(?:\\s|$)'
        foreach ($m in ([regex]::Matches($cmd, $rx))) {
          $path = if ($m.Groups["q"].Success) { $m.Groups["q"].Value } else { $m.Groups["p"].Value }
          if ($path) { $candidates += $path }
        }
      }

      foreach ($c in ($candidates | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $c)) { continue }
        $leaf = (Split-Path -Leaf $c).ToLowerInvariant()
        if ($leaf -in @("powershell.exe","pwsh.exe","cmd.exe","conhost.exe","wextract.exe","iexpress.exe")) { continue }
        # Prefer our package exe name if present
        if ($leaf -in @("installer.exe","journal-parser-setup.exe","journal-parser-installer.exe")) { return $c }
        if ($leaf -like "*journal-parser*") { return $c }
      }

      if (-not $p.ParentProcessId -or $p.ParentProcessId -le 0) { break }
      $currentPid = [int]$p.ParentProcessId
    }
  } catch { }
  return ""
}

function Get-DefaultInstallRoot([switch]$machineInstall) {
  $invoker = Get-InvokerExePath
  if ($invoker) {
    $dir = Split-Path -Parent $invoker
    if ($dir) { return $dir }
  }
  if ($machineInstall) {
    $base = [Environment]::GetFolderPath("ProgramFiles")
    return Join-Path $base "journal-parser"
  }
  $base = [Environment]::GetFolderPath("LocalApplicationData")
  return Join-Path $base "journal-parser"
}

function Get-DesktopShortcutPath([string]$name) {
  $pf = [Environment]::GetFolderPath("ProgramFiles")
  $pf86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
  $machineShortcuts =
    $Machine -or
    ($installRoot -and $pf -and $installRoot.StartsWith($pf, [StringComparison]::OrdinalIgnoreCase)) -or
    ($installRoot -and $pf86 -and $installRoot.StartsWith($pf86, [StringComparison]::OrdinalIgnoreCase))

  $desktop = if ($machineShortcuts) { [Environment]::GetFolderPath("CommonDesktopDirectory") } else { [Environment]::GetFolderPath("Desktop") }
  return Join-Path $desktop $name
}

function Get-StartMenuDir() {
  $pf = [Environment]::GetFolderPath("ProgramFiles")
  $pf86 = [Environment]::GetEnvironmentVariable("ProgramFiles(x86)")
  $machineShortcuts =
    $Machine -or
    ($installRoot -and $pf -and $installRoot.StartsWith($pf, [StringComparison]::OrdinalIgnoreCase)) -or
    ($installRoot -and $pf86 -and $installRoot.StartsWith($pf86, [StringComparison]::OrdinalIgnoreCase))

  $programs = if ($machineShortcuts) { [Environment]::GetFolderPath("CommonPrograms") } else { [Environment]::GetFolderPath("Programs") }
  return Join-Path $programs "journal-parser"
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

function Ensure-Python() {
  $py = Get-Command python -ErrorAction SilentlyContinue
  if (-not $py) {
    Fail "Python не найден. Установите Python 3.11+ и убедитесь, что 'python' есть в PATH."
  }
}

function Test-WriteAccess([string]$dir) {
  try {
    if (-not (Test-Path -LiteralPath $dir)) {
      New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
    $probe = Join-Path $dir ("._write_probe_" + [Guid]::NewGuid().ToString("N") + ".tmp")
    Set-Content -LiteralPath $probe -Value "ok" -Encoding ASCII
    Remove-Item -LiteralPath $probe -Force
    return $true
  } catch {
    return $false
  }
}

function Ensure-Elevated-IfNeeded([string]$installRoot) {
  if (Is-Administrator) { return }
  if (Test-WriteAccess $installRoot) { return }

  Info "No write access to: $installRoot"
  Info "Requesting administrator privileges..."

  $ps = (Get-Command powershell.exe).Source
  $self = $PSCommandPath

  $argList = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$self`"",
    "-InstallRoot", "`"$installRoot`""
  )
  if ($Machine) { $argList += "-Machine" }
  if ($CreateShortcuts) { $argList += "-CreateShortcuts" }
  if ($Launch) { $argList += "-Launch" }
  if ($ForceUpdate) { $argList += "-ForceUpdate" }

  try {
    $p = Start-Process -FilePath $ps -ArgumentList ($argList -join " ") -Verb RunAs -Wait -PassThru
  } catch {
    Fail "Не удалось запросить права администратора (RunAs)."
  }

  if ($p.ExitCode -ne 0) {
    Fail "Установка/обновление (elevated) завершились с ошибкой. ExitCode=$($p.ExitCode)"
  }

  exit 0
}

function Run([string]$exe, [string[]]$argumentList, [string]$cwd) {
  if ($null -eq $argumentList -or $argumentList.Count -eq 0) {
    $p = Start-Process -FilePath $exe -WorkingDirectory $cwd -Wait -PassThru -NoNewWindow
  } else {
    $p = Start-Process -FilePath $exe -ArgumentList $argumentList -WorkingDirectory $cwd -Wait -PassThru -NoNewWindow
  }
  if ($p.ExitCode -ne 0) {
    Fail "Command failed ($exe $($argumentList -join ' ')). ExitCode=$($p.ExitCode)"
  }
}

function Copy-IfMissing([string]$src, [string]$dst) {
  if (-not (Test-Path -LiteralPath $dst)) {
    Copy-Item -LiteralPath $src -Destination $dst -Force
  }
}

function Read-Installed-Revision([string]$installRoot) {
  $revFile = Join-Path $installRoot "installed-revision.txt"
  if (Test-Path -LiteralPath $revFile) {
    try { return (Get-Content -LiteralPath $revFile -ErrorAction SilentlyContinue | Select-Object -First 1).Trim() } catch { }
  }
  return ""
}

function Write-Installed-Revision([string]$installRoot, [string]$rev) {
  $revFile = Join-Path $installRoot "installed-revision.txt"
  Set-Content -Encoding ASCII -LiteralPath $revFile -Value $rev
}

function Get-Remote-Revision([string]$owner, [string]$repo, [string]$branch) {
  $api = "https://api.github.com/repos/$owner/$repo/commits/$branch"
  try {
    $resp = Invoke-WebRequest -UseBasicParsing -Uri $api -Headers @{ "User-Agent" = "journal-parser-installer" }
    $json = $resp.Content | ConvertFrom-Json
    return [string]$json.sha
  } catch {
    return ""
  }
}

# --- Config: update these to your GitHub repo ---
$OWNER  = "AlesBan"
$REPO   = "journal-parser"
$BRANCH = "main"
# ----------------------------------------------

Ensure-Python

$here = Split-Path -Parent $MyInvocation.MyCommand.Path

$installRoot = if ($InstallRoot -and $InstallRoot.Trim()) { $InstallRoot } else { Get-DefaultInstallRoot -machineInstall:$Machine }
Ensure-Elevated-IfNeeded $installRoot
Ensure-Dir $installRoot
Write-InstallRootPointer $installRoot

# Full reinstall: remove venv so deps can't get "stuck".
if ($FullReinstall) {
  $venv = Join-Path $installRoot ".venv"
  if (Test-Path -LiteralPath $venv) {
    Info "Removing existing venv..."
    try { Remove-Item -Recurse -Force -LiteralPath $venv } catch { }
  }
}

# Only download/update if remote revision differs (or unknown).
$installed = Read-Installed-Revision $installRoot
$remote = Get-Remote-Revision $OWNER $REPO $BRANCH
if (-not $ForceUpdate) {
  if ($remote -and $installed -and ($remote -eq $installed)) {
    Info "Already up to date."
    # Still allow shortcut creation / launch even if up to date.
    if (-not $CreateShortcuts -and -not $Launch) { exit 0 }
  }
}

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
  if ($name -eq "reports") { return }
  if ($name -eq "installer") { return }
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

# Create run/update helpers in install root.
$runBat = Join-Path $installRoot "run_gui.bat"
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
"@ | Set-Content -Encoding ASCII -LiteralPath $runBat

$appIco = Join-Path $installRoot "app.ico"
$srcIco = Join-Path $here "app.ico"
if (Test-Path -LiteralPath $srcIco) {
  Copy-Item -Force -LiteralPath $srcIco -Destination $appIco
}

$updatePs1 = Join-Path $installRoot "update.ps1"
@"
\$ErrorActionPreference = 'Stop'
\$here = Split-Path -Parent \$MyInvocation.MyCommand.Path
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path \$here 'install.ps1') -ForceUpdate -InstallRoot `"\$here`"$(if ($Machine) { " -Machine" } else { "" })
"@ | Set-Content -Encoding UTF8 -LiteralPath $updatePs1

# Copy this install.ps1 into install root for future updates.
Copy-Item -Force -LiteralPath $PSCommandPath -Destination (Join-Path $installRoot "install.ps1")

# Save installed revision (best-effort).
if ($remote) {
  Write-Installed-Revision $installRoot $remote
}

# Cleanup temp
Remove-Item -Recurse -Force -LiteralPath $tmpDir

Write-Host "Installed/updated to: $installRoot" -ForegroundColor Green

if ($CreateShortcuts) {
  $startMenu = Get-StartMenuDir
  Ensure-Dir $startMenu

  $icon = Join-Path $installRoot "app.ico"

  # Start Menu shortcuts
  Create-Shortcut (Join-Path $startMenu "journal-parser.lnk") $runBat $installRoot "" $icon
  Create-Shortcut (Join-Path $startMenu "Обновить journal-parser.lnk") "powershell.exe" $installRoot "-NoProfile -ExecutionPolicy Bypass -File ""$updatePs1""" $icon

  # Desktop shortcut (main app)
  Create-Shortcut (Get-DesktopShortcutPath "journal-parser.lnk") $runBat $installRoot "" $icon
}

if ($Launch) {
  $pythonw = Join-Path $installRoot ".venv\\Scripts\\pythonw.exe"
  if (Test-Path -LiteralPath $pythonw) {
    Start-Process -FilePath $pythonw -ArgumentList "-m journal_parser.gui_app" -WorkingDirectory $installRoot | Out-Null
  }
}

