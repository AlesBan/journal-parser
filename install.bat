@echo off
setlocal
REM One-click installer (downloads latest GitHub main).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
pause
endlocal

