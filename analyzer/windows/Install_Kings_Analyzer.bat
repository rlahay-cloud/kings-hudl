@echo off
setlocal
cd /d "%~dp0"
title Installing Kings HUDL Game Analyzer
echo.
echo Installing the Kings HUDL Game Analyzer. First time only, about 10 to 25 minutes.
echo Keep this window open until it says DONE.
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
echo Using %PY%
if not exist ".venv\Scripts\python.exe" (
  %PY% -m venv .venv
  if errorlevel 1 ( echo Could not set up the program folder. & pause & exit /b 1 )
)
".venv\Scripts\python.exe" -m pip install --upgrade pip
echo.
echo Step 1 of 3: the vision engine (about 200 MB)...
".venv\Scripts\python.exe" -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 ( echo That step failed. Check the internet connection and run this file again. & pause & exit /b 1 )
echo.
echo Step 2 of 3: the other parts...
".venv\Scripts\python.exe" -m pip install -r requirements-windows.txt
if errorlevel 1 ( echo That step failed. Check the internet connection and run this file again. & pause & exit /b 1 )
echo.
echo Step 3 of 3: downloading the player finder and number reader...
if not exist models mkdir models
pushd models
"..\.venv\Scripts\python.exe" -c "from ultralytics import YOLO; YOLO('yolov8s.pt'); YOLO('yolov8n-cls.pt'); import easyocr; easyocr.Reader(['en'], gpu=False); print('models ready')"
if errorlevel 1 ( popd & echo That step failed. Check the internet connection and run this file again. & pause & exit /b 1 )
popd
powershell -NoProfile -Command "$s=(New-Object -ComObject WScript.Shell).CreateShortcut([Environment]::GetFolderPath('Desktop')+'\Kings Analyzer.lnk');$s.TargetPath='%~dp0Start_Kings_Analyzer.bat';$s.WorkingDirectory='%~dp0';$s.Save()" >nul 2>&1
echo.
echo DONE. A "Kings Analyzer" shortcut is now on your desktop. Double click it to start.
pause
