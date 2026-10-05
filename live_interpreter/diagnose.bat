@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [LiveInterpreter] .venv not found.
    echo Run setup.ps1 first.
    pause
    exit /b 1
)

".venv\Scripts\python.exe" -m live_interpreter.diagnose
set "EXITCODE=%ERRORLEVEL%"

echo.
if not "%EXITCODE%"=="0" echo Diagnostics exited with code %EXITCODE%.
pause
exit /b %EXITCODE%
