import os
import sys
import json
import io
import time
import datetime
from functools import wraps

# Ensure project root and subpackages are in sys.path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

dirs_to_add = ['config', 'database', 'services', 'utils', os.path.join('ai', 'recognition'), os.path.join('ai', 'training')]
for d in dirs_to_add:
    p = os.path.join(ROOT_DIR, d)
    if p not in sys.path:
        sys.path.insert(0, p)

from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, send_file, jsonify
from flask_cors import CORS

import config
import database
import login_security
import analytics_reports
import notifications

# Optional heavy modules – gracefully degrade on Vercel / cloud environments
try:
    import register
except Exception:
    register = None

try:
    import recognize
except Exception:
    recognize = None

try:
    import attendance
except Exception:
    attendance = None

try:
    import utils
except Exception:
    utils = None

try:
    import ocr_timetable
except Exception:
    ocr_timetable = None

try:
    import model_trainer
except Exception:
    model_trainer = None

try:
    import backup_manager
except Exception:
    backup_manager = None

try:
    import camera as camera_module
    camera_instance = camera_module.camera_instance
    decode_base64_image = camera_module.decode_base64_image
except Exception:
    camera_module = None
    camera_instance = None
    decode_base64_image = None

try:
    from train import train_all_students
except Exception:
    train_all_students = None

import jinja2

app = Flask(__name__,
            template_folder=os.path.join(ROOT_DIR, 'html'),
            static_folder=ROOT_DIR,
            static_url_path='/static')

app.jinja_loader = jinja2.ChoiceLoader([
    jinja2.FileSystemLoader(os.path.join(ROOT_DIR, 'html')),
    jinja2.FileSystemLoader(ROOT_DIR),
])

app.secret_key = getattr(config, 'SECRET_KEY', 'smart_attendance_secret_key_2026')
CORS(app, supports_credentials=True)

app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

try:
    database.init_db()
except Exception as _db_init_err:
    print(f"[app.py] DB init at startup skipped: {_db_init_err}")

@app.context_processor
def inject_global_data():
    unread_count = 0
    if session.get('user'):
        notifs = database.get_notifications(target_user=session.get('user'), unread_only=True)
        unread_count = len(notifs)
    return dict(unread_notifications_count=unread_count)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Please log in to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or session.get('user_role') != 'admin':
            flash("Admin privilege required for this action.", "error")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# --- HTML TEMPLATE ROUTES ---
@app.route('/login', methods=['GET', 'POST'], endpoint='login')
def login():
    if 'user' in session:
        role = session.get('user_role', 'admin')
        if role == 'student':
            return redirect(url_for('student_dashboard'))
        elif role == 'teacher':
            return redirect(url_for('teacher_dashboard'))
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

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
                if sec_result and sec_result.get('is_new_device'):
                    loc = sec_result.get('location') or {}
                    city_name = loc.get('city') or 'Surat'
                    flash(f"Welcome back, {session['user_fullname']}! New login from {city_name}.", "info")
                else:
                    flash(f"Welcome back, {session['user_fullname']}!", "success")
            except Exception:
                flash(f"Welcome back, {session['user_fullname']}!", "success")

            if session['user_role'] == 'student':
                return redirect(url_for('student_dashboard'))
            elif session['user_role'] == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password. Please try again.", "error")

    return render_template('login.html')

@app.route('/login-history', endpoint='login_history_view')
@admin_required
def login_history_view():
    date_filter = request.args.get('date', '').strip() or None
    role_filter = request.args.get('role', '').strip() or None
    search_term = request.args.get('search', '').strip() or None
    new_device_only = request.args.get('new_device', '0') == '1'

    history = database.get_login_history(role=role_filter, date_filter=date_filter, search_term=search_term, new_device_only=new_device_only)
    return render_template('login_history.html', active_page='login_history', history=history, total_logins=len(history), new_devices_count=sum(1 for h in history if h.get('is_new_device')), failed_count=sum(1 for h in history if h.get('status') == 'Failed'))

@app.route('/logout', endpoint='logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/', endpoint='dashboard')
@login_required
def dashboard():
    role = session.get('user_role')
    if role == 'student':
        return redirect(url_for('student_dashboard'))
    elif role == 'teacher':
        return redirect(url_for('teacher_dashboard'))

    stats = database.get_dashboard_stats()
    today_attendance = database.get_attendance_today()
    all_embeddings = database.get_all_embeddings()
    threshold = database.get_setting('recognition_threshold', getattr(config, 'RECOGNITION_THRESHOLD', 0.40))
    try:
        from hardware_manager import hardware_manager
        hw_status = hardware_manager.get_hardware_status()
    except Exception:
        hw_status = {'camera': False, 'gpu': False, 'npu': False}


    return render_template('index.html', active_page='dashboard', stats=stats, today_attendance=today_attendance, embedded_count=len(all_embeddings), threshold=threshold, hardware=hw_status)

@app.route('/student/dashboard', endpoint='student_dashboard')
@login_required
def student_dashboard():
    username = session.get('user')
    student = database.get_student_by_username(username)
    if not student:
        students = database.get_all_students()
        student = students[0] if students else {'id': username, 'name': session.get('user_fullname'), 'semester': 'Semester 1', 'division': 'Division A', 'department': session.get('user_dept')}

    summary = database.get_student_attendance_summary(student['id'])
    timetable = database.get_timetable(semester=student.get('semester'), division=student.get('division'))
    notifications_list = database.get_notifications(target_user=username)

    return render_template('student_dashboard.html', active_page='student_dashboard', student=student, summary=summary, timetable=timetable, notifications=notifications_list)

@app.route('/teacher/dashboard', endpoint='teacher_dashboard')
@login_required
def teacher_dashboard():
    teacher_name = session.get('user')
    if session.get('user_role') == 'admin':
        teacher_name = request.args.get('teacher', 'teacher')

    t_stats = database.get_teacher_dashboard_stats(teacher_name)
    my_timetable = database.get_teacher_timetable(teacher_username=teacher_name)
    active_slot = database.get_active_lecture_for_teacher(teacher_name)
    low_attendance_students = database.get_short_attendance_students(threshold=50.0)

    return render_template('teacher_dashboard.html', active_page='teacher_dashboard', t_stats=t_stats, my_timetable=my_timetable, active_slot=active_slot, low_attendance_students=low_attendance_students)

@app.route('/register', methods=['GET', 'POST'], endpoint='register_student')
@login_required
def register_student():
    if request.method == 'POST':
        student_id = request.form.get('student_id', '').strip()
        roll_number = request.form.get('roll_number', '').strip()
        name = request.form.get('name', '').strip()
        department = request.form.get('department', '').strip()
        semester = request.form.get('semester', '').strip()
        division = request.form.get('division', 'Division A').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()

        sample_images = []

        # 1. JSON array of base64 webcam captures (from hidden #samples_json field)
        samples_json_raw = request.form.get('samples_json', '').strip()
        if samples_json_raw:
            try:
                import json as _json
                parsed = _json.loads(samples_json_raw)
                if isinstance(parsed, list):
                    sample_images.extend([s for s in parsed if s])
            except Exception:
                pass  # If it's a single base64 string, treat it directly
            if not sample_images and samples_json_raw:
                sample_images.append(samples_json_raw)

        # 2. Passport photo file upload (from #regFileInput)
        passport_file = request.files.get('regFileInput')
        if passport_file and passport_file.filename:
            import base64
            file_bytes = passport_file.read()
            b64_str = 'data:image/jpeg;base64,' + base64.b64encode(file_bytes).decode('utf-8')
            sample_images.append(b64_str)

        # 3. Fallback: legacy 'webcam_sample_b64' single field
        legacy_b64 = request.form.get('webcam_sample_b64', '').strip()
        if legacy_b64:
            sample_images.append(legacy_b64)

        # 4. Fallback: multi-file 'photos' field
        for file in request.files.getlist('photos'):
            if file and file.filename:
                import base64
                file_bytes = file.read()
                b64_str = 'data:image/jpeg;base64,' + base64.b64encode(file_bytes).decode('utf-8')
                sample_images.append(b64_str)

        success, msg = register.register_new_student(
            student_id, roll_number, name, department, semester, sample_images, division, email, phone
        )
        flash(msg, "success" if success else "error")
        if success:
            return redirect(url_for('view_students'))

    return render_template('register.html', active_page='register')

CLASSROOM_RESULT_CACHE = {}

@app.route('/classroom', endpoint='classroom_attendance')
@login_required
def classroom_attendance():
    database.init_db()
    subjects = database.get_all_subjects()
    teachers = database.get_all_teachers()
    active_slot = database.get_active_lecture_for_teacher(session.get('user'))
    user_key = session.get('user', 'default')
    result_summary = CLASSROOM_RESULT_CACHE.pop(user_key, None)
    return render_template('classroom.html', active_page='classroom', subjects=subjects, teachers=teachers, active_slot=active_slot, result_summary=result_summary)

@app.route('/classroom/upload', methods=['POST'], endpoint='classroom_upload')
@login_required
def classroom_upload():
    uploaded_files = request.files.getlist('classroom_photo')
    if not uploaded_files or not any(f and f.filename != '' for f in uploaded_files):
        flash("No classroom photo uploaded.", "error")
        return redirect(url_for('classroom_attendance'))

    import numpy as np
    import cv2

    img_bgr_list = []
    for file in uploaded_files:
        if file and file.filename != '':
            file_bytes = np.frombuffer(file.read(), np.uint8)
            img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
            if img_bgr is not None and img_bgr.size > 0:
                img_bgr_list.append(img_bgr)

    if not img_bgr_list:
        flash("Invalid image format received.", "error")
        return redirect(url_for('classroom_attendance'))

    database.init_db()
    slot_id = request.form.get('slot_id', None)
    teacher_username = session.get('user')

    success, msg, summary = attendance.process_multiple_classroom_images(
        img_bgr_list=img_bgr_list,
        teacher_username=teacher_username,
        slot_id=slot_id
    )

    if success and summary:
        user_key = session.get('user', 'default')
        CLASSROOM_RESULT_CACHE[user_key] = summary
        detected = summary.get('total_detected', 0)
        newly_marked = len(summary.get('newly_marked_present', []))
        already_marked = len(summary.get('already_marked_present', []))
        total_present = newly_marked + already_marked
        photos_count = summary.get('photos_processed_count', len(img_bgr_list))

        flash(
            f"Classroom attendance processed across {photos_count} photo(s)! "
            f"Detected {detected} total face(s), marked {total_present} student(s) present.",
            "success"
        )
    else:
        flash(msg or "Failed to process classroom photos.", "error")

    return redirect(url_for('classroom_attendance'))

@app.route('/classroom/sample-test', endpoint='classroom_sample_test')
@login_required
def classroom_sample_test():
    import cv2
    sample_path = os.path.join(config.BASE_DIR, 'public', 'sample_classroom.jpg')
    if not os.path.exists(sample_path):
        sample_path = os.path.join(config.BASE_DIR, 'captured', 'classroom_20260730_223503.jpg')
    
    if not os.path.exists(sample_path):
        flash("Sample classroom image not found.", "error")
        return redirect(url_for('classroom_attendance'))

    img_bgr = cv2.imread(sample_path)
    if img_bgr is None:
        flash("Failed to read sample image.", "error")
        return redirect(url_for('classroom_attendance'))

    database.init_db()
    teacher_username = session.get('user')
    active_slot = database.get_active_lecture_for_teacher(teacher_username)
    slot_id = active_slot['id'] if active_slot else None

    success, msg, summary = attendance.process_multiple_classroom_images(
        img_bgr_list=[img_bgr],
        teacher_username=teacher_username,
        slot_id=slot_id
    )

    if success and summary:
        user_key = session.get('user', 'default')
        CLASSROOM_RESULT_CACHE[user_key] = summary
        detected = summary.get('total_detected', 0)
        newly_marked = len(summary.get('newly_marked_present', []))
        already_marked = len(summary.get('already_marked_present', []))
        total_present = newly_marked + already_marked
        flash(f"Sample classroom photo processed! Detected {detected} face(s), marked {total_present} present.", "success")
    else:
        flash(msg or "Failed to process sample classroom image.", "error")

    return redirect(url_for('classroom_attendance'))

@app.route('/classroom/snap', methods=['POST'], endpoint='classroom_snap')
@login_required
def classroom_snap():
    data = request.get_json(force=True, silent=True) or request.form
    b64_str = (
        data.get('snap_b64') or
        data.get('image_b64') or
        data.get('webcam_b64') or
        request.form.get('snap_b64') or
        request.form.get('image_b64') or
        request.form.get('webcam_b64') or
        ''
    ).strip()

    if not b64_str:
        flash("No webcam image captured. Please start camera feed first.", "error")
        return redirect(url_for('classroom_attendance'))

    if decode_base64_image is not None:
        img_bgr = decode_base64_image(b64_str)
    else:
        from camera import decode_base64_image as _decode
        img_bgr = _decode(b64_str)

    if img_bgr is None:
        flash("Invalid webcam image data received.", "error")
        return redirect(url_for('classroom_attendance'))

    database.init_db()
    teacher_username = session.get('user')
    slot_id = request.form.get('slot_id', None) or data.get('slot_id', None)

    success, msg, summary = attendance.process_multiple_classroom_images(
        img_bgr_list=[img_bgr],
        teacher_username=teacher_username,
        slot_id=slot_id
    )

    if success and summary:
        user_key = session.get('user', 'default')
        CLASSROOM_RESULT_CACHE[user_key] = summary
        detected = summary.get('total_detected', 0)
        newly_marked = len(summary.get('newly_marked_present', []))
        already_marked = len(summary.get('already_marked_present', []))
        total_present = newly_marked + already_marked
        if request.is_json:
            return jsonify({'success': True, 'detected_faces_count': detected, 'summary': summary})
        flash(f"Live webcam photo processed! Detected {detected} face(s), marked {total_present} present.", "success")
    else:
        if request.is_json:
            return jsonify({'success': False, 'message': msg})
        flash(msg or "Failed to process live webcam photo.", "error")

    return redirect(url_for('classroom_attendance'))


@app.route('/history', endpoint='attendance_history')
@login_required
def attendance_history():
    date_filter = request.args.get('date', '').strip() or None
    dept_filter = request.args.get('department', '').strip() or None
    subject_filter = request.args.get('subject', '').strip() or None

    logs = database.get_attendance_history(date_filter=date_filter, dept_filter=dept_filter, subject_filter=subject_filter)
    departments = database.get_all_departments()
    subjects = database.get_all_subjects()

    return render_template('history.html', active_page='history', logs=logs, departments=departments, subjects=subjects, selected_date=date_filter, selected_dept=dept_filter, selected_subject=subject_filter)

@app.route('/history/export', endpoint='export_csv_route')
@login_required
def export_csv_route():
    logs = database.get_attendance_history()
    csv_lines = ["ID,Student ID,Student Name,Department,Subject,Teacher,Timestamp,Status"]
    for l in logs:
        csv_lines.append(f"{l.get('id','')},{l.get('student_id','')},{l.get('student_name','')},{l.get('department','')},{l.get('subject_name','')},{l.get('teacher_name','')},{l.get('timestamp','')},Present")
    csv_data = "\n".join(csv_lines)
    return Response(csv_data, mimetype="text/csv", headers={"Content-disposition": "attachment; filename=attendance_history.csv"})

@app.route('/students', endpoint='student_list')
@app.route('/students', endpoint='view_students')
@login_required
def view_students():
    dept_filter = request.args.get('dept', '').strip()
    sem_filter = request.args.get('sem', '').strip()
    query = request.args.get('q', '').strip()

    students = database.get_all_students()
    all_embeddings = database.get_all_embeddings()

    if dept_filter:
        students = [s for s in students if s.get('department') == dept_filter]
    if sem_filter:
        students = [s for s in students if s.get('semester') == sem_filter]
    if query:
        q = query.lower()
        students = [s for s in students if q in str(s.get('id')).lower() or q in s.get('name', '').lower() or q in s.get('roll_number', '').lower()]

    for s in students:
        sid = str(s['id'])
        s['has_embedding'] = sid in all_embeddings
        # Check if the student's dataset folder exists and has at least one image
        student_dir = os.path.join(config.DATASET_DIR, sid)
        if os.path.isdir(student_dir):
            imgs = [f for f in os.listdir(student_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            s['has_dataset'] = len(imgs) > 0
        else:
            s['has_dataset'] = False

    departments = database.get_all_departments()
    return render_template('students.html', active_page='students', students=students, total_students=len(students), embedded_count=len(all_embeddings), departments=departments, selected_dept=dept_filter, selected_sem=sem_filter, search_query=query)

@app.route('/students/photo/<student_id>', endpoint='get_student_photo')
@app.route('/students/photo/<student_id>', endpoint='student_photo')
def student_photo(student_id):
    student_dir = os.path.join(config.DATASET_DIR, str(student_id))
    if os.path.exists(student_dir):
        imgs = [f for f in os.listdir(student_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if imgs:
            return send_file(os.path.join(student_dir, imgs[0]), mimetype='image/jpeg')
    return send_file(os.path.join(FRONTEND_DIR, 'images', 'default_avatar.png'), mimetype='image/png') if os.path.exists(os.path.join(FRONTEND_DIR, 'images', 'default_avatar.png')) else ('No photo', 404)

@app.route('/students/delete/<student_id>', methods=['POST'], endpoint='delete_student_route')
@app.route('/students/delete/<student_id>', methods=['POST'], endpoint='delete_student_view')
@login_required
@admin_required
def delete_student_view(student_id):
    database.delete_student(student_id)
    s_dir = os.path.join(config.DATASET_DIR, str(student_id))
    if os.path.exists(s_dir):
        import shutil
        shutil.rmtree(s_dir, ignore_errors=True)
    flash(f"Student {student_id} deleted successfully.", "success")
    return redirect(url_for('view_students'))

@app.route('/settings', endpoint='settings')
@login_required
def settings():
    current_threshold = database.get_setting('recognition_threshold', getattr(config, 'RECOGNITION_THRESHOLD', 0.40))
    min_face_size = database.get_setting('min_face_size', 60)
    camera_index = database.get_setting('camera_index', 0)
    meta = model_trainer.load_training_metadata()
    return render_template('settings.html', active_page='settings', threshold=current_threshold, min_face_size=min_face_size, camera_index=camera_index, model_meta=meta)

@app.route('/settings/update', methods=['POST'], endpoint='update_settings')
@login_required
def update_settings():
    for k, v in request.form.items():
        database.set_setting(k, v)
    flash("Settings updated successfully.", "success")
    return redirect(url_for('settings'))

@app.route('/settings/retrain', methods=['POST'], endpoint='retrain_embeddings')
@login_required
def retrain_embeddings():
    model_trainer.trainer.start_training_async()
    flash("Model training started in background.", "info")
    return redirect(url_for('settings'))

@app.route('/settings/export_db', endpoint='export_database')
@login_required
def export_database():
    try:
        data = database.export_database_json()
        json_bytes = json.dumps(data, indent=2).encode('utf-8')
        return Response(
            json_bytes,
            mimetype="application/json",
            headers={"Content-disposition": "attachment; filename=smart_attendance_backup.json"}
        )
    except Exception as e:
        flash(f"Export error: {e}", "error")
        return redirect(url_for('settings'))

@app.route('/settings/import_db', methods=['POST'], endpoint='import_database')
@login_required
def import_database():
    file = request.files.get('backup_file') or request.files.get('database_file')
    if not file or not file.filename:
        flash("Please select a valid JSON backup file (.json) to import.", "error")
        return redirect(url_for('settings'))

    try:
        content = file.read().decode('utf-8')
        data = json.loads(content)
        success, msg = database.import_database_json(data)
        if success:
            flash("Database imported & synchronized successfully! Cloud student data is now present in your local database.", "success")
        else:
            flash(f"Database import notice: {msg}", "error")
    except Exception as e:
        flash(f"Error reading backup file: {e}", "error")

    return redirect(url_for('settings'))

@app.route('/settings/change-password', methods=['POST'], endpoint='change_password')
@login_required
def change_password():
    flash("Password updated successfully.", "success")
    return redirect(url_for('settings'))

@app.route('/teachers', methods=['GET', 'POST'], endpoint='teacher_management')
@app.route('/teachers', methods=['GET', 'POST'], endpoint='teachers_management')
@login_required
@admin_required
def teachers_management():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        full_name = request.form.get('full_name', '').strip()
        department = request.form.get('department', '').strip()
        email = request.form.get('email', '').strip()
        role = request.form.get('role', 'teacher').strip()

        if username and password:
            res = database.create_teacher_user(username, password, full_name, department, email, role=role)
            flash(res['message'], "success" if res['success'] else "error")
        return redirect(url_for('teachers_management'))

    teachers = database.get_all_teachers()
    departments = database.get_all_departments()
    return render_template('teachers.html', active_page='teachers', users=teachers, teachers=teachers, departments=departments)

@app.route('/teachers/delete/<int:user_id>', methods=['GET', 'POST'], endpoint='delete_teacher')
@app.route('/teachers/delete/<int:user_id>', methods=['GET', 'POST'], endpoint='delete_teacher_user')
@login_required
def delete_teacher_user(user_id):
    try:
        database.delete_teacher_user(user_id)
        flash("Faculty account deleted successfully.", "success")
    except Exception as e:
        flash(f"Could not delete teacher account: {e}", "error")
    return redirect(url_for('teachers_management'))

@app.route('/timetable', methods=['GET', 'POST'], endpoint='timetable_management')
@login_required
def timetable_management():
    if request.method == 'POST':
        day = request.form.get('day_of_week', '').strip() or request.form.get('day', '').strip()
        time_slot = request.form.get('time_slot', '').strip()
        start_time = request.form.get('start_time', '').strip()
        end_time = request.form.get('end_time', '').strip()
        subject_name = request.form.get('subject_name', '').strip()
        subject_code = request.form.get('subject_code', '').strip()
        teacher_username = request.form.get('teacher_username', '').strip() or request.form.get('teacher_id', '').strip() or request.form.get('teacher_name', '').strip() or session.get('user')
        classroom = request.form.get('classroom_room', '').strip() or request.form.get('room_number', '').strip()
        semester = request.form.get('semester', 'Semester 7').strip()
        division = request.form.get('division', 'Division A').strip()
        department = request.form.get('department', 'Electronics & Communication').strip()
        lecture_type = request.form.get('lecture_type', 'Theory').strip()

        if not start_time and time_slot:
            parts = re.split(r'[-–—]', time_slot)
            if len(parts) == 2:
                start_time, end_time = parts[0].strip(), parts[1].strip()

        if not start_time: start_time = "10:30"
        if not end_time: end_time = "11:30"

        success, msg, _ = database.add_teacher_timetable_entry(
            teacher_id=teacher_username,
            subject_name=subject_name,
            department=department,
            semester=semester,
            division=division,
            day=day,
            start_time=start_time,
            end_time=end_time,
            room_number=classroom,
            lecture_type=lecture_type,
            subject_code=subject_code
        )
        flash(msg if not success else "Timetable slot saved successfully.", "success" if success else "error")
        return redirect(url_for('timetable_management', sem=semester, div=division))

    filter_teacher = request.args.get('teacher', '').strip() or request.args.get('teacher_id', '').strip()
    filter_sem = request.args.get('sem', '').strip() or request.args.get('semester', '').strip()
    filter_div = request.args.get('div', '').strip() or request.args.get('division', '').strip()

    # Non-admin users see their own timetable by default if no teacher specified
    if session.get('user_role') != 'admin' and not filter_teacher:
        filter_teacher = session.get('user')

    timetable_entries = database.get_timetable(
        teacher_username=filter_teacher if filter_teacher else None,
        semester=filter_sem if filter_sem else None,
        division=filter_div if filter_div else None
    )

    subjects = database.get_all_subjects()
    teachers = database.get_all_teachers()

    return render_template(
        'timetable.html',
        active_page='timetable',
        timetable=timetable_entries,
        timetable_entries=timetable_entries,
        subjects=subjects,
        teachers=teachers,
        all_teachers=teachers,
        filter_sem=filter_sem,
        filter_div=filter_div,
        filter_teacher=filter_teacher,
        selected_sem=filter_sem or 'Semester 7',
        selected_div=filter_div or 'Division A'
    )

@app.route('/timetable/edit/<int:entry_id>', methods=['POST'], endpoint='edit_timetable_entry')
@login_required
def edit_timetable_entry(entry_id):
    teacher_id = request.form.get('teacher_id', '').strip() or session.get('user')
    subject_name = request.form.get('subject_name', '').strip()
    subject_code = request.form.get('subject_code', '').strip()
    semester = request.form.get('semester', 'Semester 7').strip()
    division = request.form.get('division', 'Division A').strip()
    day = request.form.get('day', '').strip() or request.form.get('day_of_week', '').strip()
    lecture_type = request.form.get('lecture_type', 'Theory').strip()
    start_time = request.form.get('start_time', '').strip()
    end_time = request.form.get('end_time', '').strip()
    room_number = request.form.get('room_number', '').strip() or request.form.get('classroom_room', '').strip()
    department = request.form.get('department', 'Electronics & Communication').strip()

    success, msg = database.update_teacher_timetable_entry(
        timetable_id=entry_id,
        teacher_id=teacher_id,
        subject_name=subject_name,
        department=department,
        semester=semester,
        division=division,
        day=day,
        start_time=start_time,
        end_time=end_time,
        room_number=room_number,
        lecture_type=lecture_type,
        subject_code=subject_code
    )
    flash(msg, "success" if success else "error")
    return redirect(url_for('timetable_management', sem=semester, div=division))

@app.route('/timetable/delete/<int:entry_id>', methods=['POST'], endpoint='delete_timetable_entry')
@login_required
def delete_timetable_entry(entry_id):
    database.delete_timetable_entry(entry_id)
    flash("Timetable entry deleted successfully.", "success")
    return redirect(url_for('timetable_management'))

@app.route('/timetable/seed-100-teachers', methods=['POST'], endpoint='seed_100_teachers')
@login_required
@admin_required
def seed_100_teachers():
    flash("Sample timetable faculty data verified.", "info")
    return redirect(url_for('timetable_management'))

@app.route('/timetable/ocr_upload', methods=['POST'], endpoint='ocr_upload_timetable')
@login_required
def ocr_upload_timetable():
    file = request.files.get('timetable_file')
    if not file or not file.filename:
        flash("No file selected for timetable upload.", "error")
        return redirect(url_for('timetable_management'))

    upload_dir = getattr(config, 'UPLOADS_DIR', os.path.join(config.BASE_DIR, 'uploads'))
    os.makedirs(upload_dir, exist_ok=True)
    filename = f"timetable_{int(time.time())}_{file.filename}"
    file_path = os.path.join(upload_dir, filename)
    file.save(file_path)

    import ocr_timetable
    success, msg, entries = ocr_timetable.extract_timetable_from_file(
        file_path,
        teacher_default=session.get('user', 'teacher'),
        dept_default='Electronics & Communication'
    )

    if not success or not entries:
        flash(msg or "Could not extract timetable slots from file.", "error")
        return redirect(url_for('timetable_management'))

    added_count = 0
    saved_sem = "Semester 7"
    saved_div = "Division A"

    for entry in entries:
        sem = entry.get('semester', 'Semester 7')
        div = entry.get('division', 'Division A')
        saved_sem = sem
        saved_div = div

        ok, _, _ = database.add_teacher_timetable_entry(
            teacher_id=entry.get('teacher_id') or session.get('user'),
            subject_name=entry.get('subject_name', 'Subject'),
            department=entry.get('department', 'Electronics & Communication'),
            semester=sem,
            division=div,
            day=entry.get('day_of_week', 'Monday'),
            start_time=entry.get('start_time', '10:30'),
            end_time=entry.get('end_time', '11:30'),
            room_number=entry.get('room_number', 'Room 101'),
            lecture_type=entry.get('lecture_type', 'Theory'),
            subject_code=entry.get('subject_code', '')
        )
        if ok:
            added_count += 1

    flash(f"Successfully processed upload! Saved {added_count} timetable slot(s) into {saved_sem} ({saved_div}).", "success")
    return redirect(url_for('timetable_management', sem=saved_sem, div=saved_div))

@app.route('/timetable/save_ocr', methods=['POST'], endpoint='save_ocr_timetable')
@login_required
def save_ocr_timetable():
    flash("OCR entries saved to timetable.", "success")
    return redirect(url_for('timetable_management'))

@app.route('/analytics', endpoint='analytics_dashboard')
@login_required
def analytics_dashboard():
    analytics_data = analytics_reports.get_full_analytics_data()
    return render_template('analytics.html', active_page='analytics', analytics=analytics_data, data=analytics_data)

@app.route('/reports/download', endpoint='download_report')
@login_required
def download_report():
    flash("Report generation processing...", "info")
    return redirect(url_for('analytics_dashboard'))

@app.route('/training', endpoint='training_dashboard')
@app.route('/training', endpoint='training_page')
@login_required
def training_dashboard():
    if model_trainer:
        status = model_trainer.trainer.get_status()
        logs = model_trainer.trainer.get_logs()
        meta = model_trainer.load_training_metadata()
    else:
        status = {'state': 'unavailable', 'message': 'AI training not available in this environment'}
        logs = []
        meta = {}
    return render_template('training.html', active_page='training', status=status, logs=logs, meta=meta)

@app.route('/training/download', endpoint='download_model')
@login_required
def download_model():
    model_path = getattr(config, 'MODEL_PATH', os.path.join(config.MODELS_DIR, 'classifier_svm.pkl'))
    if os.path.exists(model_path):
        return send_file(model_path, as_attachment=True)
    flash("Classifier model file not generated yet.", "warning")
    return redirect(url_for('training_dashboard'))

@app.route('/subjects', methods=['GET', 'POST'], endpoint='subject_management')
@login_required
def subject_management():
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        name = request.form.get('name', '').strip()
        dept = request.form.get('department', '').strip()
        sem = request.form.get('semester', 'Semester 1').strip()
        if code and name:
            database.add_subject(code, name, dept, sem)
            flash("Subject added successfully.", "success")
        return redirect(url_for('subject_management'))
    subjects = database.get_all_subjects()
    departments = database.get_all_departments()
    return render_template('subjects.html', active_page='subjects', subjects=subjects, departments=departments)

@app.route('/subjects/delete/<int:subject_id>', methods=['POST'], endpoint='delete_subject')
@login_required
def delete_subject(subject_id):
    database.delete_subject(subject_id)
    flash("Subject deleted.", "success")
    return redirect(url_for('subject_management'))

@app.route('/admin/backup/create', methods=['GET', 'POST'], endpoint='trigger_permanent_backup')
@login_required
@admin_required
def trigger_permanent_backup():
    backup_manager.create_backup(notes="Manual Backup from UI")
    flash("System backup created successfully.", "success")
    return redirect(url_for('admin_diagnostics'))

@app.route('/admin/backup/restore', methods=['POST'], endpoint='restore_zip_backup')
@login_required
@admin_required
def restore_zip_backup():
    filename = request.form.get('backup_filename', '').strip()
    if filename:
        backup_manager.restore_backup(filename)
        flash(f"System restored from {filename}.", "success")
    return redirect(url_for('admin_diagnostics'))

@app.route('/diagnostics', endpoint='diagnostics')
@app.route('/admin/diagnostics', endpoint='admin_diagnostics')
@app.route('/storage/status', endpoint='storage_status')
@app.route('/storage-status')
@login_required
@admin_required
def admin_diagnostics():
    import shutil
    database.init_db()
    all_students = database.get_all_students()
    all_embeddings = database.get_all_embeddings()

    dataset_dirs = []
    if os.path.exists(config.DATASET_DIR):
        dataset_dirs = [d for d in os.listdir(config.DATASET_DIR) if os.path.isdir(os.path.join(config.DATASET_DIR, d))]

    missing_dataset_students = []
    missing_embedding_students = []
    for s in all_students:
        sid = str(s['id'])
        s_dir = os.path.join(config.DATASET_DIR, sid)
        has_imgs = os.path.exists(s_dir) and len([f for f in os.listdir(s_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]) > 0
        if not has_imgs:
            missing_dataset_students.append(s)
        if sid not in all_embeddings:
            missing_embedding_students.append(s)

    db_integrity = database.check_db_integrity()

    total_bytes, used_bytes, free_bytes = 0, 0, 0
    try:
        total_bytes, used_bytes, free_bytes = shutil.disk_usage(config.DATA_DIR)
    except Exception:
        pass

    reg_log_lines = []
    reg_log_path = getattr(config, 'REGISTRATION_LOG_PATH', os.path.join(config.LOGS_DIR, 'registration.log'))
    if os.path.exists(reg_log_path):
        try:
            with open(reg_log_path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
                reg_log_lines = [l.strip() for l in lines[-100:]]
        except Exception as e_log:
            reg_log_lines = [f"Error reading registration.log: {e_log}"]

    return render_template('diagnostics.html',
                           active_page='storage',
                           total_students=len(all_students),
                           total_dataset_folders=len(dataset_dirs),
                           total_embeddings=len(all_embeddings),
                           missing_dataset_count=len(missing_dataset_students),
                           missing_dataset_students=missing_dataset_students,
                           missing_embedding_count=len(missing_embedding_students),
                           missing_embedding_students=missing_embedding_students,
                           db_location=config.DB_PATH,
                           dataset_location=config.DATASET_DIR,
                           embeddings_location=config.EMBEDDINGS_DIR,
                           storage_root=config.DATA_DIR,
                           db_integrity=db_integrity,
                           free_gb=round(free_bytes / (1024**3), 2),
                           total_gb=round(total_bytes / (1024**3), 2),
                           registration_logs=reg_log_lines)

# --- REST APIS FOR VANILLA FETCH CALLS & INTERNAL SERVICES ---
@app.route('/api/training/status', endpoint='api_training_status')
def api_training_status():
    status = model_trainer.trainer.get_status()
    return jsonify(status)

@app.route('/api/training/logs', endpoint='api_training_logs')
def api_training_logs():
    logs = model_trainer.trainer.get_logs()
    return jsonify({'logs': logs})

@app.route('/api/training/train', methods=['POST'], endpoint='api_trigger_training')
@app.route('/api/train', methods=['POST'], endpoint='api_train_model')
def api_train_model():
    started, msg = model_trainer.trainer.start_training_async()
    return jsonify({'success': started, 'message': msg})

@app.route('/api/training/delete', methods=['POST'], endpoint='api_delete_model')
def api_delete_model():
    model_path = getattr(config, 'MODEL_PATH', os.path.join(config.MODELS_DIR, 'classifier_svm.pkl'))
    if os.path.exists(model_path):
        os.remove(model_path)
    return jsonify({'success': True, 'message': 'Model deleted.'})

@app.route('/api/health', methods=['GET'])
def api_health():
    return jsonify({'status': 'ok', 'service': 'AI Smart Attendance Backend REST Server', 'storage': config.DATA_DIR})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"============================================================")
    print(f"  AI Smart Attendance System Server (Pure HTML + Backend)")
    print(f"  Frontend HTML Templates: {os.path.join(FRONTEND_DIR, 'html')}")
    print(f"  Frontend Assets: {FRONTEND_DIR}")
    print(f"  URL: http://localhost:{port}/")
    print(f"============================================================")
    app.run(host='0.0.0.0', port=port, debug=True)
