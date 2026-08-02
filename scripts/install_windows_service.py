import os
import sys
import subprocess

TASK_NAME = "SmartAttendanceLocalServer"
PROJECT_DIR = r"D:\smart"
VBS_PATH = os.path.join(PROJECT_DIR, "scripts", "start_server_background.vbs")

def install_task():
    print(f"Creating Windows Task Scheduler auto-start task: '{TASK_NAME}'...")
    
    # Command to create task in schtasks running on system startup
    cmd = [
        "schtasks", "/create", "/tn", TASK_NAME,
        "/tr", f'wscript.exe "{VBS_PATH}"',
        "/sc", "ONSTART",
        "/ru", "SYSTEM",
        "/f"
    ]
    
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"Successfully created background task '{TASK_NAME}'.")
        else:
            # Fallback to ONLOGON user schedule if SYSTEM registration requires admin privileges
            fallback_cmd = [
                "schtasks", "/create", "/tn", TASK_NAME,
                "/tr", f'wscript.exe "{VBS_PATH}"',
                "/sc", "ONLOGON",
                "/f"
            ]
            res_fb = subprocess.run(fallback_cmd, capture_output=True, text=True)
            if res_fb.returncode == 0:
                print(f"Successfully created background logon task '{TASK_NAME}'.")
            else:
                print(f"Notice: schtasks creation output: {res_fb.stderr or res.stderr}")
    except Exception as e:
        print(f"Error installing task: {e}")

def uninstall_task():
    print(f"Removing Windows Task Scheduler task '{TASK_NAME}'...")
    cmd = ["schtasks", "/delete", "/tn", TASK_NAME, "/f"]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            print(f"Successfully removed task '{TASK_NAME}'.")
        else:
            print(f"Notice: {res.stderr}")
    except Exception as e:
        print(f"Error removing task: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--uninstall":
        uninstall_task()
    else:
        install_task()
