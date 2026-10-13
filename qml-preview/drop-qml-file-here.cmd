@echo off
setlocal

if "%~1"=="" goto :usage

set "INIT=%~dp0..\init-qt-env\init-qt-env.bat"
if not exist "%INIT%" goto :no_init
call "%INIT%"
if errorlevel 1 goto :no_runtime

set "QML_DISABLE_DISK_CACHE=1"
set "FAILED="

:loop
if "%~1"=="" goto :done
rem qmlscene prints "does not exist." for a missing path but still exits 0,
rem so existence is checked here instead of reporting a false success. A
rem folder is passed through: the runtime rejects it with its own error.
if not exist "%~f1" goto :not_file
echo [QmlPreview] Opened: %~f1  (close the window to finish)
"%QMLSCENE%" "%~f1"
if %errorlevel%==0 goto :closed
echo [QmlPreview] FAILED: %~f1  (runtime exit %errorlevel%) - see the QML errors above
set "FAILED=1"
shift
goto :loop

:closed
echo [QmlPreview] Closed: %~f1
shift
goto :loop

:not_file
echo [QmlPreview] ERROR: not a file: %~f1
set "FAILED=1"
shift
goto :loop

:done
echo.
if defined FAILED goto :failed_run
echo [QmlPreview] RESULT: OK - every preview closed cleanly  (exit 0)
pause
exit /b 0

:failed_run
echo [QmlPreview] RESULT: FAILED  (exit 1)
pause
exit /b 1

:no_init
echo [QmlPreview] ERROR: sibling tool not found: %INIT%
echo [QmlPreview] init-qt-env must sit next to this folder: tools\init-qt-env\
pause
exit /b 3

:no_runtime
echo.
echo [QmlPreview] No QML runtime found - init-qt-env reported the reason above.
pause
exit /b 3

:usage
type "%~dp0internal\usage.md"
pause
exit /b 2
