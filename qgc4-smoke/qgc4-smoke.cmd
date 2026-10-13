@echo off
setlocal

python "%~dp0internal\smoke_qgc.py" %*
exit /b %ERRORLEVEL%
