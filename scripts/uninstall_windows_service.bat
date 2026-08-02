@echo off
echo =========================================================================
echo  Uninstalling AI Smart Attendance Production Local Server Windows Auto-Start
echo =========================================================================
cd /d "D:\smart"
python scripts\install_windows_service.py --uninstall
echo.
pause
