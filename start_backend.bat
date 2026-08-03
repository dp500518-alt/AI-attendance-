@echo off
title AI Smart Attendance - 24/7 AI Backend Server
echo ============================================================
echo   Starting AI Smart Attendance 24/7 AI Backend REST Server...
echo   REST API: http://localhost:5001/
echo ============================================================
cd /d "%~dp0"
python ai_server.py
pause
