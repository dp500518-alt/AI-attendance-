import os
import sys
import subprocess

def install_windows_startup():
    """
    Registers start_ai_server.bat in Windows Startup folder (shell:startup)
    so the 24/7 Local AI Server starts automatically when Windows boots.
    """
    appdata = os.environ.get('APPDATA')
    if not appdata:
        print("Error: Could not determine APPDATA folder.")
        return False

    startup_folder = os.path.join(appdata, r'Microsoft\Windows\Start Menu\Programs\Startup')
    os.makedirs(startup_folder, exist_ok=True)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    bat_source = os.path.join(script_dir, 'start_ai_server.bat')
    target_bat = os.path.join(startup_folder, 'smart_attendance_ai_server.bat')

    if not os.path.exists(bat_source):
        print(f"Error: {bat_source} does not exist.")
        return False

    try:
        # Create a launcher batch file in Startup folder
        with open(target_bat, 'w') as f:
            f.write(f'@echo off\n')
            f.write(f'call "{bat_source}"\n')

        print(f"Successfully registered 24/7 Local AI Server in Windows Startup folder:")
        print(f" -> {target_bat}")
        print("The AI Server will now automatically start on Windows boot!")
        return True

    except Exception as e:
        print(f"Error creating Windows Startup entry: {e}")
        return False


if __name__ == '__main__':
    install_windows_startup()
