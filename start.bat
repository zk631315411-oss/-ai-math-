@echo off
title AI Math Assistant
cd /d "%~dp0"

echo ============================================
echo   AI Math Assistant - Start
echo ============================================
echo.

set "VPYTHON=%~dp0venv\Scripts\python.exe"
set "LOGDIR=%~dp0logs"

if not exist "%VPYTHON%" (
    echo [ERROR] Project Python not found: %VPYTHON%
    echo Run: py -3.11 -m venv venv
    exit /b 1
)

if not exist "%LOGDIR%" mkdir "%LOGDIR%"

REM Kill stale processes on our ports
echo [0] Cleaning up old processes ...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
)

echo [1/2] Starting backend on port 8000 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath '%VPYTHON%' -ArgumentList '-m','uvicorn','app.main:app','--host','0.0.0.0','--port','8000' -WorkingDirectory '%~dp0' -WindowStyle Hidden -RedirectStandardOutput '%LOGDIR%\backend.stdout.log' -RedirectStandardError '%LOGDIR%\backend.stderr.log' -PassThru; Set-Content -LiteralPath '%LOGDIR%\backend.pid' -Value $p.Id"
if errorlevel 1 exit /b 1

echo [2/2] Starting frontend on port 5173 ...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$p = Start-Process -FilePath 'npm.cmd' -ArgumentList 'run','dev' -WorkingDirectory '%~dp0frontend' -WindowStyle Hidden -RedirectStandardOutput '%LOGDIR%\frontend.stdout.log' -RedirectStandardError '%LOGDIR%\frontend.stderr.log' -PassThru; Set-Content -LiteralPath '%LOGDIR%\frontend.pid' -Value $p.Id"
if errorlevel 1 exit /b 1

echo.
echo   Backend : http://localhost:8000
echo   Frontend: http://localhost:5173
echo   Docs   : http://localhost:8000/docs
echo.
echo   Wait ~5 seconds for services to start...
ping -n 6 127.0.0.1 >nul

if /i not "%~1"=="--no-browser" (
    start http://localhost:5173
    pause
)
