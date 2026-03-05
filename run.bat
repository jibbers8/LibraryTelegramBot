@echo off
echo Starting UA Library Room Booker...
python main.py
if errorlevel 1 (
    echo.
    echo Error: Python is not installed or not in PATH.
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    pause
)
