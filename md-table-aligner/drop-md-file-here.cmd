@echo off
setlocal

set "SCRIPT=%~dp0internal\fmt_md_tables.py"

if "%~1"=="" goto :usage

:loop
if "%~1"=="" goto :done

echo.
echo Source: %~f1
python "%SCRIPT%" "%~f1"
if errorlevel 1 (
    echo FAILED: %~f1
    goto :failed
)
echo Done: %~f1

shift
goto :loop

:done
echo.
echo All files processed. The output was written next to each source file.
pause
exit /b 0

:failed
echo.
echo Processing failed.
pause
exit /b 1

:usage
type "%~dp0internal\usage.md"
pause
exit /b 2