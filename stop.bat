@echo off
title AI Math Assistant - Stop
cd /d "%~dp0"

echo ============================================
echo   AI Math Assistant - Stop
echo ============================================
echo.

REM Kill process on port 8000 (backend)
echo [1/2] Stopping backend on port 8000 ...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":8000 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
    echo       Stopped PID %%p
)

REM Kill process on port 5173 (frontend)
echo [2/2] Stopping frontend on port 5173 ...
for /f "tokens=5" %%p in ('netstat -ano 2^>nul ^| findstr ":5173 " ^| findstr "LISTENING"') do (
    taskkill /PID %%p /F >nul 2>&1
    echo       Stopped PID %%p
)

echo.
echo ============================================
echo   All services stopped
echo ============================================
pause
