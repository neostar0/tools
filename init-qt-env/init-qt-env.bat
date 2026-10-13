@echo off
rem init-qt-env: resolve the Qt/QML runtime and set QMLSCENE (and QT_ROOT
rem when the kit root is known) in the CALLER's console, vcvarsall-style.
rem Must be `call`ed. Deliberately no setlocal: the variables are the point.

set "QMLSCENE="

if defined QT_ROOT goto :check_qt_root

if exist "C:\Qt\5.15.2\msvc2019_64\bin\qmlscene.exe" goto :use_default

for /f "delims=" %%i in ('where qmlscene 2^>nul') do if not defined QMLSCENE set "QMLSCENE=%%i"
if defined QMLSCENE goto :report

for /f "delims=" %%i in ('where qmlscene6 2^>nul') do if not defined QMLSCENE set "QMLSCENE=%%i"
if defined QMLSCENE goto :report_qt6
for /f "delims=" %%i in ('where qml6 2^>nul') do if not defined QMLSCENE set "QMLSCENE=%%i"
if defined QMLSCENE goto :report_qt6

echo [init-qt-env] ERROR: no QML runtime found: looked in QT_ROOT, C:\Qt\5.15.2\msvc2019_64, then PATH
exit /b 1

:check_qt_root
if exist "%QT_ROOT%\bin\qmlscene.exe" goto :use_qt_root
echo [init-qt-env] ERROR: QT_ROOT is set to %QT_ROOT% but %QT_ROOT%\bin\qmlscene.exe does not exist
echo [init-qt-env] Fix QT_ROOT (or run "set QT_ROOT=" to clear it) and try again.
exit /b 1

:use_qt_root
set "QMLSCENE=%QT_ROOT%\bin\qmlscene.exe"
goto :report

:use_default
set "QT_ROOT=C:\Qt\5.15.2\msvc2019_64"
set "QMLSCENE=%QT_ROOT%\bin\qmlscene.exe"
goto :report

:report_qt6
echo [init-qt-env] WARNING: Qt 6 runtime - a file written for Qt 5 may fail to load

:report
echo [init-qt-env] QMLSCENE=%QMLSCENE%
if defined QT_ROOT echo [init-qt-env] QT_ROOT=%QT_ROOT%  (kit root; also what qgc4-builder reads)
if not defined QT_ROOT echo [init-qt-env] QT_ROOT not set - the runtime was found on PATH only
exit /b 0
