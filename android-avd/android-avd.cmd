@echo off
setlocal

set "SCRIPT=%~dp0internal\android_avd.py"

if "%~1"=="" goto :usage
if "%~1"=="-h" goto :usage
if "%~1"=="--help" goto :usage

python "%SCRIPT%" %*
exit /b %ERRORLEVEL%

:usage
type "%~dp0internal\usage.md"
exit /b 2
