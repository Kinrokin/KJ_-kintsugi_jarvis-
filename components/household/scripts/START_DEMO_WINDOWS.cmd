@echo off
setlocal
cd /d "%~dp0.."
set PYTHONDONTWRITEBYTECODE=1
where py >nul 2>nul
if errorlevel 1 (
  echo Python launcher was not found. Nothing has been installed or changed.
  echo Open README.md for the existing-Python alternative.
  pause
  exit /b 1
)
py -3 -m jarvis.cli doctor
if errorlevel 1 exit /b 1
py -3 -m jarvis.cli --state "%LOCALAPPDATA%\KintsugiJarvis\demo-3_2" demo --serve
pause
