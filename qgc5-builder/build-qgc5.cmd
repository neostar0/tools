@echo off
setlocal

if "%~1"=="-h" goto :usage
if "%~1"=="--help" goto :usage

python "%~dp0internal\build_qgc5.py" %*
exit /b %ERRORLEVEL%

:usage
type "%~dp0internal\usage.md"
exit /b 0
