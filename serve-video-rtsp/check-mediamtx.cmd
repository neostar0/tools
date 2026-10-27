@echo off
setlocal EnableExtensions

rem Make sure mediamtx.exe lives in this tool's internal\bin, downloading the
rem pinned GitHub release when it is missing. Values that a download can fail
rem to produce travel in environment variables, never on a command line.

set "BIN=%~dp0internal\bin"
set "VER=1.21.2"
set "FORCE="

:parse
if "%~1"=="" goto :parsed
if /I "%~1"=="-h" goto :usage
if /I "%~1"=="--help" goto :usage
if /I "%~1"=="/?" goto :usage
if /I "%~1"=="--force" goto :opt_force
set "ARG=%~1"
if "%ARG:~0,1%"=="-" goto :bad_option
echo [check-mediamtx] ERROR: unexpected argument: "%ARG%"
goto :usage_bad

:bad_option
echo [check-mediamtx] ERROR: unknown option: "%ARG%"
goto :usage_bad

:opt_force
set "FORCE=1"
shift
goto :parse

:parsed
if defined FORCE goto :install
if not exist "%BIN%\mediamtx.exe" goto :install
"%BIN%\mediamtx.exe" --version >nul 2>nul
if errorlevel 1 goto :install
echo [check-mediamtx] already installed: "%BIN%\mediamtx.exe"
exit /b 0

:install
set "ARCH=amd64"
if /I "%PROCESSOR_ARCHITECTURE%"=="ARM64" set "ARCH=arm64"
if /I "%PROCESSOR_ARCHITECTURE%"=="AMD64" set "ARCH=amd64"
set "ASSET=mediamtx_v%VER%_windows_%ARCH%.zip"
set "MTX_URL=https://github.com/bluenviron/mediamtx/releases/download/v%VER%/%ASSET%"
set "MTX_SUM_URL=https://github.com/bluenviron/mediamtx/releases/download/v%VER%/checksums.sha256"
set "TMPDIR=%TEMP%\mediamtx-%RANDOM%-%RANDOM%"
set "MTX_ASSET=%ASSET%"
set "MTX_ZIP=%TMPDIR%\%ASSET%"
set "MTX_SUM=%TMPDIR%\checksums.sha256"
set "MTX_TMP=%TMPDIR%"

if not exist "%BIN%" mkdir "%BIN%"
if exist "%TMPDIR%" rmdir /S /Q "%TMPDIR%" 2>nul
mkdir "%TMPDIR%" 2>nul
if not exist "%TMPDIR%" goto :tmpfail

echo [check-mediamtx] downloading %ASSET% (v%VER%) ...
powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing -Uri $env:MTX_URL -OutFile $env:MTX_ZIP"
if errorlevel 1 goto :dlfail
powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing -Uri $env:MTX_SUM_URL -OutFile $env:MTX_SUM"
if errorlevel 1 goto :dlfail

powershell -NoProfile -Command "$l=Get-Content $env:MTX_SUM | Where-Object { $_ -match ([regex]::Escape($env:MTX_ASSET)) + '$' } | Select-Object -First 1; if(-not $l){ exit 1 }; $w=($l -split '\s+')[0].ToLower(); $h=(Get-FileHash -Algorithm SHA256 -Path $env:MTX_ZIP).Hash.ToLower(); if($w -ne $h){ exit 1 }"
if errorlevel 1 goto :sumfail

powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force -Path $env:MTX_ZIP -DestinationPath $env:MTX_TMP"
set "SRC="
for /r "%TMPDIR%" %%F in (mediamtx.exe) do if not defined SRC set "SRC=%%F"
if defined SRC goto :have_bin
tar -xf "%MTX_ZIP%" -C "%MTX_TMP%" 2>nul
for /r "%TMPDIR%" %%F in (mediamtx.exe) do if not defined SRC set "SRC=%%F"
if not defined SRC goto :extractfail

:have_bin
copy /Y "%SRC%" "%BIN%\mediamtx.exe" >nul
if not exist "%BIN%\mediamtx.exe" goto :copyfail
rmdir /S /Q "%TMPDIR%" 2>nul
echo [check-mediamtx] installed: "%BIN%\mediamtx.exe" (v%VER%)
"%BIN%\mediamtx.exe" --version
exit /b 0

:usage
type "%~dp0internal\usage.md"
exit /b 0

:usage_bad
type "%~dp0internal\usage.md"
pause
exit /b 2

:dlfail
echo [check-mediamtx] ERROR: download failed: %MTX_URL%
goto :fail
:sumfail
echo [check-mediamtx] ERROR: checksum mismatch for %ASSET%
goto :fail
:extractfail
echo [check-mediamtx] ERROR: the %ASSET% archive contains no mediamtx.exe
goto :fail
:copyfail
echo [check-mediamtx] ERROR: could not write "%BIN%\mediamtx.exe"
goto :fail
:tmpfail
echo [check-mediamtx] ERROR: could not create a temporary directory under %TEMP%
:fail
if exist "%TMPDIR%" rmdir /S /Q "%TMPDIR%" 2>nul
exit /b 1
