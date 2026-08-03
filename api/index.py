"""
Vercel serverless entry-point for AI Smart Attendance System.
Loads the Flask app from backend/app.py and exposes it as the WSGI handler.
"""
import os
import sys

# Add project directories to sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(ROOT_DIR, 'backend')

for path in [ROOT_DIR, BACKEND_DIR,
             os.path.join(BACKEND_DIR, 'config'),
             os.path.join(BACKEND_DIR, 'database'),
             os.path.join(BACKEND_DIR, 'services'),
             os.path.join(BACKEND_DIR, 'utils'),
             os.path.join(BACKEND_DIR, 'ai', 'recognition'),
             os.path.join(BACKEND_DIR, 'ai', 'training')]:
    if path not in sys.path:
        sys.path.insert(0, path)

# Load app.py as a module from the filesystem path
import importlib.util

spec = importlib.util.spec_from_file_location(
    "app",
    os.path.join(BACKEND_DIR, "app.py")
)
mod = importlib.util.module_from_spec(spec)
sys.modules['app'] = mod
spec.loader.exec_module(mod)

# Vercel looks for a variable named `app` (WSGI callable) in this file
app = mod.app
