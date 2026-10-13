@echo off
setlocal

set "QGC_ROOT=%~1"
set "CONFIG=%~2"

if not defined QGC_ROOT (
    echo Usage: %~nx0 ^<QGC_ROOT^> [debug^|release] [qmake_args...]
    exit /b 1
)

for %%I in ("%QGC_ROOT%") do set "QGC_ROOT=%%~fI"

if not defined CONFIG set "CONFIG=debug"

if /i not "%CONFIG%"=="debug" if /i not "%CONFIG%"=="release" (
    echo Usage: %~nx0 ^<QGC_ROOT^> [debug^|release] [qmake_args...]
    exit /b 1
)

set "QMAKE_CONFIG=CONFIG+=%CONFIG% CONFIG+=qml_%CONFIG%"
set "QMAKE_ARGS=%~3 %~4 %~5 %~6 %~7 %~8 %~9"

call "%~dp0..\..\init-qt-env\init-qt-env.bat" || exit /b 1
call "%~dp0vc.cmd" || exit /b 1

set "CONFIG_CAP=Debug"
if /i "%CONFIG%"=="release" set "CONFIG_CAP=Release"
set "BUILD_DIR=%QGC_ROOT%\build\Desktop_Qt_5_15_2_MSVC2019_64bit-%CONFIG_CAP%"

if not exist "%BUILD_DIR%" mkdir "%BUILD_DIR%"
cd /d "%BUILD_DIR%" || exit /b 1

echo [Build] QGC    : %QGC_ROOT%
echo [Build] Config : %CONFIG%
echo [Build] Qt     : %QT_ROOT%

echo "%QMAKE%" "%QGC_ROOT%\qgroundcontrol.pro" -spec win32-msvc %QMAKE_CONFIG% %QMAKE_ARGS%
"%QMAKE%" "%QGC_ROOT%\qgroundcontrol.pro" -spec win32-msvc %QMAKE_CONFIG% %QMAKE_ARGS% || exit /b 1

nmake /NOLOGO || exit /b 1

echo [Deploy] Running windeployqt...
set "TARGET_EXE=QGroundControl.exe"

"%QT_ROOT%\bin\windeployqt.exe" --qmldir "%QGC_ROOT%\src" --no-translations --no-system-d3d-compiler --no-angle "%BUILD_DIR%\staging\%TARGET_EXE%" || exit /b 1

echo [Deploy] Copying geoservices plugins...
xcopy /y /i "%QT_ROOT%\plugins\geoservices\*" "%BUILD_DIR%\staging\geoservices\" >nul

echo [Deploy] Copying runtime dependencies...
if exist "%QGC_ROOT%\libs\sdl2\msvc\lib\x64\SDL2.dll" copy /y "%QGC_ROOT%\libs\sdl2\msvc\lib\x64\SDL2.dll" "%BUILD_DIR%\staging\" >nul
if exist "%QGC_ROOT%\libs\OpenSSL\windows\libcrypto-1_1-x64.dll" copy /y "%QGC_ROOT%\libs\OpenSSL\windows\libcrypto-1_1-x64.dll" "%BUILD_DIR%\staging\" >nul
if exist "%QGC_ROOT%\libs\OpenSSL\windows\libssl-1_1-x64.dll" copy /y "%QGC_ROOT%\libs\OpenSSL\windows\libssl-1_1-x64.dll" "%BUILD_DIR%\staging\" >nul

if /i "%CONFIG%"=="release" (
    if exist "%QGC_ROOT%\libs\Microsoft\windows\msvcp140.dll" copy /y "%QGC_ROOT%\libs\Microsoft\windows\msvcp140.dll" "%BUILD_DIR%\staging\" >nul
    if exist "%QGC_ROOT%\libs\Microsoft\windows\vcruntime140.dll" copy /y "%QGC_ROOT%\libs\Microsoft\windows\vcruntime140.dll" "%BUILD_DIR%\staging\" >nul
)

echo [OK] Build completed: %BUILD_DIR%

endlocal
