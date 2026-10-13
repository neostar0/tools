@echo off
setlocal

if "%~1"=="" goto :usage
if not "%~2"=="" goto :usage

set "NAME=%~1"

taskkill /IM "%NAME%"

for /L %%i in (1,1,3) do (
    tasklist /FI "IMAGENAME eq %NAME%" /NH | find /I "%NAME%" >nul
    if errorlevel 1 (
        echo [OK] %NAME% exited gracefully.
        exit /b 0
    )
    timeout /t 1 /nobreak >nul
)

taskkill /F /IM "%NAME%"

tasklist /FI "IMAGENAME eq %NAME%" /NH | find /I "%NAME%" >nul
if errorlevel 1 exit /b 0

echo [FAIL] %NAME% survived.
exit /b 1

:usage
type "%~dp0internal\usage.md"
pause
exit /b 2
