import os
import sys
import time

# ── Path Setup ────────────────────────────────────────────────────────────────
_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
for _p in [
    _BACKEND_DIR,
    os.path.join(_BACKEND_DIR, 'config'),
    os.path.join(_BACKEND_DIR, 'database'),
    os.path.join(_BACKEND_DIR, 'services'),
    os.path.join(_BACKEND_DIR, 'utils'),
    os.path.join(_BACKEND_DIR, 'ai', 'recognition'),
    os.path.join(_BACKEND_DIR, 'ai', 'training'),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)
# ──────────────────────────────────────────────────────────────────────────────

import database
import config
import backup_manager
from logger import server_logger
from app import app
from recognize import face_engine

def main():
    print("==================================================================")
    print("  AI Smart Attendance System - Production Local AI Server")
    print(f"  Permanent PC Data Root: {config.DATA_DIR}")
    print("  WSGI Server: Waitress")
    print("  Listening on: http://0.0.0.0:5000 (Accessible across College LAN)")
    print("==================================================================")

    # 1. Initialize SQLite Database & WAL Mode
    try:
        database.init_db()
        server_logger.info("SQLite Database initialized with WAL mode enabled.")
    except Exception as e:
        server_logger.error(f"Error initializing SQLite Database: {e}")

    # 2. Start Automated Nightly Backup Scheduler (1:00 AM)
    try:
        backup_manager.start_nightly_backup_scheduler()
        server_logger.info("Automated 1:00 AM Nightly Backup Scheduler initialized.")
    except Exception as e:
        server_logger.error(f"Error starting backup scheduler: {e}")

    # 3. Pre-warm AI Engine Models into RAM
    try:
        loaded = (face_engine.yunet is not None or face_engine.sface is not None)
        server_logger.info(f"AI Recognition Engine pre-warmed into RAM. Models loaded: {loaded}")
    except Exception as e:
        server_logger.error(f"Error pre-warming AI Engine: {e}")

    # 4. Launch Waitress WSGI Server
    try:
        from waitress import serve
        host = '0.0.0.0'
        port = int(os.environ.get('PORT', 5000))
        threads = int(os.environ.get('WAITRESS_THREADS', 16))
        
        server_logger.info(f"Starting Waitress production WSGI server on {host}:{port} ({threads} threads)...")
        serve(app, host=host, port=port, threads=threads)
    except Exception as e:
        server_logger.error(f"Fatal error running Waitress server: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
