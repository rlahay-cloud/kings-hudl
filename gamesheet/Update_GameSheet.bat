@echo off
cd /d "%~dp0"
title Kings Film Room GameSheet updater
where py >nul 2>nul
if errorlevel 1 (
  echo Python is not installed. Install it from https://www.python.org/downloads/ and tick "Add Python to PATH".
  pause
  exit /b
)
if not exist ".ready" (
  echo First time setup. This takes a few minutes and only happens once.
  py -m pip install --upgrade playwright
  py -m playwright install chromium
  echo done> .ready
)
py update_gamesheet.py
echo.
echo All finished. You can close this window.
pause
