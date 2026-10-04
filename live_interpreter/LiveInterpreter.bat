@echo off
setlocal
cd /d "%~dp0"

set "PYTHONW=%~dp0.venv\Scripts\pythonw.exe"
set "PYTHON=%~dp0.venv\Scripts\python.exe"

if exist "%PYTHONW%" (
    start "LiveInterpreter" "%PYTHONW%" -m live_interpreter
    exit /b 0
)

if exist "%PYTHON%" (
    "%PYTHON%" -m live_interpreter
    exit /b %ERRORLEVEL%
)

echo.
echo LiveInterpreter is not installed yet.
echo Run setup.ps1 first:
echo   powershell -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
echo.
pause
exit /b 1
