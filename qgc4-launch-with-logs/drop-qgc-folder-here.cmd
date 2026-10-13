@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
if "%SCRIPT_DIR:~-1%"=="\" set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"

start "QGC Launcher" python "%SCRIPT_DIR%\internal\launch_qgc.py" %*
if errorlevel 1 goto :failed

echo [Launcher] QGC is running in the "QGC Launcher" window.
exit /b 0

:failed
echo ERROR: Failed to start QGC Launcher.
pause
exit /b 1
