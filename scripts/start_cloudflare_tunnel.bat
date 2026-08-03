@echo off
title Cloudflare Tunnel - Smart Attendance System
echo ============================================================
echo Starting Cloudflare Tunnel for Smart Attendance System...
echo Local Address : http://localhost:5000
echo ============================================================

"C:\Program Files (x86)\cloudflared\cloudflared.exe" tunnel run --token eyJhIjoiNGQyYjExZWI3MDkwYmI1NGM4MDkyYzEwN2U1MGRkNmQiLCJ0IjoiMGRhMTExMjYtNmJhYy00MzJlLTllNmItZjcwMGQ0ODAyMWY1IiwicyI6IllXRTRNbUprTWpZdE5HSXdZaTAwT1dRNUxUbGhaVGd0WVRJMVlqZzFNVGRtTkRKbSJ9

pause
