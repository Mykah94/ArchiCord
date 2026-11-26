@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\pythonw.exe" (
  start "" ".venv\Scripts\pythonw.exe" overlay_desktop.py
) else (
  start "" pyw -3 overlay_desktop.py
)
