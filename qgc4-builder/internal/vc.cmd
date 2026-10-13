@echo off

for /f "delims=" %%I in ('"%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath') do set "VS=%%I"

if not defined VS (
    echo Visual Studio C++ tools not found.
    exit /b 1
)

call "%VS%\VC\Auxiliary\Build\vcvars64.bat"
