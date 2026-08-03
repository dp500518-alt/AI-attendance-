@echo off
title Smart Attendance 24/7 Local AI Server
echo ============================================================
echo   Smart Attendance 24/7 Local AI Server Daemon
echo   Permanent Storage Root: D:\SmartAttendanceServer\
echo   REST API: http://localhost:5001/
echo ============================================================

cd /d "%~dp0.."

:SERVER_LOOP
echo [%DATE% %TIME%] Starting AI Server process on port 5001...
python ai_server.py
echo [%DATE% %TIME%] WARNING: AI Server process stopped or crashed! Auto-restarting in 3 seconds...
timeout /t 3 /nobreak >nul
goto SERVER_LOOP
