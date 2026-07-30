import os
import json
import io
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, session, Response, send_file
import config
import database
import register
import attendance
import utils
from camera import camera_instance, decode_base64_image
from train import train_all_students

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Set Max Payload Limit to 100 MB to prevent "413 Request Entity Too Large" errors
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024

# Initialize database on app startup
database.init_db()

@app.errorhandler(413)
def request_entity_too_large(error):
    flash("Uploaded file or photo data was too large. Please select a smaller photo or retry.", "error")
    return redirect(request.referrer or url_for('dashboard'))

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Please login to access the system.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash("Please login to access the system.", "warning")
            return redirect(url_for('login'))
        if session.get('user_role') != 'admin':
            flash("Admin privilege required for this action.", "error")
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

# 1. Login & Authentication Routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user' in session:
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
            flash(f"Welcome back, {session['user_fullname']}!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid username or password.", "error")

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

# 2. Dashboard Route
@app.route('/')
@login_required
def dashboard():
    stats = database.get_dashboard_stats()
    today_attendance = database.get_attendance_today()
    all_embeddings = database.get_all_embeddings()
    threshold = database.get_setting('recognition_threshold', config.RECOGNITION_THRESHOLD)

    return render_template('index.html',
                           active_page='dashboard',
                           stats=stats,
                           today_attendance=today_attendance,
                           embedded_count=len(all_embeddings),
                           threshold=threshold)

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
        samples_json = request.form.get('samples_json', '')

        sample_images_b64 = []
        if samples_json:
            try:
                sample_images_b64 = json.loads(samples_json)
            except Exception as e:
                print("Error parsing sample images JSON:", e)

        success, msg = register.register_new_student(
            student_id, roll_number, name, department, semester, sample_images_b64
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
    return render_template('classroom.html', active_page='classroom', result_summary=None)

@app.route('/classroom/upload', methods=['POST'])
@login_required
def classroom_upload():
    if 'classroom_photo' not in request.files:
        flash("No file selected.", "error")
        return redirect(url_for('classroom_attendance'))

    file = request.files['classroom_photo']
    if file.filename == '':
        flash("No file selected.", "error")
        return redirect(url_for('classroom_attendance'))

    try:
        import numpy as np
        import cv2
        file_bytes = np.frombuffer(file.read(), np.uint8)
        img_bgr = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)

        threshold_val = float(database.get_setting('recognition_threshold', config.RECOGNITION_THRESHOLD))
        success, msg, summary = attendance.process_classroom_image(img_bgr, custom_threshold=threshold_val)

        if success:
            flash(msg, "success")
            return render_template('classroom.html', active_page='classroom', result_summary=summary)
        else:
            flash(msg, "error")

    except Exception as e:
        flash(f"Error processing image: {e}", "error")

    return redirect(url_for('classroom_attendance'))

@app.route('/classroom/snap', methods=['POST'])
@login_required
def classroom_snap():
    snap_b64 = request.form.get('snap_b64', '')
    if not snap_b64:
        flash("No camera snapshot received.", "error")
        return redirect(url_for('classroom_attendance'))

    try:
        img_bgr = decode_base64_image(snap_b64)
        threshold_val = float(database.get_setting('recognition_threshold', config.RECOGNITION_THRESHOLD))
        success, msg, summary = attendance.process_classroom_image(img_bgr, custom_threshold=threshold_val)

        if success:
            flash(msg, "success")
            return render_template('classroom.html', active_page='classroom', result_summary=summary)
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
    students = database.get_all_students()
    return render_template('students.html', active_page='students', students=students)

@app.route('/students/delete/<student_id>', methods=['POST'])
@login_required
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
    return render_template('settings.html', active_page='settings', threshold=threshold)

@app.route('/settings/update', methods=['POST'])
@login_required
def update_settings():
    threshold = request.form.get('threshold', config.RECOGNITION_THRESHOLD)
    database.set_setting('recognition_threshold', threshold)
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

# 9. Timetable Routes
@app.route('/timetable', methods=['GET', 'POST'])
@login_required
def timetable_management():
    if request.method == 'POST':
        teacher_username = request.form.get('teacher_username', '').strip()
        if session.get('user_role') != 'admin':
            teacher_username = session.get('user')
        
        subject_name = request.form.get('subject_name', '').strip()
        department = request.form.get('department', '').strip()
        semester = request.form.get('semester', '').strip()
        day_of_week = request.form.get('day_of_week', '').strip()
        start_time = request.form.get('start_time', '').strip()
        end_time = request.form.get('end_time', '').strip()
        room_number = request.form.get('room_number', '').strip()

        if not teacher_username or not subject_name or not day_of_week or not start_time or not end_time:
            flash("Please fill in all required timetable fields.", "error")
        else:
            database.add_timetable_entry(teacher_username, subject_name, department, semester, day_of_week, start_time, end_time, room_number)
            flash(f"Timetable slot for '{subject_name}' added successfully.", "success")
        return redirect(url_for('timetable_management'))

    filter_teacher = request.args.get('teacher', '')
    if session.get('user_role') != 'admin':
        filter_teacher = session.get('user')

    timetable_entries = database.get_timetable(teacher_username=filter_teacher if filter_teacher else None)
    all_teachers = database.get_all_users()

    return render_template('timetable.html', 
                           active_page='timetable', 
                           timetable_entries=timetable_entries, 
                           all_teachers=all_teachers, 
                           filter_teacher=filter_teacher)

@app.route('/timetable/delete/<int:entry_id>', methods=['POST'])
@login_required
def delete_timetable_entry(entry_id):
    database.delete_timetable_entry(entry_id)
    flash("Timetable entry removed.", "info")
    return redirect(url_for('timetable_management'))

# 10. Live Video Stream Route (MJPEG)
@app.route('/video_feed')
@login_required
def video_feed():
    return Response(camera_instance.generate_mjpeg_stream(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == '__main__':
    print("Starting AI Smart Attendance System on http://127.0.0.1:5000 ...")
    app.run(host='0.0.0.0', port=5000, debug=True)
