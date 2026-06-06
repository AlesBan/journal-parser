$ErrorActionPreference = "Stop"

function Get-StateInstallRoot() {
  try {
    $base = [Environment]::GetFolderPath("ApplicationData")
    $p = Join-Path (Join-Path $base "journal-parser") "install-root.txt"
    if (Test-Path -LiteralPath $p) {
      $v = (Get-Content -LiteralPath $p -ErrorAction SilentlyContinue | Select-Object -First 1).Trim()
      if ($v) { return $v }
    }
  } catch { }
  return ""
}

$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$target = Get-StateInstallRoot
if (-not $target) { $target = $here }

powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $here "install.ps1") -ForceUpdate -InstallRoot $target

