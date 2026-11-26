@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" overlay_studio.py
) else (
  py -3 overlay_studio.py
)
if errorlevel 1 (
  echo ArchiCord Overlay Studio konnte nicht gestartet werden.
  pause
)
