@echo off
setlocal
cd /d "%~dp0"
title Installing Kings Highlight Video
echo.
echo Installing Kings Highlight Video. First time only, about 2 minutes.
echo.
set "PY="
for %%V in (3.12 3.11 3.10) do (
  if not defined PY (
    py -%%V -c "import tkinter, sys" >nul 2>&1 && set "PY=py -%%V"
  )
)
if not defined PY (
  echo Python was not found on this computer. Installing Python 3.11 now...
  winget install -e --id Python.Python.3.11 --accept-package-agreements --accept-source-agreements --silent
  py -3.11 -c "import tkinter, sys" >nul 2>&1 && set "PY=py -3.11"
)
if not defined PY (
  echo.
  echo I could not install Python by myself.
  echo Please install Python 3.11 from https://www.python.org/downloads/ and tick "Add python.exe to PATH"
  echo on the first screen. Then double click this file again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
  if errorlevel 1 ( echo Could not set up the program folder. & pause & exit /b 1 )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 ( echo That step failed. Check the internet connection and run this file again. & pause & exit /b 1 )
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Kings Highlight Video.lnk');$s.TargetPath='%~dp0Start_Kings_Highlights.bat';$s.WorkingDirectory='%~dp0';$s.Save()" >nul 2>&1
echo.
echo DONE. A "Kings Highlight Video" shortcut is now on your desktop. Double click it to start.
pause
