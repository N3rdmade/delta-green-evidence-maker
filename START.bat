@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Evidence Photo Composer

rem ============================================================
rem Evidence Photo Composer bootstrap
rem - Finds an existing Python 3 installation
rem - Installs Python automatically when missing
rem - Installs Flask/Pillow automatically when missing
rem - Launches the composer
rem ============================================================

call :FindPython
if defined PYEXE goto :PythonReady

echo.
echo ============================================================
echo  Python 3 was not found - installing it automatically...
echo ============================================================
echo.

rem First choice: Windows Package Manager.
where winget >nul 2>&1
if not errorlevel 1 (
    echo Installing Python 3.13 with Windows Package Manager...
    winget install --id Python.Python.3.13 --exact --scope user --silent --accept-package-agreements --accept-source-agreements
)

rem A newly-installed Python may not be on this Command Prompt's PATH yet,
rem so FindPython also checks the normal Python installation folders.
call :FindPython
if defined PYEXE goto :PythonReady

rem Fallback when winget is unavailable or could not install Python.
rem Download the official Python installer from python.org and install it
rem for the current Windows user, including pip and the Python launcher.
echo.
echo Windows Package Manager did not provide Python.
echo Downloading the official Python installer from python.org...
set "PYINSTALLER=%TEMP%\evidence-photo-composer-python-installer.exe"
set "PYURL=https://www.python.org/ftp/python/3.13.7/python-3.13.7-amd64.exe"
if /I "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "PYURL=https://www.python.org/ftp/python/3.13.7/python-3.13.7-arm64.exe"

powershell -NoProfile -ExecutionPolicy Bypass -Command "$ProgressPreference='SilentlyContinue'; try { Invoke-WebRequest -UseBasicParsing -Uri '%PYURL%' -OutFile '%PYINSTALLER%'; exit 0 } catch { Write-Host $_.Exception.Message; exit 1 }"
if errorlevel 1 goto :PythonInstallFailed
if not exist "%PYINSTALLER%" goto :PythonInstallFailed

echo Installing Python. This may take a minute...
start /wait "" "%PYINSTALLER%" /quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_pip=1 Include_test=0 SimpleInstall=1
set "INSTALL_RESULT=%ERRORLEVEL%"
del /q "%PYINSTALLER%" >nul 2>&1
if not "%INSTALL_RESULT%"=="0" goto :PythonInstallFailed

call :FindPython
if not defined PYEXE goto :PythonInstallFailed

:PythonReady
echo Python found: "%PYEXE%" %PYARGS%

rem Check the Python packages the composer needs.
"%PYEXE%" %PYARGS% -c "import flask, PIL" >nul 2>&1
if not errorlevel 1 goto :Launch

echo.
echo ============================================================
echo  First-time setup - installing required Python packages...
echo ============================================================
echo.

"%PYEXE%" %PYARGS% -m pip --version >nul 2>&1
if errorlevel 1 (
    "%PYEXE%" %PYARGS% -m ensurepip --upgrade
    if errorlevel 1 goto :DependencyInstallFailed
)

"%PYEXE%" %PYARGS% -m pip install --disable-pip-version-check -r "%~dp0requirements.txt"
if errorlevel 1 goto :DependencyInstallFailed

rem Final verification before launching.
"%PYEXE%" %PYARGS% -c "import flask, PIL" >nul 2>&1
if errorlevel 1 goto :DependencyInstallFailed

:Launch
echo.
echo Starting Evidence Photo Composer...
"%PYEXE%" %PYARGS% "%~dp0photo_composer.py"
if errorlevel 1 (
    echo.
    echo The composer exited with an error. See the message above.
    pause
)
goto :End

:PythonInstallFailed
echo.
echo ============================================================
echo  ERROR: Python could not be installed automatically.
echo ============================================================
echo.
echo The automatic installer could not finish. Check your internet
echo connection / Windows permissions, then run START.bat again.
echo.
echo You can also install Python 3 manually from python.org and then
echo run START.bat again.
echo.
pause
goto :End

:DependencyInstallFailed
echo.
echo ============================================================
echo  ERROR: Flask or Pillow could not be installed.
echo ============================================================
echo.
echo Try running START.bat again. If it still fails, run:
echo.
echo   "%PYEXE%" %PYARGS% -m pip install -r requirements.txt
echo.
pause
goto :End

:FindPython
set "PYEXE="
set "PYARGS="

rem Prefer the Python launcher when it already has Python 3.
py -3 --version >nul 2>&1
if not errorlevel 1 (
    set "PYEXE=py"
    set "PYARGS=-3"
    goto :eof
)

rem Try python.exe on PATH. Avoid the Microsoft Store alias when it fails.
python --version >nul 2>&1
if not errorlevel 1 (
    set "PYEXE=python"
    goto :eof
)

rem Look in standard per-user installation directories. This also finds
rem Python immediately after a silent install without reopening Command Prompt.
for /d %%D in ("%LocalAppData%\Programs\Python\Python3*") do (
    if exist "%%~fD\python.exe" (
        set "PYEXE=%%~fD\python.exe"
        goto :eof
    )
)

rem Look in common all-user installation directories as a final check.
for /d %%D in ("%ProgramFiles%\Python3*") do (
    if exist "%%~fD\python.exe" (
        set "PYEXE=%%~fD\python.exe"
        goto :eof
    )
)

goto :eof

:End
endlocal
