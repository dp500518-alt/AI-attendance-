import os
import sys
import time
import json
import logging
import datetime
from flask import Flask, request, jsonify, send_file
import config
import database
import register
import recognize
import model_trainer
import backup_manager
from camera import decode_base64_image

# Configure 24/7 Server File Logger in D:\SmartAttendanceServer\logs\ai_server.log
LOG_FILE = os.path.join(config.LOGS_DIR, 'ai_server.log')
os.makedirs(config.LOGS_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)

from storage_manager import storage_manager

try:
    storage_manager.reconnect_and_sync()
except Exception as e:
    logging.error(f"Persistent storage reconnect error on AI server startup: {e}")

SERVER_START_TIME = time.time()


@app.route('/')
@app.route('/health', methods=['GET'])
def health():
    """24/7 Health Check Endpoint."""
    uptime = round(time.time() - SERVER_START_TIME, 2)
    return jsonify({
        'status': 'ok',
        'service': 'Smart Attendance 24/7 Local AI Server',
        'port': 5001,
        'uptime_seconds': uptime,
        'permanent_storage': config.DATA_DIR,
        'is_container_env': config.IS_CONTAINER_ENV,
        'object_storage_connected': storage_manager.is_object_storage_connected(),
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route('/status', methods=['GET'])
def status():
    """Detailed Engine & Training Status Endpoint."""
    database.init_db()
    students = database.get_all_students()
    all_embs = database.get_all_embeddings()
    meta = model_trainer.load_training_metadata()
    trainer_status = model_trainer.trainer.get_status()

    return jsonify({
        'status': 'running',
        'total_registered_students': len(students),
        'total_embeddings_in_db': len(all_embs),
        'permanent_data_dir': config.DATA_DIR,
        'is_container_env': config.IS_CONTAINER_ENV,
        'object_storage_connected': storage_manager.is_object_storage_connected(),
        'training': trainer_status,
        'model_metadata': meta,
        'uptime_seconds': round(time.time() - SERVER_START_TIME, 2)
    })


@app.route('/register', methods=['POST'])
def register_student_api():
    """
    Registers student in permanent D:\SmartAttendanceServer dataset and triggers background model training.
    """
    data = request.get_json(force=True, silent=True) or request.form
    student_id = data.get('student_id', '').strip()
    roll_number = data.get('roll_number', '').strip()
    name = data.get('name', '').strip()
    department = data.get('department', 'Computer Science').strip()
    semester = data.get('semester', 'Semester 1').strip()
    division = data.get('division', 'Division A').strip()
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    sample_images_b64 = data.get('sample_images_b64', [])

    if isinstance(sample_images_b64, str):
        try:
            sample_images_b64 = json.loads(sample_images_b64)
        except Exception:
            sample_images_b64 = [sample_images_b64]

    logging.info(f"API Register Request received for student: {student_id} ({name})")
    success, msg = register.register_new_student(
        student_id, roll_number, name, department, semester, sample_images_b64, division, email, phone
    )

    return jsonify({'success': success, 'message': msg})


@app.route('/recognize', methods=['POST'])
def recognize_api():
    """
    Real-Time Face Recognition Endpoint.
    Receives base64 image or file upload and returns Student ID predictions with confidence score %.
    """
    t_start = time.time()
    img_bgr = None

    if request.is_json or request.form:
        data = request.get_json(force=True, silent=True) or request.form
        b64_str = data.get('image_b64', '')
        if b64_str:
            img_bgr = decode_base64_image(b64_str)

    if img_bgr is None and 'photo' in request.files:
        file = request.files['photo']
        import numpy as np
        import cv2
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img_bgr is None or img_bgr.size == 0:
        return jsonify({'success': False, 'message': 'Invalid image data received.', 'faces': []}), 400

    database.init_db()
    known_embeddings = database.get_all_embeddings()
    results = recognize.face_engine.recognize_faces(img_bgr, known_embeddings)

    total_time_ms = round((time.time() - t_start) * 1000, 2)
    logging.info(f"API Recognize processed {len(results)} face(s) in {total_time_ms}ms.")

    return jsonify({
        'success': True,
        'detected_faces_count': len(results),
        'processing_time_ms': total_time_ms,
        'faces': results
    })


@app.route('/train', methods=['POST'])
def train_api():
    """Triggers background AI Classifier Model Training Queue."""
    logging.info("API Train trigger requested.")
    started, msg = model_trainer.trainer.start_training_async()
    return jsonify({'success': started, 'message': msg})


@app.route('/backup', methods=['POST'])
def backup_api():
    """Triggers immediate manual backup."""
    notes = request.json.get('notes', 'Manual API Backup') if request.is_json else 'Manual API Backup'
    result = backup_manager.create_backup(notes=notes)
    logging.info(f"API Backup created: {result.get('filename')}")
    return jsonify(result)


@app.route('/backups', methods=['GET'])
def list_backups_api():
    """Lists available system backups."""
    backups = backup_manager.get_backup_list()
    return jsonify({'backups': backups, 'count': len(backups)})


@app.route('/restore', methods=['POST'])
def restore_api():
    """Restores selected backup file."""
    data = request.get_json(force=True, silent=True) or request.form
    backup_filename = data.get('backup_filename', '').strip()
    if not backup_filename:
        return jsonify({'success': False, 'message': 'backup_filename is required.'}), 400

    result = backup_manager.restore_backup(backup_filename)
    logging.info(f"API Restore result for {backup_filename}: {result['success']}")
    return jsonify(result)


@app.route('/logs', methods=['GET'])
def logs_api():
    """Returns recent server logs."""
    logs = []
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, 'r', encoding='utf-8', errors='ignore') as f:
                logs = [line.strip() for line in f.readlines()[-200:]]
        except Exception as e:
            logs = [f"Error reading log file: {e}"]
    return jsonify({'logs': logs})


if __name__ == '__main__':
    port = int(os.environ.get('AI_SERVER_PORT', 5001))
    print(f"============================================================")
    print(f"  Starting Smart Attendance 24/7 Local AI Server")
    print(f"  Permanent Storage: {config.DATA_DIR}")
    print(f"  REST API Endpoint: http://localhost:{port}/")
    print(f"============================================================")
    logging.info(f"24/7 AI Server starting on http://localhost:{port}/ with permanent storage at {config.DATA_DIR}")
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)
