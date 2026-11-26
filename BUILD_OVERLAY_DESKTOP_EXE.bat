@echo off
setlocal
cd /d "%~dp0"
echo Builds a local Windows executable. PyInstaller must be installed first.
if exist ".venv\Scripts\python.exe" (
  set "PY=.venv\Scripts\python.exe"
) else (
  set "PY=py -3"
)
%PY% -m PyInstaller --noconfirm --clean --windowed --name ArchiCordOverlay ^
  --collect-submodules tracker --add-data "webui_assets;webui_assets" overlay_desktop.py
if errorlevel 1 (
  echo PyInstaller build failed. Run: py -3 -m pip install pyinstaller
  pause
  exit /b 1
)
echo Done. dist\ArchiCordOverlay
pause
