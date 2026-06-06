@echo off
setlocal

REM Launch minimal GUI without terminal window (uses pythonw).
REM If .venv exists, use it; otherwise fall back to system pythonw.

set "ROOT=%~dp0"
cd /d "%ROOT%"

if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" -m journal_parser.gui_app
) else (
  start "" pythonw -m journal_parser.gui_app
)

endlocal

