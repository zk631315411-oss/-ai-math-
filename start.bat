@echo off
title AI Math Assistant
cd /d "%~dp0"

echo ============================================
echo   AI Math Assistant - Start
echo ============================================
echo.

set "VPYTHON=python"

REM Kill stale processes on our ports
echo [0] Cleaning up old processes ...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
)
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
)

echo [1/2] Starting backend on port 8000 ...
start "AI-Backend" /min "%VPYTHON%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000

echo [2/2] Starting frontend on port 5173 ...
cd /d "%~dp0frontend"
start "AI-Frontend" /min cmd /c "npm run dev"
cd /d "%~dp0"

echo.
echo   Backend : http://localhost:8000
echo   Frontend: http://localhost:5173
echo   Docs   : http://localhost:8000/docs
echo.
echo   Wait ~5 seconds for services to start...
ping -n 6 127.0.0.1 >nul

start http://localhost:5173
pause
