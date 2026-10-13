@echo off
call "%~dp0..\stop-process\stop-process.cmd" QGroundControl.exe
exit /b %ERRORLEVEL%
