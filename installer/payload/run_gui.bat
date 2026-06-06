@echo off
setlocal
set "ROOT=%~dp0"
cd /d "%ROOT%"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m journal_parser.gui_app
) else (
  start "" pythonw -m journal_parser.gui_app
)
endlocal

