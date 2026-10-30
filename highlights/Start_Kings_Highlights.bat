@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Please run Install_Kings_Highlights.bat first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" kings_highlights_app.py
