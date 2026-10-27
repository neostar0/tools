@echo off
setlocal EnableExtensions

rem Serve a video file as a looping RTSP stream: mediamtx.exe is the RTSP
rem server, ffmpeg.exe loops the file into it as a publisher, and the rtsp://
rem URL is printed. Values that come from the caller travel to the children as
rem environment variables (see internal\start-process.ps1), never as command
rem line text - a file named "a & b.mp4" must not be able to inject syntax.

set "TOOL=%~dp0"
set "BIN=%TOOL%internal\bin"
set "RUN=%TOOL%internal\runtime"
set "START=%TOOL%internal\start-process.ps1"
set "MTX_PIDFILE=%RUN%\mediamtx.pid"
set "FF_PIDFILE=%RUN%\ffmpeg.pid"
set "CFG=%RUN%\mediamtx.yml"
set "NAME=stream"
set "PORT=8554"
set "FILE="
set "STOP="

:parse
if "%~1"=="" goto :parsed
if /I "%~1"=="-h" goto :usage
if /I "%~1"=="--help" goto :usage
if /I "%~1"=="/?" goto :usage
if /I "%~1"=="--stop" goto :opt_stop
if /I "%~1"=="-n" goto :opt_name
if /I "%~1"=="--name" goto :opt_name
if /I "%~1"=="-p" goto :opt_port
if /I "%~1"=="--port" goto :opt_port
if defined FILE goto :two_files
set "FILE=%~f1"
shift
goto :parse

:opt_stop
set "STOP=1"
shift
goto :parse

:opt_name
if "%~2"=="" goto :name_needs_value
set "NAME=%~2"
shift
shift
goto :parse

:opt_port
if "%~2"=="" goto :port_needs_value
set "PORT=%~2"
shift
shift
goto :parse

:name_needs_value
echo [serve-video-rtsp] ERROR: -n/--name needs a value
goto :usage_bad

:port_needs_value
echo [serve-video-rtsp] ERROR: -p/--port needs a value
goto :usage_bad

:two_files
echo [serve-video-rtsp] ERROR: only one video file may be given
goto :usage_bad

:parsed
set "RTSP_NAME=%NAME%"
powershell -NoProfile -Command "if($env:RTSP_NAME -match '^[A-Za-z0-9_.-]+$'){ exit 0 } else { exit 1 }"
if errorlevel 1 goto :bad_name
set "RTSP_PORT=%PORT%"
powershell -NoProfile -Command "if($env:RTSP_PORT -match '^[0-9]{1,5}$' -and [int]$env:RTSP_PORT -ge 1 -and [int]$env:RTSP_PORT -le 65535){ exit 0 } else { exit 1 }"
if errorlevel 1 goto :bad_port
if defined STOP goto :stop
if not defined FILE goto :usage_bad
if exist "%FILE%" goto :checked_file
echo [serve-video-rtsp] ERROR: not a file: "%FILE%"
exit /b 1

:bad_name
echo [serve-video-rtsp] ERROR: invalid RTSP path name: "%NAME%"
goto :usage_bad

:bad_port
echo [serve-video-rtsp] ERROR: invalid port: "%PORT%"
goto :usage_bad

:checked_file
call :pidfile_running "%MTX_PIDFILE%" mediamtx
if not errorlevel 1 goto :already_running
call :pidfile_running "%FF_PIDFILE%" ffmpeg
if not errorlevel 1 goto :already_running
del "%MTX_PIDFILE%" 2>nul
del "%FF_PIDFILE%" 2>nul

netstat -ano -p tcp | findstr "LISTENING" | findstr /C:":%PORT%" >nul
if not errorlevel 1 goto :port_busy

echo [serve-video-rtsp] checking mediamtx
call "%TOOL%check-mediamtx.cmd"
if errorlevel 1 exit /b 1

set "FFMPEG=%BIN%\ffmpeg.exe"
if exist "%FFMPEG%" goto :have_ffmpeg
where ffmpeg.exe >nul 2>nul
if errorlevel 1 goto :install_ffmpeg
set "FFMPEG=ffmpeg.exe"
goto :have_ffmpeg

:install_ffmpeg
echo [serve-video-rtsp] ffmpeg not found - downloading the static build once
if not exist "%RUN%" mkdir "%RUN%"
set "FF_URL=https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
set "FF_ZIP=%RUN%\ffmpeg.zip"
set "FF_XDIR=%RUN%\ffmpeg-x"
if exist "%FF_ZIP%" del "%FF_ZIP%" 2>nul
if exist "%FF_XDIR%" rmdir /S /Q "%FF_XDIR%" 2>nul
powershell -NoProfile -Command "Invoke-WebRequest -UseBasicParsing -Uri $env:FF_URL -OutFile $env:FF_ZIP"
if errorlevel 1 goto :ff_failed
powershell -NoProfile -ExecutionPolicy Bypass -Command "Expand-Archive -Force -Path $env:FF_ZIP -DestinationPath $env:FF_XDIR"
set "SRC="
for /r "%FF_XDIR%" %%F in (ffmpeg.exe) do if not defined SRC set "SRC=%%F"
if not defined SRC goto :ff_failed
if not exist "%BIN%" mkdir "%BIN%"
copy /Y "%SRC%" "%BIN%\ffmpeg.exe" >nul
if not exist "%BIN%\ffmpeg.exe" goto :ff_failed
del "%FF_ZIP%" 2>nul
rmdir /S /Q "%FF_XDIR%" 2>nul
set "FFMPEG=%BIN%\ffmpeg.exe"
goto :have_ffmpeg

:ff_failed
echo [serve-video-rtsp] ERROR: could not obtain ffmpeg - install it and put ffmpeg.exe in "%BIN%"
exit /b 1

:have_ffmpeg
if not exist "%RUN%" mkdir "%RUN%"

> "%CFG%" echo(logLevel: info
>> "%CFG%" echo(logDestinations: [file]
>> "%CFG%" echo(logFile: "%RUN%\mediamtx.log"
>> "%CFG%" echo(rtspAddress: ":%PORT%"
>> "%CFG%" echo(paths:
>> "%CFG%" echo(  %NAME%:
>> "%CFG%" echo(    source: publisher

echo [serve-video-rtsp] starting mediamtx on port %PORT%
set "MTX_EXE=%BIN%\mediamtx.exe"
set "MTX_CFG=%CFG%"
set "MTX_OUT=%RUN%\mediamtx.out"
set "MTX_ERR=%RUN%\mediamtx.err"
set "MTX_PID="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%START%" -Kind mtx 2^>nul`) do set "MTX_PID=%%P"
if not defined MTX_PID goto :start_failed
set "RTSP_PID=%MTX_PID%"
powershell -NoProfile -Command "if($env:RTSP_PID -match '^[0-9]+$'){ exit 0 } else { exit 1 }"
if errorlevel 1 goto :start_failed
> "%MTX_PIDFILE%" echo(%MTX_PID%
set "WAITED=0"
call :wait_for_port
if errorlevel 1 goto :mtx_failed

echo [serve-video-rtsp] publishing "%FILE%" (loops forever)
call :start_ffmpeg "-c copy"
if not defined FF_PID goto :ffmpeg_start_failed
ping -n 3 127.0.0.1 >nul
call :ffmpeg_alive
if not errorlevel 1 goto :stream_up
echo [serve-video-rtsp] stream copy was rejected - retrying with an H.264/AAC transcode
call :start_ffmpeg "-c:v libx264 -preset veryfast -pix_fmt yuv420p -c:a aac"
if not defined FF_PID goto :ffmpeg_start_failed
ping -n 4 127.0.0.1 >nul
call :ffmpeg_alive
if not errorlevel 1 goto :stream_up
echo [serve-video-rtsp] ERROR: ffmpeg could not publish "%FILE%" - its log follows
if exist "%RUN%\ffmpeg.log" type "%RUN%\ffmpeg.log"
call :cleanup
exit /b 1

:stream_up
set "IP_URL="
for /f "usebackq delims=" %%I in (`powershell -NoProfile -Command "$e=[System.Net.Dns]::GetHostEntry($env:COMPUTERNAME); $a=@($e.AddressList | Where-Object { $_.AddressFamily -eq 'InterNetwork' }); if($a.Count){ $a[0].IPAddressToString }" 2^>nul`) do set "IP_URL=%%I"
if not defined IP_URL set "IP_URL=127.0.0.1"
echo(
echo [serve-video-rtsp] RTSP ready
echo(    rtsp://%IP_URL%:%PORT%/%NAME%
echo(    rtsp://127.0.0.1:%PORT%/%NAME%    (this machine)
echo(    video:  "%FILE%"   (loops forever)
echo(    logs:   "%RUN%\mediamtx.log", "%RUN%\ffmpeg.log"
echo(    stop:   serve-video-rtsp.cmd --stop
exit /b 0

:start_failed
echo [serve-video-rtsp] ERROR: could not start mediamtx - see "%RUN%\mediamtx.log"
if exist "%RUN%\mediamtx.err" type "%RUN%\mediamtx.err"
if exist "%RUN%\mediamtx.out" type "%RUN%\mediamtx.out"
exit /b 1

:mtx_failed
echo [serve-video-rtsp] ERROR: mediamtx did not open port %PORT% - see "%RUN%\mediamtx.log"
if exist "%RUN%\mediamtx.err" type "%RUN%\mediamtx.err"
if exist "%RUN%\mediamtx.out" type "%RUN%\mediamtx.out"
call :cleanup
exit /b 1

:ffmpeg_start_failed
echo [serve-video-rtsp] ERROR: could not start ffmpeg
call :cleanup
exit /b 1

:already_running
echo [serve-video-rtsp] ERROR: already running - run "serve-video-rtsp.cmd --stop" first
exit /b 1

:port_busy
echo [serve-video-rtsp] ERROR: port %PORT% is already in use - use -p, or "serve-video-rtsp.cmd --stop" if that server is ours
exit /b 1

:stop
set "STOPPED="
call :kill_pidfile "%FF_PIDFILE%" ffmpeg
call :kill_pidfile "%MTX_PIDFILE%" mediamtx
if defined STOPPED goto :stopped_some
echo [serve-video-rtsp] not running
exit /b 0

:stopped_some
echo [serve-video-rtsp] stopped
exit /b 0

:usage
type "%TOOL%internal\usage.md"
exit /b 0

:usage_bad
type "%TOOL%internal\usage.md"
pause
exit /b 2

rem ---------------------------------------------------------------- helpers

:cleanup
call :kill_pidfile "%FF_PIDFILE%" ffmpeg
call :kill_pidfile "%MTX_PIDFILE%" mediamtx
exit /b 0

:pidfile_running
rem %~1 = pid file, %~2 = process name without .exe; errorlevel 0 when alive
set "PF_PID="
if not exist "%~1" exit /b 1
set /p PF_PID=<"%~1"
if not defined PF_PID exit /b 1
set "CHK_PID=%PF_PID%"
call :is_running "%~2"
exit /b %ERRORLEVEL%

:kill_pidfile
rem %~1 = pid file, %~2 = process name without .exe
set "KF_PID="
if not exist "%~1" exit /b 0
set /p KF_PID=<"%~1"
del "%~1" 2>nul
if not defined KF_PID exit /b 0
set "CHK_PID=%KF_PID%"
call :is_running "%~2"
if errorlevel 1 exit /b 0
set "KILL_PID=%KF_PID%"
powershell -NoProfile -Command "Stop-Process -Id ([int]$env:KILL_PID) -Force -ErrorAction SilentlyContinue"
set "STOPPED=1"
echo [serve-video-rtsp] stopped %~2 (pid %KF_PID%)
exit /b 0

:is_running
rem %~1 = process name without .exe; uses CHK_PID; errorlevel 0 when alive
set "CHK_PROC=%~1"
if not defined CHK_PID exit /b 1
if not defined CHK_PROC exit /b 1
powershell -NoProfile -Command "$p=Get-Process -Id $env:CHK_PID -ErrorAction SilentlyContinue; if($p -and $p.ProcessName -eq $env:CHK_PROC){ exit 0 } else { exit 1 }"
exit /b %ERRORLEVEL%

:wait_for_port
netstat -ano -p tcp | findstr "LISTENING" | findstr /C:":%PORT%" >nul
if not errorlevel 1 exit /b 0
set "CHK_PID=%MTX_PID%"
call :is_running mediamtx
if errorlevel 1 exit /b 1
set /a WAITED=%WAITED%+1
if %WAITED% GEQ 30 exit /b 1
ping -n 2 127.0.0.1 >nul
goto :wait_for_port

:ffmpeg_alive
set "CHK_PID=%FF_PID%"
call :is_running ffmpeg
exit /b %ERRORLEVEL%

:start_ffmpeg
rem %~1 = codec arguments
set "FF_EXE=%FFMPEG%"
set "VID_FILE=%FILE%"
set "RTSP_URL=rtsp://127.0.0.1:%PORT%/%NAME%"
set "FF_ARGS=%~1"
set "FF_OUT=%RUN%\ffmpeg.out"
set "FF_ERR=%RUN%\ffmpeg.log"
set "FF_PID="
for /f "usebackq delims=" %%P in (`powershell -NoProfile -ExecutionPolicy Bypass -File "%START%" -Kind ff 2^>nul`) do set "FF_PID=%%P"
if not defined FF_PID exit /b 0
> "%FF_PIDFILE%" echo(%FF_PID%
exit /b 0
