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
        date TEXT NOT NULL,
        time TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Present',
        UNIQUE(student_id, date),
        FOREIGN KEY(student_id) REFERENCES Students(id) ON DELETE CASCADE
    );
    """)

    # Admin & Teacher Users table
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

    # Timetable table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS Timetable (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_username TEXT NOT NULL,
        subject_name TEXT NOT NULL,
        department TEXT NOT NULL,
        semester TEXT NOT NULL,
        day_of_week TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        room_number TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(teacher_username) REFERENCES Users(username) ON DELETE CASCADE
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
def add_student(student_id, roll_number, name, department, semester):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO Students (id, roll_number, name, department, semester, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (student_id.strip(), roll_number.strip(), name.strip(), department.strip(), semester.strip(), now_str))
    conn.commit()
    conn.close()

def get_all_students():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Students ORDER BY created_at DESC")
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
def mark_attendance(student_id, status='Present', date_str=None, time_str=None):
    now = datetime.datetime.now()
    if not date_str:
        date_str = now.strftime("%Y-%m-%d")
    if not time_str:
        time_str = now.strftime("%H:%M:%S")

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
        INSERT INTO Attendance (student_id, date, time, status)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(student_id, date) DO NOTHING
        """, (student_id, date_str, time_str, status))
        conn.commit()
        inserted = cursor.rowcount > 0
    except sqlite3.Error:
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
    SELECT a.id, a.student_id, s.name, s.roll_number, s.department, s.semester, a.date, a.time, a.status
    FROM Attendance a
    JOIN Students s ON a.student_id = s.id
    WHERE a.date = ?
    ORDER BY a.time DESC
    """, (date_str,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_attendance_history(date_filter=None, dept_filter=None, search_term=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT a.id, a.student_id, s.name, s.roll_number, s.department, s.semester, a.date, a.time, a.status
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
    if search_term:
        query += " AND (s.name LIKE ? OR s.roll_number LIKE ? OR a.student_id LIKE ?)"
        term = f"%{search_term}%"
        params.extend([term, term, term])

    query += " ORDER BY a.date DESC, a.time DESC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

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

    conn.close()
    return {
        'total_students': total_students,
        'present_today': present_today,
        'absent_today': absent_today,
        'attendance_pct': attendance_pct,
        'today_date': today
    }

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

# Timetable Functions
def get_timetable(teacher_username=None):
    conn = get_connection()
    cursor = conn.cursor()
    if teacher_username:
        cursor.execute("""
        SELECT t.*, u.full_name as teacher_name 
        FROM Timetable t
        LEFT JOIN Users u ON t.teacher_username = u.username
        WHERE t.teacher_username = ?
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
        """, (teacher_username,))
    else:
        cursor.execute("""
        SELECT t.*, u.full_name as teacher_name 
        FROM Timetable t
        LEFT JOIN Users u ON t.teacher_username = u.username
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
        """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_timetable_entry(teacher_username, subject_name, department, semester, day_of_week, start_time, end_time, room_number=''):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
    INSERT INTO Timetable (teacher_username, subject_name, department, semester, day_of_week, start_time, end_time, room_number, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (teacher_username.strip(), subject_name.strip(), department.strip(), semester.strip(), day_of_week.strip(), start_time.strip(), end_time.strip(), room_number.strip(), now_str))
    conn.commit()
    conn.close()

def delete_timetable_entry(entry_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Timetable WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()

