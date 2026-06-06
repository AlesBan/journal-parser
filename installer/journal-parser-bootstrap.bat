@echo off
setlocal
REM Bootstrapper: ensure app exists (first run) and launch GUI.
set "ROOT=%~dp0"
cd /d "%ROOT%"

REM Install/update only if needed (install.ps1 caches installed revision).
powershell -NoProfile -ExecutionPolicy Bypass -File "%ROOT%install.ps1"

REM Launch GUI without terminal window.
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m journal_parser.gui_app
) else (
  start "" pythonw -m journal_parser.gui_app
)
endlocal

