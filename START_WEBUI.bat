@echo off
setlocal
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -u webui.py
  goto DONE
)

where py >nul 2>nul
if not errorlevel 1 (
  py -3.13 -u webui.py
  if not errorlevel 1 goto DONE
  echo Python 3.13 konnte nicht gestartet werden. Versuche Standard-Python ...
)

where python >nul 2>nul
if not errorlevel 1 (
  python -u webui.py
) else (
  echo Python wurde nicht gefunden. Bitte Python 3.11 oder 3.13 installieren.
)

:DONE
echo.
echo ArchiCord WebUI wurde beendet. Eventuelle Fehler stehen oben.
pause
