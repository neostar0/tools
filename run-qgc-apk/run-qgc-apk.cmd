@echo off
setlocal

set "SCRIPT=%~dp0run-qgc-apk.sh"

rem Forward the optional QGC root and every run-apk-on-avd option unchanged.
rem With no arguments, run-qgc-apk.sh locates the QGC checkout itself.
bash "%SCRIPT%" %*
exit /b %ERRORLEVEL%
