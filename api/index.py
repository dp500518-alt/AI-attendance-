"""
Vercel serverless entry-point for AI Smart Attendance System.
Safely loads the Flask app from backend/app.py and exposes it as the WSGI handler.

Vercel environment constraints handled here:
  - Read-only filesystem (only /tmp is writable)
  - No GPU / OpenCV camera / hardware access
  - 250 MB package size limit (ultralytics/insightface excluded)
  - 10 s default / 60 s max function timeout
  - All errors caught so Vercel returns 500 JSON, not blank crash page
"""
import os
import sys
import traceback

# ── 1. Tell all backend modules to use /tmp for writable storage ────────────
os.environ.setdefault('DATA_DIR', '/tmp/smart_attendance_data')
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('FLASK_DEBUG', '0')

# ── 2. Build sys.path so flat `import config` etc. all resolve ──────────────
_ROOT_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND_DIR = os.path.join(_ROOT_DIR, 'backend')

for _p in [
    _ROOT_DIR,
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

# ── 3. Load Flask app, capturing any import-time crash as a fallback app ────
try:
    import importlib.util as _ilu

    _spec = _ilu.spec_from_file_location('app', os.path.join(_BACKEND_DIR, 'app.py'))
    _mod  = _ilu.module_from_spec(_spec)
    sys.modules['app'] = _mod
    _spec.loader.exec_module(_mod)

    # Vercel WSGI handler — must be named `app`
    app = _mod.app

except Exception as _boot_err:
    # ── Fallback: if app.py crashes on import, return a readable error ──────
    from flask import Flask as _Flask, jsonify as _jsonify
    import traceback as _tb

    _err_text = _tb.format_exc()
    print("=== Vercel boot error ===")
    print(_err_text)

    app = _Flask(__name__)

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def _boot_error_handler(path):
        return _jsonify({
            'error': 'Server boot failed',
            'detail': str(_boot_err),
            'traceback': _err_text[-2000:]   # last 2000 chars to stay under response limit
        }), 500
