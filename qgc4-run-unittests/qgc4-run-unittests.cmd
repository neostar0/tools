@echo off
setlocal

python "%~dp0internal\run_unittests.py" %*
exit /b %ERRORLEVEL%
