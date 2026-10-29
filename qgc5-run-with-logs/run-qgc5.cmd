@echo off
setlocal

set "ARGS=%*"
if "%~1"=="-h" goto :usage
if "%~1"=="--help" goto :usage
echo %ARGS% | findstr /C:"--help" >nul && goto :usage
echo %ARGS% | findstr /C:"-h" >nul && goto :usage

python "%~dp0internal\run_qgc5.py" %ARGS%
exit /b %ERRORLEVEL%

:usage
type "%~dp0internal\usage.md"
exit /b 0
