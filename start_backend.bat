@echo off
title AI Smart Attendance - Flask Backend Server
echo ============================================================
echo   Starting AI Smart Attendance Flask Backend Server...
echo   Server URL: http://localhost:5000/
echo ============================================================
cd /d "%~dp0backend"
python app.py
pause
