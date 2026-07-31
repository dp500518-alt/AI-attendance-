import sqlite3
import json
import os
import datetime
import numpy as np
from werkzeug.security import generate_password_hash, check_password_hash
import config

def get_connection():
    os.makedirs(config.DB_DIR, exist_ok=True)
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # Students table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Students (
        id TEXT PRIMARY KEY,
        roll_number TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        semester TEXT NOT NULL,
        division TEXT NOT NULL DEFAULT 'Division A',
        email TEXT,
        phone TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # Embeddings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Embeddings (
        student_id TEXT PRIMARY KEY,
        embedding TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(student_id) REFERENCES Students(id) ON DELETE CASCADE
    );
    """)

    # Attendance table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        timetable_id INTEGER,
        subject_name TEXT,
        semester TEXT,
        division TEXT,
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Present',
        UNIQUE(student_id, date, timetable_id),
        FOREIGN KEY(student_id) REFERENCES Students(id) ON DELETE CASCADE
    );
    """)

    # Admin, Teacher, Student Users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        department TEXT,
        role TEXT NOT NULL DEFAULT 'teacher',
        created_at TEXT NOT NULL
    );
    """)

    # Check and add missing columns to Users if upgrading existing DB
    cursor.execute("PRAGMA table_info(Users);")
    user_columns = [col['name'] for col in cursor.fetchall()]
    if 'full_name' not in user_columns:
        cursor.execute("ALTER TABLE Users ADD COLUMN full_name TEXT;")
    if 'department' not in user_columns:
        cursor.execute("ALTER TABLE Users ADD COLUMN department TEXT;")
    if 'role' not in user_columns:
        cursor.execute("ALTER TABLE Users ADD COLUMN role TEXT NOT NULL DEFAULT 'teacher';")
    if 'email' not in user_columns:
        cursor.execute("ALTER TABLE Users ADD COLUMN email TEXT;")

    # Check and add missing columns to Students
    cursor.execute("PRAGMA table_info(Students);")
    student_cols = [col['name'] for col in cursor.fetchall()]
    if 'division' not in student_cols:
        cursor.execute("ALTER TABLE Students ADD COLUMN division TEXT NOT NULL DEFAULT 'Division A';")
    if 'email' not in student_cols:
        cursor.execute("ALTER TABLE Students ADD COLUMN email TEXT;")
    if 'phone' not in student_cols:
        cursor.execute("ALTER TABLE Students ADD COLUMN phone TEXT;")

    # Timetable table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Timetable (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_username TEXT NOT NULL,
        subject_name TEXT NOT NULL,
        department TEXT NOT NULL,
        semester TEXT NOT NULL,
        division TEXT NOT NULL DEFAULT 'Division A',
        day_of_week TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        room_number TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(teacher_username) REFERENCES Users(username) ON DELETE CASCADE
    );
    """)

    cursor.execute("PRAGMA table_info(Timetable);")
    tt_cols = [col['name'] for col in cursor.fetchall()]
    if 'division' not in tt_cols:
        cursor.execute("ALTER TABLE Timetable ADD COLUMN division TEXT NOT NULL DEFAULT 'Division A';")

    # Check and add missing columns to Attendance
    cursor.execute("PRAGMA table_info(Attendance);")
    att_cols = [col['name'] for col in cursor.fetchall()]
    if 'timetable_id' not in att_cols:
        cursor.execute("ALTER TABLE Attendance ADD COLUMN timetable_id INTEGER;")
    if 'subject_name' not in att_cols:
        cursor.execute("ALTER TABLE Attendance ADD COLUMN subject_name TEXT;")
    if 'semester' not in att_cols:
        cursor.execute("ALTER TABLE Attendance ADD COLUMN semester TEXT;")
    if 'division' not in att_cols:
        cursor.execute("ALTER TABLE Attendance ADD COLUMN division TEXT;")

    # Notifications Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Notifications (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        target_user TEXT NOT NULL,
        title TEXT NOT NULL,
        message TEXT NOT NULL,
        channel TEXT NOT NULL DEFAULT 'website',
        is_read INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL
    );
    """)

    # LoginHistory Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS LoginHistory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL,
        role TEXT NOT NULL,
        full_name TEXT,
        login_date TEXT NOT NULL,
        login_time TEXT NOT NULL,
        ip_address TEXT,
        country TEXT,
        state TEXT,
        city TEXT,
        latitude REAL,
        longitude REAL,
        timezone TEXT,
        browser TEXT,
        os TEXT,
        device_type TEXT,
        user_agent TEXT,
        is_new_device INTEGER DEFAULT 0,
        status TEXT DEFAULT 'Success',
        session_id TEXT,
        created_at TEXT NOT NULL
    );
    """)

    # Subjects Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Subjects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        code TEXT,
        name TEXT NOT NULL,
        department TEXT NOT NULL,
        semester TEXT NOT NULL
    );
    """)

    # System Settings table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    # Insert default admin user if not exists
    cursor.execute("SELECT id FROM Users WHERE username = ?", (config.DEFAULT_ADMIN_USER,))
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if not cursor.fetchone():
        pass_hash = generate_password_hash(config.DEFAULT_ADMIN_PASS)
        cursor.execute("""
        INSERT INTO Users (username, password_hash, full_name, department, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (config.DEFAULT_ADMIN_USER, pass_hash, 'Super Administrator', 'Management', 'admin', now_str))
    else:
        cursor.execute("UPDATE Users SET role = 'admin' WHERE username = ?", (config.DEFAULT_ADMIN_USER,))

    # Insert default teacher user if not exists
    cursor.execute("SELECT id FROM Users WHERE username = ?", ('teacher',))
    if not cursor.fetchone():
        teacher_pass_hash = generate_password_hash('teacher123')
        cursor.execute("""
        INSERT INTO Users (username, password_hash, full_name, department, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, ('teacher', teacher_pass_hash, 'Faculty Teacher', 'Computer Science', 'teacher', now_str))

    # Default settings
    cursor.execute("INSERT OR IGNORE INTO Settings (key, value) VALUES ('recognition_threshold', ?)",
                   (str(config.RECOGNITION_THRESHOLD),))

    conn.commit()
    conn.close()

# User Security Functions
def verify_user(username, password):
    if not username or not password:
        return None
    username_clean = username.strip()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Users WHERE LOWER(username) = LOWER(?)", (username_clean,))
    user = cursor.fetchone()
    conn.close()
    if user and check_password_hash(user['password_hash'], password):
        return dict(user)
    return None

def change_admin_password(username, new_password):
    conn = get_connection()
    cursor = conn.cursor()
    pass_hash = generate_password_hash(new_password)
    cursor.execute("UPDATE Users SET password_hash = ? WHERE username = ?", (pass_hash, username))
    conn.commit()
    conn.close()

# Student Functions
def add_student(student_id, roll_number, name, department, semester, division='Division A', email='', phone=''):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO Students (id, roll_number, name, department, semester, division, email, phone, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (student_id.strip(), roll_number.strip(), name.strip(), department.strip(), semester.strip(), division.strip(), email.strip(), phone.strip(), now_str))
    conn.commit()
    conn.close()

def get_all_students():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Students ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_students_by_sem_div(semester=None, division=None, department=None):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM Students WHERE 1=1"
    params = []
    if semester:
        query += " AND semester = ?"
        params.append(semester)
    if division:
        query += " AND division = ?"
        params.append(division)
    if department:
        query += " AND department = ?"
        params.append(department)
    query += " ORDER BY roll_number ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_student(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Students WHERE id = ?", (student_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_student_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Students WHERE id = ? OR roll_number = ? OR name LIKE ?", (username, username, f"%{username}%"))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_student(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Students WHERE id = ?", (student_id,))
    conn.commit()
    conn.close()

# Embeddings Functions
def save_embedding(student_id, embedding_vector):
    if isinstance(embedding_vector, np.ndarray):
        emb_list = embedding_vector.tolist()
    else:
        emb_list = list(embedding_vector)

    emb_json = json.dumps(emb_list)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO Embeddings (student_id, embedding, updated_at)
    VALUES (?, ?, ?)
    ON CONFLICT(student_id) DO UPDATE SET
        embedding = excluded.embedding,
        updated_at = excluded.updated_at
    """, (student_id, emb_json, now_str))
    conn.commit()
    conn.close()

def get_all_embeddings():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT student_id, embedding FROM Embeddings")
    rows = cursor.fetchall()
    conn.close()

    embeddings_map = {}
    for row in rows:
        student_id = row['student_id']
        emb_vec = np.array(json.loads(row['embedding']), dtype=np.float32)
        embeddings_map[student_id] = emb_vec
    return embeddings_map

# Attendance Functions
def mark_attendance(student_id, status='Present', date_str=None, time_str=None, timetable_id=None, subject_name=None, semester=None, division=None):
    now = datetime.datetime.now()
    if not date_str:
        date_str = now.strftime("%Y-%m-%d")
    if not time_str:
        time_str = now.strftime("%H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO Attendance (student_id, date, time, status, timetable_id, subject_name, semester, division)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(student_id, date, timetable_id) DO NOTHING
        """, (student_id, date_str, time_str, status, timetable_id, subject_name, semester, division))
        conn.commit()
        inserted = cursor.rowcount > 0
    except sqlite3.Error as e:
        print("Mark attendance error:", e)
        inserted = False
    finally:
        conn.close()

    return inserted

def get_attendance_today():
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    return get_attendance_by_date(today)

def get_attendance_by_date(date_str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT a.id, a.student_id, s.name, s.roll_number, s.department, 
           COALESCE(a.semester, s.semester) as semester, 
           COALESCE(a.division, s.division) as division,
           COALESCE(a.subject_name, 'General') as subject_name,
           a.date, a.time, a.status
    FROM Attendance a
    JOIN Students s ON a.student_id = s.id
    WHERE a.date = ?
    ORDER BY a.time DESC
    """, (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_attendance_history(date_filter=None, dept_filter=None, sem_filter=None, div_filter=None, subject_filter=None, search_term=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT a.id, a.student_id, s.name, s.roll_number, s.department, 
           COALESCE(a.semester, s.semester) as semester, 
           COALESCE(a.division, s.division) as division,
           COALESCE(a.subject_name, 'General') as subject_name,
           a.date, a.time, a.status
    FROM Attendance a
    JOIN Students s ON a.student_id = s.id
    WHERE 1=1
    """
    params = []

    if date_filter:
        query += " AND a.date = ?"
        params.append(date_filter)
    if dept_filter:
        query += " AND s.department = ?"
        params.append(dept_filter)
    if sem_filter:
        query += " AND (a.semester = ? OR s.semester = ?)"
        params.extend([sem_filter, sem_filter])
    if div_filter:
        query += " AND (a.division = ? OR s.division = ?)"
        params.extend([div_filter, div_filter])
    if subject_filter:
        query += " AND a.subject_name LIKE ?"
        params.append(f"%{subject_filter}%")
    if search_term:
        query += " AND (s.name LIKE ? OR s.roll_number LIKE ? OR a.student_id LIKE ?)"
        term = f"%{search_term}%"
        params.extend([term, term, term])

    query += " ORDER BY a.date DESC, a.time DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_student_attendance_summary(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) as total FROM Attendance WHERE student_id = ?", (student_id,))
    total_attended = cursor.fetchone()['total']

    cursor.execute("""
    SELECT subject_name, COUNT(*) as count 
    FROM Attendance 
    WHERE student_id = ? 
    GROUP BY subject_name
    """, (student_id,))
    by_subject = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return {
        'total_attended': total_attended,
        'by_subject': by_subject
    }

def get_short_attendance_students(threshold=50.0):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, roll_number, name, department, semester, division, email, phone FROM Students")
    students = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT DISTINCT date FROM Attendance")
    total_conducted = len(cursor.fetchall()) or 1

    low_attendance = []
    for s in students:
        cursor.execute("SELECT COUNT(DISTINCT date) as attended FROM Attendance WHERE student_id = ?", (s['id'],))
        attended = cursor.fetchone()['attended']
        pct = round((attended / total_conducted) * 100, 1)

        status_flag = "Good"
        if pct < 50.0:
            status_flag = "Critical"
        elif pct <= 75.0:
            status_flag = "Warning"

        s['attended_days'] = attended
        s['total_days'] = total_conducted
        s['attendance_pct'] = pct
        s['status_flag'] = status_flag

        if pct < threshold:
            low_attendance.append(s)

    conn.close()
    return low_attendance

def get_dashboard_stats():
    conn = get_connection()
    cursor = conn.cursor()

    today = datetime.datetime.now().strftime("%Y-%m-%d")

    cursor.execute("SELECT COUNT(*) as total FROM Students")
    total_students = cursor.fetchone()['total']

    cursor.execute("SELECT COUNT(DISTINCT student_id) as present FROM Attendance WHERE date = ?", (today,))
    present_today = cursor.fetchone()['present']

    absent_today = max(0, total_students - present_today)
    attendance_pct = round((present_today / total_students * 100), 1) if total_students > 0 else 0.0

    low_students = get_short_attendance_students(threshold=50.0)

    conn.close()
    return {
        'total_students': total_students,
        'present_today': present_today,
        'absent_today': absent_today,
        'attendance_pct': attendance_pct,
        'low_attendance_count': len(low_students),
        'today_date': today
    }

# Notifications Functions
def create_notification(target_user, title, message, channel='website'):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO Notifications (target_user, title, message, channel, is_read, created_at)
    VALUES (?, ?, ?, ?, 0, ?)
    """, (target_user.strip(), title.strip(), message.strip(), channel.strip(), now_str))
    conn.commit()
    conn.close()

def get_notifications(target_user=None, unread_only=False):
    conn = get_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM Notifications WHERE 1=1"
    params = []

    if target_user:
        query += " AND (target_user = ? OR target_user = 'all')"
        params.append(target_user)
    if unread_only:
        query += " AND is_read = 0"

    query += " ORDER BY created_at DESC LIMIT 50"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def mark_notification_read(notif_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Notifications SET is_read = 1 WHERE id = ?", (notif_id,))
    conn.commit()
    conn.close()

# Subjects Functions
def get_all_subjects():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Subjects ORDER BY department ASC, semester ASC, name ASC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_subject(code, name, department, semester):
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO Subjects (code, name, department, semester)
        VALUES (?, ?, ?, ?)
        """, (code.strip(), name.strip(), department.strip(), semester.strip()))
        conn.commit()
        conn.close()
        return True, "Subject added successfully."
    except Exception as e:
        conn.close()
        return False, str(e)

def delete_subject(subject_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Subjects WHERE id = ?", (subject_id,))
    conn.commit()
    conn.close()

# System Settings Functions
def get_setting(key, default_val=None):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM Settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default_val

def set_setting(key, value):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO Settings (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value
    """, (key, str(value)))
    conn.commit()
    conn.close()

# Teacher User Management Functions
def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, full_name, department, role, created_at FROM Users ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_teachers():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, full_name, department, role, created_at FROM Users WHERE role = 'teacher' ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_user(username, password, full_name='', department='', role='teacher'):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pass_hash = generate_password_hash(password)
    try:
        cursor.execute("""
        INSERT INTO Users (username, password_hash, full_name, department, role, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (username.strip(), pass_hash, full_name.strip(), department.strip(), role, now_str))
        conn.commit()
        conn.close()
        return True, "User registered successfully."
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Username already exists."
    except Exception as e:
        conn.close()
        return False, str(e)

def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Users WHERE id = ? AND username != ?", (user_id, config.DEFAULT_ADMIN_USER))
    conn.commit()
    conn.close()

# Timetable & Intelligent Detection Functions
def get_timetable(teacher_username=None, semester=None, division=None, day_of_week=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT t.*, u.full_name as teacher_name 
    FROM Timetable t
    LEFT JOIN Users u ON t.teacher_username = u.username
    WHERE 1=1
    """
    params = []

    if teacher_username:
        query += " AND t.teacher_username = ?"
        params.append(teacher_username)
    if semester:
        query += " AND t.semester = ?"
        params.append(semester)
    if division:
        query += " AND t.division = ?"
        params.append(division)
    if day_of_week:
        query += " AND t.day_of_week = ?"
        params.append(day_of_week)

    query += """
    ORDER BY CASE t.day_of_week
        WHEN 'Monday' THEN 1
        WHEN 'Tuesday' THEN 2
        WHEN 'Wednesday' THEN 3
        WHEN 'Thursday' THEN 4
        WHEN 'Friday' THEN 5
        WHEN 'Saturday' THEN 6
        WHEN 'Sunday' THEN 7
        ELSE 8
    END, t.start_time ASC
    """

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_active_timetable_slot(teacher_username=None, day_of_week=None, time_str=None, slot_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    # 1. If explicit slot_id provided (e.g. manual simulation or dropdown override)
    if slot_id:
        cursor.execute("""
        SELECT t.*, u.full_name as teacher_name 
        FROM Timetable t
        LEFT JOIN Users u ON t.teacher_username = u.username
        WHERE t.id = ?
        """, (slot_id,))
        row = cursor.fetchone()
        conn.close()
        if row:
            return dict(row)

    now = datetime.datetime.now()
    if not day_of_week:
        day_of_week = now.strftime("%A")
    if not time_str:
        time_str = now.strftime("%H:%M")

    # 2. Try exact day & time match
    if teacher_username:
        cursor.execute("""
        SELECT t.*, u.full_name as teacher_name 
        FROM Timetable t
        LEFT JOIN Users u ON t.teacher_username = u.username
        WHERE t.teacher_username = ? AND t.day_of_week = ? AND t.start_time <= ? AND t.end_time >= ?
        ORDER BY t.start_time ASC
        LIMIT 1
        """, (teacher_username, day_of_week, time_str, time_str))
        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)

    cursor.execute("""
    SELECT t.*, u.full_name as teacher_name 
    FROM Timetable t
    LEFT JOIN Users u ON t.teacher_username = u.username
    WHERE t.day_of_week = ? AND t.start_time <= ? AND t.end_time >= ?
    ORDER BY t.start_time ASC
    LIMIT 1
    """, (day_of_week, time_str, time_str))

    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)

    # 3. Fallback: match any slot for today or latest added slot so zero-input auto-detection always works
    if teacher_username:
        cursor.execute("""
        SELECT t.*, u.full_name as teacher_name 
        FROM Timetable t
        LEFT JOIN Users u ON t.teacher_username = u.username
        WHERE t.teacher_username = ? AND t.day_of_week = ?
        ORDER BY t.start_time ASC
        LIMIT 1
        """, (teacher_username, day_of_week))
        row = cursor.fetchone()
        if row:
            conn.close()
            return dict(row)

    cursor.execute("""
    SELECT t.*, u.full_name as teacher_name 
    FROM Timetable t
    LEFT JOIN Users u ON t.teacher_username = u.username
    ORDER BY t.id DESC
    LIMIT 1
    """)
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def add_timetable_entry(teacher_username, subject_name, department, semester, day_of_week, start_time, end_time, room_number='', division='Division A'):
    conn = get_connection()
    cursor = conn.cursor()

    # Check if teacher_username exists in Users
    cursor.execute("SELECT username FROM Users WHERE username = ?", (teacher_username.strip(),))
    user_row = cursor.fetchone()
    valid_teacher = user_row[0] if user_row else None

    if not valid_teacher:
        cursor.execute("SELECT username FROM Users LIMIT 1")
        fallback_row = cursor.fetchone()
        valid_teacher = fallback_row[0] if fallback_row else 'teacher'

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO Timetable (teacher_username, subject_name, department, semester, division, day_of_week, start_time, end_time, room_number, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (valid_teacher, subject_name.strip(), department.strip(), semester.strip(), division.strip(), day_of_week.strip(), start_time.strip(), end_time.strip(), room_number.strip(), now_str))
    conn.commit()
    conn.close()

def delete_timetable_entry(entry_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Timetable WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()

# --- LOGIN HISTORY SECURITY HELPERS ---

def add_login_history(username, role, full_name, login_date, login_time, ip_address, country, state, city, latitude, longitude, timezone, browser, os_name, device_type, user_agent, is_new_device, status, session_id, created_at):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO LoginHistory (
        username, role, full_name, login_date, login_time, ip_address,
        country, state, city, latitude, longitude, timezone,
        browser, os, device_type, user_agent, is_new_device, status, session_id, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        username, role, full_name, login_date, login_time, ip_address,
        country, state, city, latitude, longitude, timezone,
        browser, os_name, device_type, user_agent, 1 if is_new_device else 0, status, session_id, created_at
    ))
    conn.commit()
    inserted_id = cursor.lastrowid
    conn.close()
    return inserted_id

def get_user_prior_success_logins(username):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT * FROM LoginHistory 
    WHERE username = ? AND status = 'Success'
    ORDER BY id DESC
    """, (username,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_login_history(username=None, role=None, date_filter=None, search_term=None, new_device_only=False):
    conn = get_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM LoginHistory WHERE 1=1"
    params = []

    if username:
        query += " AND username = ?"
        params.append(username)

    if role:
        query += " AND role = ?"
        params.append(role)

    if date_filter:
        query += " AND login_date = ?"
        params.append(date_filter)

    if new_device_only:
        query += " AND is_new_device = 1"

    if search_term:
        term = f"%{search_term.strip()}%"
        query += " AND (username LIKE ? OR full_name LIKE ? OR ip_address LIKE ? OR city LIKE ? OR browser LIKE ? OR os LIKE ?)"
        params.extend([term, term, term, term, term, term])

    query += " ORDER BY id DESC LIMIT 500"

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_user_email(username, role=None):
    conn = get_connection()
    cursor = conn.cursor()

    # First check Users table if email column exists
    cursor.execute("PRAGMA table_info(Users);")
    user_cols = [col['name'] for col in cursor.fetchall()]
    if 'email' in user_cols:
        cursor.execute("SELECT email FROM Users WHERE username = ?", (username,))
        row = cursor.fetchone()
        if row and row['email']:
            conn.close()
            return row['email']

    # Next check Students table by username / ID / roll_number
    cursor.execute("PRAGMA table_info(Students);")
    st_cols = [col['name'] for col in cursor.fetchall()]
    if 'email' in st_cols:
        cursor.execute("SELECT email FROM Students WHERE id = ? OR roll_number = ?", (username, username))
        row = cursor.fetchone()
        if row and row['email']:
            conn.close()
            return row['email']

    conn.close()
    return f"{username}@student.edu.in"


