@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo Please run Install_Kings_Analyzer.bat first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" kings_analyzer_app.py
