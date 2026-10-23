@echo off
cd /d "%~dp0"
title Launching Pro AutoClicker...

:: Verify python is installed
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Python was not found in your system PATH.
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

:: Install requirements if needed
python -c "import customtkinter, pynput" >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Installing required packages (customtkinter, pynput)...
    python -m pip install -r requirements.txt
    if %ERRORLEVEL% neq 0 (
        echo Failed to install dependencies.
        pause
        exit /b 1
    )
)

:: Launch with pythonw (no terminal) or python
where pythonw >nul 2>&1
if %ERRORLEVEL% equ 0 (
    start "" pythonw autoclicker.py
) else (
    start "" python autoclicker.py
)
exit /b 0

