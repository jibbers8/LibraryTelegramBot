@echo off
echo Closing any running Chrome...
taskkill /F /IM chrome.exe >nul 2>&1
timeout /t 2 >nul

echo Starting Chrome with remote debugging...
start chrome --remote-debugging-port=9222

echo.
echo Chrome should be open now.
echo Make sure you're logged into the library website.
echo Then run the booking app (run.bat).
echo.
pause
