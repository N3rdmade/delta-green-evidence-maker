@echo off
setlocal
cd /d "%~dp0"
title Evidence Photo Composer - Setup

echo Evidence Photo Composer now performs all first-time setup automatically.
echo.
echo START.bat will:
echo   1. Install Python 3 if it is missing.
echo   2. Install Flask and Pillow if they are missing.
echo   3. Launch the composer.
echo.
echo Press any key to start setup now.
pause >nul
call "%~dp0START.bat"
endlocal
