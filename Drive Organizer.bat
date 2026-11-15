@echo off
rem Drive Organizer - Windows launcher. Double-click to start the app.
rem First run: creates a private Python environment in .venv and installs what the app needs.

setlocal
pushd "%~dp0"
title Drive Organizer

set "PY="
py -3 -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>nul && set "PY=py -3"
if not defined PY (
  python -c "import sys; sys.exit(sys.version_info < (3, 9))" >nul 2>nul && set "PY=python"
)
if not defined PY (
  echo Drive Organizer needs Python 3.9 or newer. Trying to install it for you...
  winget install --id Python.Python.3.12 -e --scope user --accept-source-agreements --accept-package-agreements
  echo.
  echo If Python installed, close this window and double-click "Drive Organizer.bat" again.
  echo If it did not, install Python from https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^).
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  echo First run: setting up ^(takes a few minutes^)...
  %PY% -m venv .venv
  if errorlevel 1 (
    echo Setup failed.
    pause
    exit /b 1
  )
)

rem Install (or update) dependencies whenever requirements.txt changes
fc /b requirements.txt ".venv\requirements-installed.txt" >nul 2>nul
if errorlevel 1 (
  echo Installing what the app needs...
  ".venv\Scripts\python.exe" -m pip install --quiet --upgrade pip
  ".venv\Scripts\python.exe" -m pip install -r requirements.txt
  if errorlevel 1 (
    echo Install failed - check your internet connection.
    pause
    exit /b 1
  )
  copy /y requirements.txt ".venv\requirements-installed.txt" >nul
)

".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
