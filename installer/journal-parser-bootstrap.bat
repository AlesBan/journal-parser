@echo off
setlocal
REM Bootstrapper: ensure installed app is present/updated and launch GUI.
set "ROOT=%~dp0"
cd /d "%ROOT%"

REM Run installer/update logic (downloads latest GitHub main, installs venv/deps).
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%install.ps1"

REM Launch GUI without terminal window.
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m journal_parser.gui_app
) else (
  start "" pythonw -m journal_parser.gui_app
)
endlocal

