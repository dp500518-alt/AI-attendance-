@echo off
title AI Smart Attendance - Flask REST API Backend
echo ============================================================
echo   Starting AI Smart Attendance Flask REST API Backend...
echo   REST API: http://localhost:5000/
echo ============================================================
cd /d "%~dp0backend"
python app.py
pause
