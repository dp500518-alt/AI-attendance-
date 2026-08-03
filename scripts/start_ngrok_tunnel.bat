@echo off
title ngrok Tunnel - Smart Attendance System
echo ============================================================
echo Starting ngrok Tunnel for Smart Attendance System...
echo Domain        : https://divisive-ritalin-dragging.ngrok-free.dev
echo Target Local  : http://localhost:5000
echo ============================================================

"d:\smart\tools\ngrok.exe" http --url=divisive-ritalin-dragging.ngrok-free.dev 5000

pause
