import os
import sys
import json
import io
import time
import datetime
from functools import wraps

# Ensure backend root and subpackages are in sys.path
BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

dirs_to_add = ['config', 'database', 'services', 'utils', os.path.join('ai', 'recognition'), os.path.join('ai', 'training')]
for d in dirs_to_add:
    p = os.path.join(BACKEND_DIR, d)
    if p not in sys.path:
        sys.path.insert(0, p)

from flask import Flask, request, redirect, url_for, flash, session, Response, send_file, jsonify
from flask_cors import CORS

import config
import database
import register
import recognize
import attendance
import utils
import ocr_timetable
import login_security
import analytics_reports
import notifications
import model_trainer
import backup_manager
from camera import camera_instance, decode_base64_image
from train import train_all_students

app = Flask(__name__)
app.secret_key = getattr(config, 'SECRET_KEY', 'smart_attendance_secret_key_2026')
CORS(app, supports_credentials=True, origins='*')

app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Requested-With'
    return response

database.init_db()

# Helper authentication check
def get_current_user():
    if 'user' in session:
        return {
            'username': session.get('user'),
            'role': session.get('user_role', 'teacher'),
            'full_name': session.get('user_fullname', session.get('user')),
            'department': session.get('user_dept', '')
        }
    return None

# --- AUTH REST APIS ---
@app.route('/api/auth/login', methods=['POST'])
@app.route('/login', methods=['POST'])
def api_login():
    data = request.get_json(force=True, silent=True) or request.form
    username = data.get('username', '').strip()
    password = data.get('password', '').strip()

    user = database.verify_user(username, password)
    if user:
        session['user'] = user['username']
        session['user_role'] = user.get('role', 'teacher')
        session['user_fullname'] = user.get('full_name') or user['username']
        session['user_dept'] = user.get('department') or ''

        try:
            sec_result = login_security.process_login_security(
                username=user['username'],
                role=user.get('role', 'teacher'),
                full_name=session['user_fullname'],
                request_obj=request,
                session_id=session.get('_id', ''),
                status='Success'
            )
        except Exception:
            pass

        return jsonify({
            'success': True,
            'user': {
                'username': user['username'],
                'role': user.get('role', 'teacher'),
                'full_name': session['user_fullname'],
                'department': session['user_dept']
            },
            'redirect': '/student/dashboard' if user.get('role') == 'student' else ('/teacher/dashboard' if user.get('role') == 'teacher' else '/dashboard')
        })

    return jsonify({'success': False, 'message': 'Invalid username or password.'}), 401


@app.route('/api/auth/logout', methods=['POST', 'GET'])
@app.route('/logout', methods=['POST', 'GET'])
def api_logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully.'})


@app.route('/api/auth/me', methods=['GET'])
def api_auth_me():
    curr = get_current_user()
    if curr:
        return jsonify({'authenticated': True, 'user': curr})
    return jsonify({'authenticated': False, 'user': None})


# --- DASHBOARD & STATS APIS ---
@app.route('/api/dashboard/stats', methods=['GET'])
@app.route('/', methods=['GET'])
def api_dashboard_stats():
    stats = database.get_dashboard_stats()
    today_attendance = database.get_attendance_today()
    all_embeddings = database.get_all_embeddings()
    threshold = database.get_setting('recognition_threshold', getattr(config, 'RECOGNITION_THRESHOLD', 0.40))
    from hardware_manager import hardware_manager
    hw_status = hardware_manager.get_hardware_status()

    return jsonify({
        'stats': stats,
        'today_attendance': today_attendance,
        'embedded_count': len(all_embeddings),
        'threshold': threshold,
        'hardware': hw_status
    })


@app.route('/api/student/dashboard', methods=['GET'])
def api_student_dashboard():
    username = request.args.get('username') or session.get('user', '')
    student = database.get_student_by_username(username)
    if not student:
        students = database.get_all_students()
        student = students[0] if students else {'id': username or 'S101', 'name': 'Student', 'semester': 'Semester 1', 'division': 'Division A', 'department': 'Computer Science'}

    summary = database.get_student_attendance_summary(student['id'])
    timetable = database.get_timetable(semester=student.get('semester'), division=student.get('division'))
    notifications_list = database.get_notifications(target_user=username)

    return jsonify({
        'student': student,
        'summary': summary,
        'timetable': timetable,
        'notifications': notifications_list
    })


@app.route('/api/teacher/dashboard', methods=['GET'])
def api_teacher_dashboard():
    teacher_name = request.args.get('teacher') or session.get('user', 'teacher')
    t_stats = database.get_teacher_dashboard_stats(teacher_name)
    my_timetable = database.get_teacher_timetable(teacher_username=teacher_name)
    active_slot = database.get_active_lecture_for_teacher(teacher_name)
    low_attendance_students = database.get_short_attendance_students(threshold=50.0)

    return jsonify({
        't_stats': t_stats,
        'my_timetable': my_timetable,
        'active_slot': active_slot,
        'low_attendance_students': low_attendance_students
    })


# --- STUDENTS DIRECTORY APIS ---
@app.route('/api/students', methods=['GET'])
@app.route('/students', methods=['GET'])
def api_get_students():
    dept = request.args.get('dept', '')
    sem = request.args.get('sem', '')
    query = request.args.get('q', '')

    students = database.get_all_students()
    all_embeddings = database.get_all_embeddings()

    if dept:
        students = [s for s in students if s.get('department') == dept]
    if sem:
        students = [s for s in students if s.get('semester') == sem]
    if query:
        q = query.lower()
        students = [s for s in students if q in str(s.get('id')).lower() or q in s.get('name', '').lower() or q in s.get('roll_number', '').lower()]

    for s in students:
        sid = str(s['id'])
        s['has_embedding'] = sid in all_embeddings

    return jsonify({
        'students': students,
        'total': len(students),
        'embedded_count': len(all_embeddings)
    })


@app.route('/api/students/photo/<student_id>', methods=['GET'])
@app.route('/students/photo/<student_id>', methods=['GET'])
def api_get_student_photo(student_id):
    student_dir = os.path.join(config.DATASET_DIR, str(student_id))
    if os.path.exists(student_dir):
        imgs = [f for f in os.listdir(student_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if imgs:
            return send_file(os.path.join(student_dir, imgs[0]), mimetype='image/jpeg')
    return send_file(os.path.join(config.BASE_DIR, 'static', 'images', 'default_avatar.png'), mimetype='image/png') if os.path.exists(os.path.join(config.BASE_DIR, 'static', 'images', 'default_avatar.png')) else ('No image', 404)


@app.route('/api/students/delete/<student_id>', methods=['POST', 'DELETE'])
@app.route('/students/delete/<student_id>', methods=['POST', 'DELETE'])
def api_delete_student(student_id):
    database.delete_student(student_id)
    s_dir = os.path.join(config.DATASET_DIR, str(student_id))
    if os.path.exists(s_dir):
        import shutil
        shutil.rmtree(s_dir, ignore_errors=True)
    return jsonify({'success': True, 'message': f'Student {student_id} deleted successfully.'})


# --- TEACHERS DIRECTORY APIS ---
@app.route('/api/teachers', methods=['GET', 'POST'])
@app.route('/teachers', methods=['GET', 'POST'])
def api_teachers():
    if request.method == 'POST':
        data = request.get_json(force=True, silent=True) or request.form
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        full_name = data.get('full_name', '').strip()
        department = data.get('department', '').strip()
        email = data.get('email', '').strip()

        if not username or not password:
            return jsonify({'success': False, 'message': 'Username and password are required.'}), 400

        res = database.create_teacher_user(username, password, full_name, department, email)
        return jsonify(res)

    teachers = database.get_all_teachers()
    return jsonify({'teachers': teachers, 'total': len(teachers)})


@app.route('/api/teachers/delete/<int:user_id>', methods=['POST', 'DELETE'])
@app.route('/teachers/delete/<int:user_id>', methods=['POST', 'DELETE'])
def api_delete_teacher(user_id):
    database.delete_teacher_user(user_id)
    return jsonify({'success': True, 'message': 'Teacher user deleted successfully.'})


# --- TIMETABLE & OCR APIS ---
@app.route('/api/timetable', methods=['GET', 'POST'])
@app.route('/timetable', methods=['GET', 'POST'])
def api_timetable():
    if request.method == 'POST':
        data = request.get_json(force=True, silent=True) or request.form
        day = data.get('day_of_week', '').strip()
        time_slot = data.get('time_slot', '').strip()
        subject_name = data.get('subject_name', '').strip()
        teacher_name = data.get('teacher_name', '').strip()
        classroom = data.get('classroom_room', '').strip()
        semester = data.get('semester', 'Semester 1').strip()
        division = data.get('division', 'Division A').strip()

        success = database.add_timetable_entry(day, time_slot, subject_name, teacher_name, classroom, semester, division)
        return jsonify({'success': success, 'message': 'Timetable entry added successfully.' if success else 'Failed to add entry.'})

    sem = request.args.get('semester', 'Semester 1')
    div = request.args.get('division', 'Division A')
    timetable = database.get_timetable(semester=sem, division=div)
    subjects = database.get_all_subjects()
    teachers = database.get_all_teachers()

    return jsonify({
        'timetable': timetable,
        'subjects': subjects,
        'teachers': teachers,
        'semester': sem,
        'division': div
    })


@app.route('/api/timetable/edit/<int:entry_id>', methods=['POST'])
def api_edit_timetable(entry_id):
    data = request.get_json(force=True, silent=True) or request.form
    day = data.get('day_of_week', '').strip()
    time_slot = data.get('time_slot', '').strip()
    subject_name = data.get('subject_name', '').strip()
    teacher_name = data.get('teacher_name', '').strip()
    classroom = data.get('classroom_room', '').strip()

    success = database.update_timetable_entry(entry_id, day, time_slot, subject_name, teacher_name, classroom)
    return jsonify({'success': success, 'message': 'Timetable entry updated successfully.'})


@app.route('/api/timetable/delete/<int:entry_id>', methods=['POST', 'DELETE'])
def api_delete_timetable(entry_id):
    database.delete_timetable_entry(entry_id)
    return jsonify({'success': True, 'message': 'Timetable entry deleted successfully.'})


@app.route('/api/timetable/ocr_upload', methods=['POST'])
def api_ocr_upload():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file uploaded.'}), 400

    file = request.files['file']
    filename = file.filename
    filepath = os.path.join(config.UPLOADS_DIR, filename)
    file.save(filepath)

    result = ocr_timetable.process_ocr_timetable(filepath)
    return jsonify({'success': True, 'ocr_result': result})


@app.route('/api/timetable/save_ocr', methods=['POST'])
def api_save_ocr():
    data = request.get_json(force=True, silent=True) or request.form
    entries = data.get('entries', [])
    if isinstance(entries, str):
        entries = json.loads(entries)

    count = database.save_ocr_timetable_entries(entries)
    return jsonify({'success': True, 'saved_count': count})


# --- CLASSROOM ATTENDANCE & RECOGNITION APIS ---
@app.route('/api/classroom/upload', methods=['POST'])
@app.route('/classroom/upload', methods=['POST'])
def api_classroom_upload():
    if 'classroom_photo' not in request.files:
        return jsonify({'success': False, 'message': 'No classroom image uploaded.'}), 400

    file = request.files['classroom_photo']
    import numpy as np
    import cv2
    file_bytes = np.frombuffer(file.read(), np.uint8)
    img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

    if img_bgr is None:
        return jsonify({'success': False, 'message': 'Invalid image format.'}), 400

    database.init_db()
    known_embs = database.get_all_embeddings()
    results = recognize.face_engine.recognize_faces(img_bgr, known_embs)

    subject_name = request.form.get('subject_name', 'General Lecture')
    teacher_name = request.form.get('teacher_name', session.get('user_fullname', 'Teacher'))

    marked_list = []
    for f in results:
        if f.get('student_id') and f.get('student_id') != 'Unknown':
            att = attendance.mark_attendance(
                student_id=f['student_id'],
                subject_name=subject_name,
                teacher_name=teacher_name,
                confidence=f.get('confidence', 0.0)
            )
            marked_list.append(att)

    return jsonify({
        'success': True,
        'faces_detected': len(results),
        'marked_attendance': marked_list,
        'faces': results
    })


@app.route('/api/classroom/snap', methods=['POST'])
def api_classroom_snap():
    data = request.get_json(force=True, silent=True) or request.form
    b64_str = data.get('image_b64', '')
    if not b64_str:
        return jsonify({'success': False, 'message': 'No base64 image data.'}), 400

    img_bgr = camera.decode_base64_image(b64_str)
    if img_bgr is None:
        return jsonify({'success': False, 'message': 'Invalid base64 image.'}), 400

    database.init_db()
    known_embs = database.get_all_embeddings()
    results = recognize.face_engine.recognize_faces(img_bgr, known_embs)

    subject_name = data.get('subject_name', 'Live Snap Lecture')
    teacher_name = data.get('teacher_name', session.get('user_fullname', 'Teacher'))

    marked = []
    for f in results:
        if f.get('student_id') and f.get('student_id') != 'Unknown':
            att = attendance.mark_attendance(
                student_id=f['student_id'],
                subject_name=subject_name,
                teacher_name=teacher_name,
                confidence=f.get('confidence', 0.0)
            )
            marked.append(att)

    return jsonify({
        'success': True,
        'detected_faces_count': len(results),
        'marked_attendance': marked,
        'faces': results
    })


# --- HISTORY & ANALYTICS APIS ---
@app.route('/api/history', methods=['GET'])
@app.route('/history', methods=['GET'])
def api_history():
    date_val = request.args.get('date', '').strip() or None
    dept_val = request.args.get('department', '').strip() or None
    subj_val = request.args.get('subject', '').strip() or None

    logs = database.get_attendance_history(date_filter=date_val, dept_filter=dept_val, subject_filter=subj_val)
    return jsonify({'logs': logs, 'total': len(logs)})


@app.route('/api/analytics', methods=['GET'])
@app.route('/analytics', methods=['GET'])
def api_analytics():
    data = analytics_reports.get_full_analytics_data()
    return jsonify(data)


# --- SUBJECTS APIS ---
@app.route('/api/subjects', methods=['GET', 'POST'])
@app.route('/subjects', methods=['GET', 'POST'])
def api_subjects():
    if request.method == 'POST':
        data = request.get_json(force=True, silent=True) or request.form
        code = data.get('code', '').strip()
        name = data.get('name', '').strip()
        dept = data.get('department', '').strip()

        success = database.add_subject(code, name, dept)
        return jsonify({'success': success, 'message': 'Subject added.' if success else 'Subject code already exists.'})

    subjects = database.get_all_subjects()
    return jsonify({'subjects': subjects, 'total': len(subjects)})


@app.route('/api/subjects/delete/<int:subject_id>', methods=['POST', 'DELETE'])
def api_delete_subject(subject_id):
    database.delete_subject(subject_id)
    return jsonify({'success': True, 'message': 'Subject deleted.'})


# --- NOTIFICATIONS APIS ---
@app.route('/api/notifications', methods=['GET'])
def api_notifications():
    user = request.args.get('user') or session.get('user', '')
    notifs = database.get_notifications(target_user=user)
    return jsonify({'notifications': notifs})


@app.route('/api/notifications/read/<int:notif_id>', methods=['POST'])
def api_read_notification(notif_id):
    database.mark_notification_read(notif_id)
    return jsonify({'success': True})


# --- TRAINING & DIAGNOSTICS APIS ---
@app.route('/api/training/train', methods=['POST'])
@app.route('/api/train', methods=['POST'])
def api_train_model():
    started, msg = model_trainer.trainer.start_training_async()
    return jsonify({'success': started, 'message': msg})


@app.route('/api/training/status', methods=['GET'])
def api_training_status():
    status = model_trainer.trainer.get_status()
    return jsonify(status)


@app.route('/api/training/logs', methods=['GET'])
def api_training_logs():
    logs = model_trainer.trainer.get_logs()
    return jsonify({'logs': logs})


@app.route('/api/register', methods=['POST'])
def api_register_student():
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

    success, msg = register.register_new_student(
        student_id, roll_number, name, department, semester, sample_images_b64, division, email, phone
    )
    return jsonify({'success': success, 'message': msg})


@app.route('/api/recognize', methods=['POST'])
def api_recognize_faces():
    img_bgr = None
    if request.is_json or request.form:
        data = request.get_json(force=True, silent=True) or request.form
        b64_str = data.get('image_b64', '')
        if b64_str:
            img_bgr = camera.decode_base64_image(b64_str)

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

    return jsonify({
        'success': True,
        'detected_faces_count': len(results),
        'faces': results
    })


@app.route('/api/health', methods=['GET'])
@app.route('/health', methods=['GET'])
def api_health():
    return jsonify({
        'status': 'ok',
        'service': 'AI Smart Attendance REST API Backend',
        'storage': config.DATA_DIR,
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })


@app.route('/api/diagnostics', methods=['GET'])
@app.route('/storage/status', methods=['GET'])
@app.route('/storage-status', methods=['GET'])
def api_diagnostics():
    import shutil
    database.init_db()
    all_students = database.get_all_students()
    all_embeddings = database.get_all_embeddings()

    dataset_dirs = []
    if os.path.exists(config.DATASET_DIR):
        dataset_dirs = [d for d in os.listdir(config.DATASET_DIR) if os.path.isdir(os.path.join(config.DATASET_DIR, d))]

    db_integrity = database.check_db_integrity()

    total_bytes, used_bytes, free_bytes = 0, 0, 0
    try:
        total_bytes, used_bytes, free_bytes = shutil.disk_usage(config.DATA_DIR)
    except Exception:
        pass

    return jsonify({
        'total_students': len(all_students),
        'total_dataset_folders': len(dataset_dirs),
        'total_embeddings': len(all_embeddings),
        'db_location': config.DB_PATH,
        'dataset_location': config.DATASET_DIR,
        'embeddings_location': config.EMBEDDINGS_DIR,
        'storage_root': config.DATA_DIR,
        'db_integrity': db_integrity,
        'free_gb': round(free_bytes / (1024**3), 2),
        'total_gb': round(total_bytes / (1024**3), 2)
    })


@app.route('/api/settings', methods=['GET', 'POST'])
def api_settings():
    if request.method == 'POST':
        data = request.get_json(force=True, silent=True) or request.form
        for key in ['recognition_threshold', 'min_face_size', 'camera_index', 'smtp_server', 'smtp_port', 'sender_email']:
            if key in data:
                database.set_setting(key, data[key])
        return jsonify({'success': True, 'message': 'Settings updated successfully.'})

    settings = {
        'recognition_threshold': database.get_setting('recognition_threshold', 0.40),
        'min_face_size': database.get_setting('min_face_size', 60),
        'camera_index': database.get_setting('camera_index', 0),
        'smtp_server': database.get_setting('smtp_server', ''),
        'sender_email': database.get_setting('sender_email', '')
    }
    return jsonify({'settings': settings})


@app.route('/api/settings/update', methods=['POST'])
def api_settings_update():
    data = request.get_json(force=True, silent=True) or request.form
    for key, val in data.items():
        database.set_setting(key, val)
    return jsonify({'success': True, 'message': 'Settings saved successfully.'})


@app.route('/api/admin/backup/create', methods=['POST'])
@app.route('/api/backup', methods=['POST'])
def api_trigger_backup():
    notes = request.json.get('notes', 'REST API Backup') if request.is_json else 'REST API Backup'
    res = backup_manager.create_backup(notes=notes)
    return jsonify(res)


@app.route('/api/admin/backup/restore', methods=['POST'])
@app.route('/api/restore', methods=['POST'])
def api_trigger_restore():
    data = request.get_json(force=True, silent=True) or request.form
    backup_filename = data.get('backup_filename', '').strip()
    if not backup_filename:
        return jsonify({'success': False, 'message': 'backup_filename parameter is required.'}), 400

    res = backup_manager.restore_backup(backup_filename)
    return jsonify(res)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting AI Smart Attendance REST API Backend on http://0.0.0.0:{port} ...")
    app.run(host='0.0.0.0', port=port, debug=True)
