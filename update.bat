@echo off
setlocal
REM Reinstaller / updater (pulls latest GitHub main).
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1"
pause
endlocal

