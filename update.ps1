$ErrorActionPreference = "Stop"

$installRoot = Join-Path ([Environment]::GetFolderPath("LocalApplicationData")) "journal-parser"
$installScript = Join-Path $installRoot "install.ps1"

if (-not (Test-Path -LiteralPath $installScript)) {
  Write-Host "Not installed yet. Running installer from repo folder..." -ForegroundColor Yellow
  powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "install.ps1")
  exit 0
}

Write-Host "Updating installed journal-parser..." -ForegroundColor Cyan
powershell -NoProfile -ExecutionPolicy Bypass -File $installScript
Write-Host "Done." -ForegroundColor Green

