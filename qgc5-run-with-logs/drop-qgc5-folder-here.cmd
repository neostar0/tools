@echo off
setlocal

start "QGC5 Launcher" python "%~dp0internal\run_qgc5.py" --pause %*
exit /b 0
