@echo off
setlocal

if not "%~2"=="" goto :usage
if "%~1"=="max" goto :run
if "%~1"=="restore" goto :run
if "%~1"=="full" goto :run
goto :usage

:run
call "%~dp0..\set-window-state\set-window-state.cmd" QGroundControl "%~1"
exit /b %ERRORLEVEL%

:usage
type "%~dp0internal\usage.md"
pause
exit /b 2
