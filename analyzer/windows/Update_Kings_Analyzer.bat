@echo off
cd /d "%~dp0"
title Updating Kings HUDL Game Analyzer
if not exist ".venv\Scripts\python.exe" (
  echo Please run Install_Kings_Analyzer.bat first.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" update.py
echo.
echo Done. Your results, learned.json and installed parts were not touched.
pause
