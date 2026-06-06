$ErrorActionPreference = "Stop"

function Fail([string]$msg) {
  Write-Host ""
  Write-Host "ERROR: $msg" -ForegroundColor Red
  exit 1
}

function Info([string]$msg) {
  Write-Host $msg -ForegroundColor Cyan
}

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$iss = Join-Path $PSScriptRoot "journal-parser.iss"

if (-not (Test-Path -LiteralPath $iss)) {
  Fail "Missing .iss: $iss"
}

$iscc = Get-Command "iscc.exe" -ErrorAction SilentlyContinue
if (-not $iscc) {
  Fail "Inno Setup не найден (iscc.exe). Установите Inno Setup и добавьте iscc.exe в PATH."
}

Info "Building installer..."
Push-Location $PSScriptRoot
try {
  & $iscc.Source $iss | Out-Host
} finally {
  Pop-Location
}

Info "Done. See installer\\output\\journal-parser-setup.exe"

