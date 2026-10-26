@echo off
setlocal

set "SCRIPT=%~dp0internal\run_apk_on_avd.py"

if "%~1"=="" goto :usage
if "%~1"=="-h" goto :usage
if "%~1"=="--help" goto :usage

:loop
if "%~1"=="" goto :done

echo.
echo Source: %~f1
python "%SCRIPT%" "%~f1"
if errorlevel 1 (
    echo FAILED: %~f1
    goto :failed
)
echo Done: %~f1

shift
goto :loop

:done
echo.
echo APK launched on the virtual device.
exit /b 0

:failed
echo.
echo Launch failed.
exit /b 1

:usage
type "%~dp0internal\usage.md"
exit /b 2
