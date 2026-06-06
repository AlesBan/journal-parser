$ErrorActionPreference = "Stop"

function Fail([string]$msg) {
  Write-Host ""
  Write-Host "ERROR: $msg" -ForegroundColor Red
  exit 1
}

function Info([string]$msg) {
  Write-Host $msg -ForegroundColor Cyan
}

$iss = Join-Path $PSScriptRoot "journal-parser.iss"
$outDir = Join-Path $PSScriptRoot "output"
if (-not (Test-Path -LiteralPath $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }

function Build-Inno() {
  if (-not (Test-Path -LiteralPath $iss)) { return $false }
  $iscc = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
  if (-not $iscc) {
    # Try default install locations
    $candidates = @(
      "${env:ProgramFiles(x86)}\\Inno Setup 6\\ISCC.exe",
      "${env:ProgramFiles}\\Inno Setup 6\\ISCC.exe"
    )
    foreach ($c in $candidates) {
      if (Test-Path -LiteralPath $c) { $iscc = Get-Command $c -ErrorAction SilentlyContinue; break }
    }
  }
  if (-not $iscc) { return $false }
  Info "Building installer via Inno Setup..."
  Push-Location $PSScriptRoot
  try { & $iscc.Source $iss | Out-Host } finally { Pop-Location }
  return $true
}

function Build-IExpress([string]$sedName) {
  $iexpress = Join-Path $env:WINDIR "System32\\iexpress.exe"
  if (-not (Test-Path -LiteralPath $iexpress)) { Fail "iexpress.exe not found: $iexpress" }
  $sed = Join-Path $PSScriptRoot $sedName
  if (-not (Test-Path -LiteralPath $sed)) { Fail "Missing SED: $sed" }
  Info "Building $sedName via IExpress..."
  Push-Location $PSScriptRoot
  try {
    & $iexpress /N /Q $sed | Out-Host
  } finally {
    Pop-Location
  }
}

if (Build-Inno) {
  Info "Done. See installer\\output\\journal-parser-setup.exe"
  exit 0
}

Info "Inno Setup not found. Falling back to Windows IExpress..."
Build-IExpress "iexpress-installer.sed"
Build-IExpress "iexpress-reinstaller.sed"

# Move outputs into installer/output/ for consistency
$installerExe = Join-Path $PSScriptRoot "Installer.exe"
$reinstallerExe = Join-Path $PSScriptRoot "Reinstaller.exe"
if (Test-Path -LiteralPath $installerExe) { Move-Item -Force -LiteralPath $installerExe -Destination (Join-Path $outDir "Installer.exe") }
if (Test-Path -LiteralPath $reinstallerExe) { Move-Item -Force -LiteralPath $reinstallerExe -Destination (Join-Path $outDir "Reinstaller.exe") }

Info "Done. See installer\\output\\Installer.exe and installer\\output\\Reinstaller.exe"

