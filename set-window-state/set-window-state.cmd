@echo off
setlocal

if "%~1"=="" goto :usage

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0internal\window_state.ps1" %*
exit /b %ERRORLEVEL%

:usage
type "%~dp0internal\usage.md"
pause
exit /b 2
