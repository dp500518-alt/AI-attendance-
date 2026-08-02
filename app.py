import os
import json
import io
import time
import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, send_file, jsonify
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
app.secret_key = config.SECRET_KEY

# Set Max Payload Limit to 100 MB
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# Initialize database on app startup
database.init_db()

@app.context_processor
def inject_global_data():
    unread_count = 0
    if session.get('user'):
        notifs = database.get_notifications(target_user=session.get('user'), unread_only=True)
        unread_count = len(notifs)
    return dict(unread_notifications_count=unread_count)

@app.errorhandler(413)
def request_entity_too_large(error):
    flash("The uploaded file or photo batch exceeds maximum limit (100MB). Please select smaller photo files.", "error")
    return redirect(request.referrer or url_for('dashboard'))

# Authentication Helper Decorators
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

# 1. Login & Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
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

            # Process Security Login Tracking & New Device Alert Email
            sec_result = login_security.process_login_security(
                username=user['username'],
                role=user.get('role', 'teacher'),
                full_name=session['user_fullname'],
                request_obj=request,
                session_id=session.get('_id', ''),
                status='Success'
            )

            if sec_result.get('is_new_device'):
                flash(f"Welcome back, {session['user_fullname']}! 🔒 New login detected from {sec_result['location']['city']}.", "info")
            else:
                flash(f"Welcome back, {session['user_fullname']}!", "success")

            if session['user_role'] == 'student':
                return redirect(url_for('student_dashboard'))
            elif session['user_role'] == 'teacher':
                return redirect(url_for('teacher_dashboard'))
            return redirect(url_for('dashboard'))
        else:
            # Record failed login attempt
            if username:
                login_security.process_login_security(
                    username=username,
                    role='unknown',
                    full_name=username,
                    request_obj=request,
                    session_id='',
                    status='Failed'
                )
            flash("Invalid username or password. Please try again.", "error")

    return render_template('login.html')

@app.route('/login-history')
@admin_required
def login_history_view():
    date_filter = request.args.get('date', '').strip() or None
    role_filter = request.args.get('role', '').strip() or None
    search_term = request.args.get('search', '').strip() or None
    new_device_only = request.args.get('new_device', '0') == '1'

    history = database.get_login_history(
        role=role_filter,
        date_filter=date_filter,
        search_term=search_term,
        new_device_only=new_device_only
    )

    total_logins = len(history)
    new_devices_count = sum(1 for h in history if h.get('is_new_device'))
    failed_count = sum(1 for h in history if h.get('status') == 'Failed')

    return render_template('login_history.html',
                           active_page='login_history',
                           history=history,
                           total_logins=total_logins,
                           new_devices_count=new_devices_count,
                           failed_count=failed_count,
                           selected_date=date_filter,
                           selected_role=role_filter,
                           search_term=search_term,
                           new_device_only=new_device_only)

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# 2. Portals (Student, Teacher, Admin Dashboards)
@app.route('/')
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
    threshold = database.get_setting('recognition_threshold', config.RECOGNITION_THRESHOLD)
    from hardware_manager import hardware_manager
    hw_status = hardware_manager.get_hardware_status()

    return render_template('index.html',
                           active_page='dashboard',
                           stats=stats,
                           today_attendance=today_attendance,
                           embedded_count=len(all_embeddings),
                           threshold=threshold,
                           hardware=hw_status)

@app.route('/student/dashboard')
@login_required
def student_dashboard():
    username = session.get('user')
    student = database.get_student_by_username(username)
    
    if not student:
        # Fallback to first student or dummy object if not mapped
        students = database.get_all_students()
        student = students[0] if students else {'id': username, 'name': session.get('user_fullname'), 'semester': 'Semester 1', 'division': 'Division A', 'department': session.get('user_dept')}

    summary = database.get_student_attendance_summary(student['id'])
    timetable = database.get_timetable(semester=student.get('semester'), division=student.get('division'))
    notifications_list = database.get_notifications(target_user=username)

    return render_template('student_dashboard.html',
                           active_page='student_dashboard',
                           student=student,
                           summary=summary,
                           timetable=timetable,
                           notifications=notifications_list)

@app.route('/teacher/dashboard')
@login_required
def teacher_dashboard():
    teacher_name = session.get('user')
    if session.get('user_role') == 'admin':
        # Admin viewing teacher dashboard fallback
        teacher_name = request.args.get('teacher', 'teacher')

    t_stats = database.get_teacher_dashboard_stats(teacher_name)
    my_timetable = database.get_teacher_timetable(teacher_username=teacher_name)
    active_slot = database.get_active_lecture_for_teacher(teacher_name)
    low_attendance_students = database.get_short_attendance_students(threshold=50.0)

    return render_template('teacher_dashboard.html',
                           active_page='teacher_dashboard',
                           t_stats=t_stats,
                           my_timetable=my_timetable,
                           active_slot=active_slot,
                           low_attendance_students=low_attendance_students)


# 3. Student Registration Route
@app.route('/register', methods=['GET', 'POST'])
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
        samples_json = request.form.get('samples_json', '')

        sample_images_b64 = []
        if samples_json:
            try:
                sample_images_b64 = json.loads(samples_json)
            except Exception as e:
                print("Error parsing sample images JSON:", e)

        success, msg = register.register_new_student(
            student_id, roll_number, name, department, semester, sample_images_b64, division, email, phone
        )

        if success:
            flash(msg, "success")
            return redirect(url_for('student_list'))
        else:
            flash(msg, "error")

    return render_template('register.html', active_page='register')

# 4. Classroom Attendance Route
@app.route('/classroom')
@login_required
def classroom_attendance():
    selected_slot_id = request.args.get('slot_id', type=int)
    teacher_name = session.get('user')
    if session.get('user_role') == 'admin':
        teacher_name = request.args.get('teacher')

    active_slot = database.get_active_lecture_for_teacher(teacher_name, slot_id=selected_slot_id) if teacher_name else database.get_active_timetable_slot(slot_id=selected_slot_id)
    all_slots = database.get_teacher_timetable(teacher_username=teacher_name if session.get('user_role') != 'admin' else None)
    return render_template('classroom.html', active_page='classroom', active_slot=active_slot, all_slots=all_slots, result_summary=None)

@app.route('/classroom/upload', methods=['POST'])
@login_required
def classroom_upload():
    files = request.files.getlist('classroom_photo')
    if not files or all(f.filename == '' for f in files):
        flash("No photo file(s) selected.", "error")
        return redirect(url_for('classroom_attendance'))

    selected_slot_id = request.form.get('slot_id', type=int)
    teacher_name = session.get('user') if session.get('user_role') != 'admin' else None

    try:
        import numpy as np
        import cv2

        img_bgr_list = []
        for file in files:
            if file and file.filename != '':
                file_bytes = np.frombuffer(file.read(), np.uint8)
                img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
                if img_bgr is not None and img_bgr.size > 0:
                    img_bgr_list.append(img_bgr)

        if not img_bgr_list:
            flash("Could not read any valid image files.", "error")
            return redirect(url_for('classroom_attendance'))

        threshold_val = float(database.get_setting('recognition_threshold', config.RECOGNITION_THRESHOLD))
        success, msg, summary = attendance.process_multiple_classroom_images(
            img_bgr_list,
            custom_threshold=threshold_val,
            teacher_username=teacher_name,
            slot_id=selected_slot_id
        )

        active_slot = database.get_active_timetable_slot(teacher_username=teacher_name, slot_id=selected_slot_id)
        all_slots = database.get_timetable(teacher_username=teacher_name)

        if success:
            flash(msg, "success")
            return render_template('classroom.html', active_page='classroom', active_slot=active_slot, all_slots=all_slots, result_summary=summary)
        else:
            flash(msg, "error")

    except Exception as e:
        flash(f"Error processing images: {e}", "error")

    return redirect(url_for('classroom_attendance'))

@app.route('/classroom/snap', methods=['POST'])
@login_required
def classroom_snap():
    snap_b64 = request.form.get('snap_b64', '')
    selected_slot_id = request.form.get('slot_id', type=int)
    teacher_name = session.get('user') if session.get('user_role') != 'admin' else None

    if not snap_b64:
        flash("No camera snapshot received.", "error")
        return redirect(url_for('classroom_attendance'))

    try:
        img_bgr = decode_base64_image(snap_b64)
        threshold_val = float(database.get_setting('recognition_threshold', config.RECOGNITION_THRESHOLD))
        success, msg, summary = attendance.process_classroom_image(
            img_bgr,
            custom_threshold=threshold_val,
            teacher_username=teacher_name,
            slot_id=selected_slot_id
        )

        active_slot = database.get_active_timetable_slot(teacher_username=teacher_name, slot_id=selected_slot_id)
        all_slots = database.get_timetable(teacher_username=teacher_name)

        if success:
            flash(msg, "success")
            return render_template('classroom.html', active_page='classroom', active_slot=active_slot, all_slots=all_slots, result_summary=summary)
        else:
            flash(msg, "error")
    except Exception as e:
        flash(f"Error processing camera snapshot: {e}", "error")

    return redirect(url_for('classroom_attendance'))

# 5. Attendance History & Export Routes
@app.route('/history')
@login_required
def attendance_history():
    date_filter = request.args.get('date', '').strip() or None
    dept_filter = request.args.get('dept', '').strip() or None
    search_term = request.args.get('search', '').strip() or None

    records = database.get_attendance_history(date_filter=date_filter, dept_filter=dept_filter, search_term=search_term)

    return render_template('history.html',
                           active_page='history',
                           records=records,
                           selected_date=date_filter,
                           selected_dept=dept_filter,
                           search_term=search_term)

@app.route('/history/export')
@login_required
def export_csv_route():
    date_filter = request.args.get('date', '').strip() or None
    dept_filter = request.args.get('dept', '').strip() or None
    search_term = request.args.get('search', '').strip() or None

    filename, csv_content = utils.export_attendance_to_csv(date_filter, dept_filter, search_term)

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-disposition": f"attachment; filename={filename}"}
    )

# 6. Student Directory Routes
@app.route('/students')
@login_required
def student_list():
    query = request.args.get('q', '').strip()
    sem_filter = request.args.get('sem', '').strip()
    dept_filter = request.args.get('dept', '').strip()

    all_students = database.get_all_students()
    filtered = []

    for s in all_students:
        if query:
            q_lower = query.lower()
            if not (q_lower in s.get('name', '').lower() or q_lower in s.get('id', '').lower() or q_lower in s.get('roll_number', '').lower()):
                continue
        if sem_filter and s.get('semester') != sem_filter:
            continue
        if dept_filter and s.get('department') != dept_filter:
            continue
        filtered.append(s)

    embeddings = database.get_all_embeddings()

    return render_template('students.html',
                           active_page='students',
                           students=filtered,
                           total_count=len(all_students),
                           query=query,
                           sem_filter=sem_filter,
                           dept_filter=dept_filter,
                           embeddings=embeddings)

@app.route('/students/photo/<student_id>')
@login_required
def get_student_photo(student_id):
    student_id = str(student_id).strip()
    
    # 1. Check disk dataset folder
    student_dir = os.path.join(config.DATASET_DIR, student_id)
    if os.path.exists(student_dir):
        files = [f for f in os.listdir(student_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if files:
            return send_file(os.path.join(student_dir, files[0]), mimetype='image/jpeg')

    # 2. Check SQLite DB StudentPhotos table
    db_photos = database.get_student_photos(student_id)
    if db_photos and len(db_photos) > 0:
        try:
            img = decode_base64_image(db_photos[0])
            if img is not None and img.size > 0:
                import cv2
                _, buf = cv2.imencode('.jpg', img)
                return Response(buf.tobytes(), mimetype='image/jpeg')
        except Exception:
            pass

    # 3. Fallback placeholder SVG avatar
    svg_avatar = f'''<svg xmlns="http://www.w3.org/2000/svg" width="120" height="120" viewBox="0 0 120 120">
      <rect width="100%" height="100%" fill="#4f46e5"/>
      <text x="50%" y="55%" font-size="44" font-weight="bold" fill="#ffffff" dominant-baseline="middle" text-anchor="middle">{student_id[:2].upper()}</text>
    </svg>'''
    return Response(svg_avatar, mimetype='image/svg+xml')

@app.route('/students/delete/<student_id>', methods=['POST'])
@admin_required
def delete_student_route(student_id):
    student = database.get_student(student_id)
    if student:
        database.delete_student(student_id)

        # Delete dataset directory
        import shutil
        student_dir = os.path.join(config.DATASET_DIR, str(student_id))
        if os.path.exists(student_dir):
            shutil.rmtree(student_dir, ignore_errors=True)

        flash(f"Student '{student['name']}' deleted successfully.", "success")
    else:
        flash("Student not found.", "error")

    return redirect(url_for('student_list'))

# 7. System Settings Routes
@app.route('/settings')
@login_required
def settings():
    threshold = database.get_setting('recognition_threshold', config.RECOGNITION_THRESHOLD)
    backup_list = backup_manager.get_backup_list()
    from hardware_manager import hardware_manager
    hw_status = hardware_manager.get_hardware_status()
    return render_template('settings.html', active_page='settings', threshold=threshold, backup_list=backup_list, hardware=hw_status)

@app.route('/admin/backup/create', methods=['GET', 'POST'])
@login_required
def trigger_permanent_backup():
    result = backup_manager.create_backup(notes="Manual Admin Trigger")
    if result['success']:
        flash(result['message'], "success")
    else:
        flash(f"Backup failed: {result['message']}", "error")
    return redirect(url_for('settings'))

@app.route('/admin/backup/restore', methods=['POST'])
@login_required
def restore_zip_backup():
    filename = request.form.get('backup_filename', '').strip()
    if not filename:
        flash("No backup filename specified.", "error")
        return redirect(url_for('settings'))

    result = backup_manager.restore_backup(filename)
    if result['success']:
        flash(result['message'], "success")
    else:
        flash(f"Restore failed: {result['message']}", "error")
    return redirect(url_for('settings'))

@app.route('/storage-status', methods=['GET'])
@admin_required
def storage_status():
    import psutil
    import backup_manager

    def get_dir_size_mb(path):
        if not os.path.exists(path):
            return 0.0
        total = 0
        for root, _, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                total += os.path.getsize(fp) if os.path.exists(fp) else 0
        return round(total / (1024 * 1024), 2)

    db_size = round(os.path.getsize(config.DB_PATH) / (1024 * 1024), 2) if os.path.exists(config.DB_PATH) else 0.0
    dataset_size = get_dir_size_mb(config.DATASET_DIR)
    embeddings_size = get_dir_size_mb(config.EMBEDDINGS_DIR)
    models_size = get_dir_size_mb(config.MODELS_DIR)
    backups_size = get_dir_size_mb(config.BACKUPS_DIR)

    student_folders = [d for d in os.listdir(config.DATASET_DIR) if os.path.isdir(os.path.join(config.DATASET_DIR, d))] if os.path.exists(config.DATASET_DIR) else []
    backups = backup_manager.get_backup_list()
    db_health = database.check_db_integrity()

    # Free disk space
    try:
        usage = shutil.disk_usage(config.DATA_DIR)
        free_space_gb = round(usage.free / (1024 * 1024 * 1024), 2)
        total_space_gb = round(usage.total / (1024 * 1024 * 1024), 2)
    except Exception:
        free_space_gb = 0.0
        total_space_gb = 0.0

    storage_info = {
        'data_root': config.DATA_DIR,
        'db_path': config.DB_PATH,
        'db_size_mb': db_size,
        'dataset_path': config.DATASET_DIR,
        'dataset_size_mb': dataset_size,
        'student_folder_count': len(student_folders),
        'embeddings_path': config.EMBEDDINGS_DIR,
        'embeddings_size_mb': embeddings_size,
        'models_path': config.MODELS_DIR,
        'models_size_mb': models_size,
        'backups_path': config.BACKUPS_DIR,
        'backups_size_mb': backups_size,
        'backup_count': len(backups),
        'last_backup': backups[0] if backups else None,
        'db_health': db_health,
        'free_space_gb': free_space_gb,
        'total_space_gb': total_space_gb
    }

    return render_template('storage_status.html', storage=storage_info, backups=backups)

@app.route('/settings/update', methods=['POST'])
@login_required
def update_settings():
    threshold = request.form.get('threshold', config.RECOGNITION_THRESHOLD)
    database.set_setting('recognition_threshold', threshold)

    hw_pref = request.form.get('ai_hardware_preference', '').strip()
    if hw_pref:
        from hardware_manager import hardware_manager
        if hardware_manager.set_preference(hw_pref):
            recognize.face_engine.reconfigure_hardware()
            flash(f"AI Hardware Preference updated to '{hw_pref}'. Reconfigured execution provider.", "info")

    flash(f"Recognition threshold updated to {threshold}.", "success")
    return redirect(url_for('settings'))

@app.route('/settings/retrain', methods=['POST'])
@login_required
def retrain_embeddings():
    results = train_all_students()
    flash(f"Re-trained face embeddings for all students.", "success")
    return redirect(url_for('settings'))

@app.route('/settings/change-password', methods=['POST'])
@login_required
def change_password():
    new_pass = request.form.get('new_password', '').strip()
    confirm_pass = request.form.get('confirm_password', '').strip()

    if new_pass != confirm_pass:
        flash("Passwords do not match.", "error")
        return redirect(url_for('settings'))

    database.change_admin_password(session['user'], new_pass)
    flash("Admin password updated successfully.", "success")
    return redirect(url_for('settings'))

# 8. Teacher Management Routes
@app.route('/teachers', methods=['GET', 'POST'])
@admin_required
def teacher_management():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        full_name = request.form.get('full_name', '').strip()
        department = request.form.get('department', '').strip()
        role = request.form.get('role', 'teacher').strip()

        if not username or not password or not full_name:
            flash("Username, Password, and Full Name are required.", "error")
        else:
            success, msg = database.add_user(username, password, full_name, department, role)
            if success:
                flash(f"User '{full_name}' ({username}) created successfully as {role.upper()}.", "success")
            else:
                flash(f"Failed to create user: {msg}", "error")
        return redirect(url_for('teacher_management'))

    users = database.get_all_users()
    return render_template('teachers.html', active_page='teachers', users=users)

@app.route('/teachers/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_teacher(user_id):
    database.delete_user(user_id)
    flash("User account deleted successfully.", "info")
    return redirect(url_for('teacher_management'))

# 9. Timetable & OCR Reader Routes
@app.route('/timetable', methods=['GET', 'POST'])
@login_required
def timetable_management():
    if request.method == 'POST':
        teacher_id = request.form.get('teacher_username', '').strip() or request.form.get('teacher_id', '').strip()
        if session.get('user_role') != 'admin':
            teacher_id = session.get('user')
        
        subject_name = request.form.get('subject_name', '').strip()
        subject_code = request.form.get('subject_code', '').strip()
        department = request.form.get('department', 'Computer Science').strip()
        semester = request.form.get('semester', '').strip()
        division = request.form.get('division', 'Division A').strip()
        day = request.form.get('day_of_week', '').strip() or request.form.get('day', '').strip()
        start_time = request.form.get('start_time', '').strip()
        end_time = request.form.get('end_time', '').strip()
        room_number = request.form.get('room_number', '').strip()
        lecture_type = request.form.get('lecture_type', 'Theory').strip()
        academic_year = request.form.get('academic_year', '2025-2026').strip()

        if not teacher_id or not subject_name or not day or not start_time or not end_time:
            flash("Please fill in all required timetable fields.", "error")
        else:
            success, msg, _ = database.add_teacher_timetable_entry(
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
                academic_year=academic_year,
                subject_code=subject_code
            )
            if success:
                flash(f"Timetable slot for '{subject_name}' ({semester} {division}) added successfully.", "success")
            else:
                flash(msg, "error")

        return redirect(url_for('timetable_management'))

    filter_teacher = request.args.get('teacher', '')
    filter_sem = request.args.get('sem', '')
    filter_div = request.args.get('div', '')

    if session.get('user_role') != 'admin':
        filter_teacher = session.get('user')

    timetable_entries = database.get_teacher_timetable(
        teacher_username=filter_teacher if filter_teacher else None,
        semester=filter_sem if filter_sem else None,
        division=filter_div if filter_div else None
    )
    all_teachers = database.get_all_teachers()
    all_subjects = database.get_all_subjects()

    return render_template('timetable.html', 
                           active_page='timetable', 
                           timetable_entries=timetable_entries, 
                           all_teachers=all_teachers,
                           all_subjects=all_subjects, 
                           filter_teacher=filter_teacher,
                           filter_sem=filter_sem,
                           filter_div=filter_div)

@app.route('/timetable/edit/<int:entry_id>', methods=['POST'])
@login_required
def edit_timetable_entry(entry_id):
    teacher_id = request.form.get('teacher_id', '').strip()
    if session.get('user_role') != 'admin':
        teacher_id = session.get('user')

    subject_name = request.form.get('subject_name', '').strip()
    subject_code = request.form.get('subject_code', '').strip()
    department = request.form.get('department', 'Computer Science').strip()
    semester = request.form.get('semester', '').strip()
    division = request.form.get('division', 'Division A').strip()
    day = request.form.get('day', '').strip()
    start_time = request.form.get('start_time', '').strip()
    end_time = request.form.get('end_time', '').strip()
    room_number = request.form.get('room_number', '').strip()
    lecture_type = request.form.get('lecture_type', 'Theory').strip()
    academic_year = request.form.get('academic_year', '2025-2026').strip()

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
        academic_year=academic_year,
        subject_code=subject_code
    )
    if success:
        flash(msg, "success")
    else:
        flash(msg, "error")

    return redirect(url_for('timetable_management'))

@app.route('/timetable/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete_timetable_entry(entry_id):
    database.delete_teacher_timetable_entry(entry_id)
    flash("Timetable entry removed successfully.", "info")
    return redirect(url_for('timetable_management'))

@app.route('/timetable/seed-100-teachers', methods=['POST'])
@admin_required
def seed_100_teachers():
    t_cnt, tt_cnt = database.seed_100_teachers_and_timetables()
    flash(f"Successfully generated/verified 100 teacher accounts (+{t_cnt} new) and created {tt_cnt} conflict-free timetable slots!", "success")
    return redirect(url_for('timetable_management'))

@app.route('/timetable/ocr_upload', methods=['POST'])
@login_required
def ocr_upload_timetable():
    if 'timetable_file' not in request.files:
        flash("No timetable file provided.", "error")
        return redirect(url_for('timetable_management'))

    file = request.files['timetable_file']
    if file.filename == '':
        flash("No file selected.", "error")
        return redirect(url_for('timetable_management'))

    temp_path = os.path.join(config.CAPTURED_DIR, f"temp_tt_{file.filename}")
    file.save(temp_path)

    teacher_default = session.get('user', 'teacher')
    dept_default = session.get('user_dept', 'Computer Science') or 'Computer Science'

    success, msg, entries = ocr_timetable.extract_timetable_from_file(temp_path, teacher_default, dept_default)
    
    if os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except Exception:
            pass

    if success:
        return render_template('ocr_preview.html', active_page='timetable', entries=entries, msg=msg)
    else:
        flash(msg, "error")
        return redirect(url_for('timetable_management'))

@app.route('/timetable/save_ocr', methods=['POST'])
@login_required
def save_ocr_timetable():
    ocr_json = request.form.get('ocr_entries_json', '[]')
    try:
        entries = json.loads(ocr_json)
        count = 0
        conflicts = 0
        for item in entries:
            t_id = item.get('teacher_id') or item.get('teacher_username') or session.get('user')
            success, msg, _ = database.add_teacher_timetable_entry(
                teacher_id=t_id,
                subject_name=item.get('subject_name', 'Subject'),
                department=item.get('department', 'Computer Science'),
                semester=item.get('semester', 'Semester 1'),
                division=item.get('division', 'Division A'),
                day=item.get('day_of_week') or item.get('day', 'Monday'),
                start_time=item.get('start_time', '10:00'),
                end_time=item.get('end_time', '11:00'),
                room_number=item.get('room_number', 'Room 101'),
                lecture_type=item.get('lecture_type', 'Theory'),
                academic_year=item.get('academic_year', '2025-2026'),
                subject_code=item.get('subject_code', '')
            )
            if success:
                count += 1
            else:
                conflicts += 1

        flash(f"Successfully saved {count} OCR timetable slots to database. ({conflicts} skipped due to conflict)", "success")
    except Exception as e:
        flash(f"Failed to save OCR entries: {e}", "error")

    return redirect(url_for('timetable_management'))

# 10. Analytics & Reports Routes
@app.route('/analytics')
@login_required
def analytics_dashboard():
    sem_filter = request.args.get('sem', '')
    div_filter = request.args.get('div', '')
    subject_filter = request.args.get('subject', '')

    analytics = analytics_reports.generate_analytics_data(sem=sem_filter or None, div=div_filter or None, subject=subject_filter or None)
    low_attendance_students = database.get_short_attendance_students(threshold=50.0)

    return render_template('analytics.html',
                           active_page='analytics',
                           analytics=analytics,
                           low_attendance_students=low_attendance_students,
                           sem_filter=sem_filter,
                           div_filter=div_filter,
                           subject_filter=subject_filter)

@app.route('/reports/download')
@login_required
def download_report():
    fmt = request.args.get('format', 'excel').lower()
    report_type = request.args.get('type', 'history')
    date_filter = request.args.get('date', '').strip() or None
    dept_filter = request.args.get('dept', '').strip() or None
    sem_filter = request.args.get('sem', '').strip() or None
    div_filter = request.args.get('div', '').strip() or None
    subject_filter = request.args.get('subject', '').strip() or None

    if report_type == 'short_attendance':
        low_students = database.get_short_attendance_students(threshold=50.0)
        records = []
        for s in low_students:
            records.append({
                'date': 'Overall',
                'time': f"{s['attendance_pct']}%",
                'student_id': s['id'],
                'roll_number': s['roll_number'],
                'name': s['name'],
                'department': s['department'],
                'semester': s['semester'],
                'division': s['division'],
                'status': 'Critical (<50%)'
            })
        title = "Short_Attendance_Report"
    else:
        records = database.get_attendance_history(date_filter=date_filter, dept_filter=dept_filter, sem_filter=sem_filter, div_filter=div_filter, subject_filter=subject_filter)
        title = "Attendance_Summary_Report"

    if fmt == 'pdf':
        pdf_bytes = analytics_reports.export_pdf_report(records, title=title)
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={"Content-disposition": f"attachment; filename={title}.pdf"}
        )
    else:
        excel_bytes = analytics_reports.export_excel_report(records, title=title)
        return Response(
            excel_bytes,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-disposition": f"attachment; filename={title}.xlsx"}
        )

# 11. Subjects Routes
@app.route('/subjects', methods=['GET', 'POST'])
@login_required
def subject_management():
    if request.method == 'POST':
        code = request.form.get('code', '').strip()
        name = request.form.get('name', '').strip()
        department = request.form.get('department', '').strip()
        semester = request.form.get('semester', '').strip()

        if not name or not department or not semester:
            flash("Subject Name, Department, and Semester are required.", "error")
        else:
            success, msg = database.add_subject(code, name, department, semester)
            if success:
                flash(f"Subject '{name}' added successfully.", "success")
            else:
                flash(f"Failed to add subject: {msg}", "error")

        return redirect(url_for('subject_management'))

    subjects = database.get_all_subjects()
    return render_template('subjects.html', active_page='subjects', subjects=subjects)

@app.route('/subjects/delete/<int:subject_id>', methods=['POST'])
@login_required
def delete_subject(subject_id):
    database.delete_subject(subject_id)
    flash("Subject deleted successfully.", "info")
    return redirect(url_for('subject_management'))

# 12. Notifications Routes
@app.route('/notifications/read/<int:notif_id>', methods=['POST'])
@login_required
def read_notification(notif_id):
    database.mark_notification_read(notif_id)
    return jsonify({'status': 'ok'})

# 13. Live Video Stream Route (MJPEG)
@app.route('/video_feed')
@login_required
def video_feed():
    return Response(camera_instance.generate_mjpeg_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# 14. Database Backup & Cloud Restore Routes
@app.route('/settings/export_db', methods=['GET'])
@login_required
def export_database():
    try:
        data = database.export_database_json()
        json_str = json.dumps(data, indent=2)
        filename = f"smart_attendance_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        return Response(
            json_str,
            mimetype="application/json",
            headers={"Content-disposition": f"attachment; filename={filename}"}
        )
    except Exception as e:
        flash(f"Export failed: {e}", "error")
        return redirect(url_for('system_settings'))

@app.route('/settings/import_db', methods=['POST'])
@login_required
def import_database():
    if 'backup_file' not in request.files:
        flash("No backup file selected.", "error")
        return redirect(url_for('system_settings'))

    file = request.files['backup_file']
    if file.filename == '':
        flash("No file selected.", "error")
        return redirect(url_for('system_settings'))

    try:
        content = file.read().decode('utf-8', errors='ignore')
        data = json.loads(content)
        success, msg = database.import_database_json(data)
        if success:
            database.sync_backup_seed()
            flash(msg, "success")
        else:
            flash(msg, "error")
    except Exception as e:
        flash(f"Import failed: {e}", "error")

    return redirect(url_for('system_settings'))

# -------------------------------------------------------------
# AI Face Classifier Training Pipeline Routes & Endpoints
# -------------------------------------------------------------
@app.route('/training')
@login_required
def training_dashboard():
    meta = model_trainer.load_training_metadata()
    return render_template('training.html', active_page='training', meta=meta)

@app.route('/api/training/train', methods=['POST'])
@login_required
def api_trigger_training():
    started, msg = model_trainer.trainer.start_training_async()
    return jsonify({'success': started, 'message': msg})

@app.route('/api/training/status')
@login_required
def api_training_status():
    status = model_trainer.trainer.get_status()
    return jsonify(status)

@app.route('/api/training/logs')
@login_required
def api_training_logs():
    logs = model_trainer.trainer.get_logs()
    return jsonify({'logs': logs})

@app.route('/api/training/download')
@login_required
def download_model():
    clf_path = model_trainer.CLASSIFIER_PATH
    if not os.path.exists(clf_path) and os.path.exists(os.path.join(config.REPO_MODELS_DIR, 'face_classifier.pkl')):
        clf_path = os.path.join(config.REPO_MODELS_DIR, 'face_classifier.pkl')

    if os.path.exists(clf_path):
        return send_file(clf_path, as_attachment=True, download_name='face_classifier.pkl')

    # If no model file exists yet, check if student photos exist to trigger training
    students = database.get_all_students()
    if not students:
        flash("No trained face classifier model found. Please register a student with a passport photo first.", "warning")
    else:
        started, msg = model_trainer.trainer.start_training_async()
        flash("No trained face classifier model file found on disk. Automated background model training has been initiated. Please wait a moment and click Download again.", "info")

    return redirect(url_for('training_dashboard'))

@app.route('/api/training/delete', methods=['POST'])
@login_required
def api_delete_model():
    success = model_trainer.delete_model_artifacts()
    return jsonify({'success': success, 'message': 'Trained model artifacts reset successfully.'})

# -------------------------------------------------------------
# Standardized Production REST API Endpoints & Health Diagnostics
# -------------------------------------------------------------
SERVER_START_TIME = time.time()

@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check_api():
    """Live Server, Database, Memory, CPU, and AI Health Diagnostic Endpoint."""
    import psutil
    uptime = round(time.time() - SERVER_START_TIME, 2)
    db_health = database.check_db_integrity()
    trainer_status = model_trainer.trainer.get_status()

    return jsonify({
        'status': 'healthy',
        'server': 'AI Smart Attendance Local Production Server',
        'uptime_seconds': uptime,
        'database': db_health,
        'ai_models': {
            'detector_loaded': recognize.face_engine.yunet is not None,
            'recognizer_loaded': recognize.face_engine.sface is not None,
            'classifier_cached': getattr(recognize.face_engine, '_cached_classifier', None) is not None
        },
        'training': trainer_status,
        'system_resources': {
            'cpu_usage_percent': psutil.cpu_percent(interval=None),
            'ram_usage_percent': psutil.virtual_memory().percent,
            'ram_available_mb': round(psutil.virtual_memory().available / (1024 * 1024), 2)
        },
        'permanent_storage': config.DATA_DIR,
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route('/api/hardware-info', methods=['GET'])
@admin_required
def hardware_info_api():
    """Localhost-only Admin Diagnostic Endpoint for hardware metrics."""
    client_ip = request.remote_addr
    if client_ip not in ['127.0.0.1', '::1', 'localhost']:
        return jsonify({'error': 'Access denied. Hardware diagnostics restricted to localhost administrators.'}), 403

    from hardware_manager import hardware_manager
    return jsonify(hardware_manager.get_hardware_status())

@app.route('/api/server-info', methods=['GET'])
def server_info_api():
    """Returns permanent storage directories and system metrics."""
    database.init_db()
    students = database.get_all_students()
    all_embs = database.get_all_embeddings()
    return jsonify({
        'server_name': 'Smart Attendance Production Server',
        'data_root': config.DATA_DIR,
        'database_path': config.DB_PATH,
        'total_students': len(students),
        'total_embeddings': len(all_embs),
        'directories': {
            'dataset': config.DATASET_DIR,
            'embeddings': config.EMBEDDINGS_DIR,
            'models': config.MODELS_DIR,
            'backups': config.BACKUPS_DIR,
            'logs': config.LOGS_DIR
        }
    })

@app.route('/api/model-info', methods=['GET'])
def model_info_api():
    """Returns trained classifier metadata."""
    meta = model_trainer.load_training_metadata()
    return jsonify(meta or {'status': 'No model trained yet'})

@app.route('/api/register', methods=['POST'])
def api_register_student():
    """REST API endpoint to register a new student."""
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

@app.route('/api/train', methods=['POST'])
def api_train_model():
    """REST API endpoint to trigger background classifier training."""
    started, msg = model_trainer.trainer.start_training_async()
    return jsonify({'success': started, 'message': msg})

@app.route('/api/recognize', methods=['POST'])
def api_recognize_faces():
    """REST API endpoint for real-time face recognition."""
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

@app.route('/api/backup', methods=['POST'])
def api_trigger_backup():
    """REST API endpoint to trigger system backup."""
    notes = request.json.get('notes', 'REST API Backup') if request.is_json else 'REST API Backup'
    res = backup_manager.create_backup(notes=notes)
    return jsonify(res)

@app.route('/api/restore', methods=['POST'])
def api_trigger_restore():
    """REST API endpoint to restore system backup."""
    data = request.get_json(force=True, silent=True) or request.form
    backup_filename = data.get('backup_filename', '').strip()
    if not backup_filename:
        return jsonify({'success': False, 'message': 'backup_filename parameter is required.'}), 400

    res = backup_manager.restore_backup(backup_filename)
    return jsonify(res)

if __name__ == '__main__':
    print("Starting AI Smart Attendance System on http://127.0.0.1:5000 ...")
    app.run(host='0.0.0.0', port=5000, debug=True)

