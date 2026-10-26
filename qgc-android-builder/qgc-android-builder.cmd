@echo off
setlocal

set "SCRIPT=%~dp0internal\build_android.py"

if "%~1"=="" goto :run
if "%~1"=="-h" goto :usage
if "%~1"=="--help" goto :usage

:run
python "%SCRIPT%" %*
exit /b %ERRORLEVEL%

:usage
type "%~dp0internal\usage.md"
exit /b 2
