"""
Vercel serverless entry-point for AI Smart Attendance System.
Exposes the Flask app as the WSGI handler for @vercel/python.
"""
import os
import sys
import traceback

os.environ['VERCEL'] = '1'
os.environ.setdefault('DATA_DIR', '/tmp/smart_attendance_data')
os.environ.setdefault('FLASK_ENV', 'production')
os.environ.setdefault('FLASK_DEBUG', '0')

_ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

for _p in [
    _ROOT_DIR,
    os.path.join(_ROOT_DIR, 'config'),
    os.path.join(_ROOT_DIR, 'database'),
    os.path.join(_ROOT_DIR, 'services'),
    os.path.join(_ROOT_DIR, 'utils'),
    os.path.join(_ROOT_DIR, 'ai', 'recognition'),
    os.path.join(_ROOT_DIR, 'ai', 'training'),
]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

try:
    from app import app
except Exception as _boot_err:
    from flask import Flask as _Flask, jsonify as _jsonify
    _err_text = traceback.format_exc()
    print("=== Vercel Boot Error ===")
    print(_err_text)

    app = _Flask(__name__)

    @app.route('/', defaults={'path': ''})
    @app.route('/<path:path>')
    def _boot_error_handler(path):
        return _jsonify({
            'error': 'Server boot failed',
            'detail': str(_boot_err),
            'traceback': _err_text[-2000:]
        }), 500
