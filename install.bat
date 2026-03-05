@echo off
echo ========================================
echo UA Library Room Booker - Installation
echo ========================================
echo.

echo Checking Python installation...
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ERROR: Python is not installed or not in PATH.
    echo.
    echo Please install Python first:
    echo 1. Go to https://www.python.org/downloads/
    echo 2. Download Python 3.11 or newer
    echo 3. Run the installer
    echo 4. CHECK THE BOX "Add Python to PATH"
    echo 5. Click "Install Now"
    echo 6. Restart your computer
    echo.
    echo Then run this installer again.
    pause
    exit /b 1
)

echo Python found!
echo.
echo Installing required packages...
python -m pip install -r requirements.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install packages.
    echo Please try running as administrator.
    pause
    exit /b 1
)

echo.
echo ========================================
echo Installation complete!
echo ========================================
echo.
echo To run the application, double-click run.bat
echo Or run: python main.py
echo.
pause
