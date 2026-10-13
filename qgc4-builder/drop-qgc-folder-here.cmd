@echo off
setlocal

if "%~1"=="" goto :usage

call "%~dp0internal\build-qgc.cmd" %*
set "RC=%ERRORLEVEL%"
echo.
pause
exit /b %RC%

:usage
type "%~dp0internal\usage.md"
echo.
pause
exit /b 2
