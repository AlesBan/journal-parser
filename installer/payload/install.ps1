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

$installRoot = Get-InstallRoot
Ensure-Dir $installRoot

# Only download/update if remote revision differs (or unknown).
$installed = Read-Installed-Revision $installRoot
$remote = Get-Remote-Revision $OWNER $REPO $BRANCH
if ($remote -and $installed -and ($remote -eq $installed)) {
  Info "Already up to date."
  exit 0
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

# Save installed revision (best-effort).
if ($remote) {
  Write-Installed-Revision $installRoot $remote
}

# Cleanup temp
Remove-Item -Recurse -Force -LiteralPath $tmpDir

Write-Host "Installed/updated to: $installRoot" -ForegroundColor Green

