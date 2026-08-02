@echo off
echo =========================================================================
echo  Installing AI Smart Attendance Production Local Server Windows Auto-Start
echo =========================================================================
cd /d "D:\smart"
python scripts\install_windows_service.py
echo.
echo Installation complete! Server will start automatically on Windows boot.
pause
