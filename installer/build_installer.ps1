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

function Assert-Writable([string]$dir) {
  try {
    $probe = Join-Path $dir ("._write_probe_" + [Guid]::NewGuid().ToString("N") + ".tmp")
    Set-Content -LiteralPath $probe -Value "ok" -Encoding ASCII
    Remove-Item -LiteralPath $probe -Force
  } catch {
    Fail "Нет прав на запись в папку: $dir`nЗапусти сборку из обычной папки (например, D:\\Downloads\\journal-parser) или от администратора. Часто 'Program Files' запрещает запись."
  }
}

function Run-Checked([string]$exe, [string[]]$args) {
  & $exe @args | Out-Host
  if ($LASTEXITCODE -ne 0) {
    Fail "Команда завершилась с ошибкой (ExitCode=$LASTEXITCODE): $exe $($args -join ' ')"
  }
}

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
  try { Run-Checked $iscc.Source @($iss) } finally { Pop-Location }
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
    Run-Checked $iexpress @("/N", "/Q", $sed)
  } finally {
    Pop-Location
  }
}

Assert-Writable $PSScriptRoot
Assert-Writable $outDir

if (Build-Inno) {
  Info "Done. See installer\\output\\journal-parser-setup.exe"
  exit 0
}

Info "Inno Setup not found. Falling back to Windows IExpress..."

# Remove stale outputs in case a previous build left partial files.
$stale1 = Join-Path $PSScriptRoot "Installer.exe"
$stale2 = Join-Path $PSScriptRoot "Reinstaller.exe"
if (Test-Path -LiteralPath $stale1) { Remove-Item -Force -LiteralPath $stale1 }
if (Test-Path -LiteralPath $stale2) { Remove-Item -Force -LiteralPath $stale2 }

Build-IExpress "iexpress-installer.sed"
Build-IExpress "iexpress-reinstaller.sed"

# Move outputs into installer/output/ for consistency
$installerExe = Join-Path $PSScriptRoot "Installer.exe"
$reinstallerExe = Join-Path $PSScriptRoot "Reinstaller.exe"
if (-not (Test-Path -LiteralPath $installerExe)) { Fail "IExpress did not produce Installer.exe in: $PSScriptRoot" }
if (-not (Test-Path -LiteralPath $reinstallerExe)) { Fail "IExpress did not produce Reinstaller.exe in: $PSScriptRoot" }
if (Test-Path -LiteralPath $installerExe) { Move-Item -Force -LiteralPath $installerExe -Destination (Join-Path $outDir "Installer.exe") }
if (Test-Path -LiteralPath $reinstallerExe) { Move-Item -Force -LiteralPath $reinstallerExe -Destination (Join-Path $outDir "Reinstaller.exe") }

Info "Done. See installer\\output\\Installer.exe and installer\\output\\Reinstaller.exe"

