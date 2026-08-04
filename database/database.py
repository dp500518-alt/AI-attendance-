import sqlite3
import json
import os
import datetime
import time
import numpy as np
from werkzeug.security import generate_password_hash, check_password_hash
import config

import atexit
from logger import database_logger

_active_connections = set()

def close_all_connections():
    """Flushes SQLite WAL journals and closes active connections on shutdown."""
    global _active_connections
    for conn in list(_active_connections):
        try:
            conn.execute("PRAGMA wal_checkpoint(FULL);")
            conn.close()
        except Exception:
            pass
    _active_connections.clear()
    database_logger.info("SQLite database connections closed safely. WAL flushed.")

atexit.register(close_all_connections)

def get_connection():
    os.makedirs(config.DB_DIR, exist_ok=True)
    if not os.path.exists(config.DB_PATH):
        base_db = os.path.join(config.BASE_DIR, 'database', 'smart_attendance.db')
        if os.path.exists(base_db) and base_db != config.DB_PATH:
            try:
                import shutil
                shutil.copy2(base_db, config.DB_PATH)
                database_logger.info(f"Copied base database seed from {base_db} to {config.DB_PATH}")
            except Exception as e:
                database_logger.error(f"Error copying base DB seed: {e}")

    conn = sqlite3.connect(config.DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    except Exception:
        pass

    _active_connections.add(conn)
    return conn

def check_db_integrity():
    """Checks SQLite database integrity and returns status."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        res = cursor.execute("PRAGMA quick_check;").fetchone()
        conn.close()
        status = res[0] if res else "Unknown"
        return {'status': 'healthy' if status == 'ok' else status, 'integrity': status}
    except Exception as e:
        return {'status': 'error', 'message': str(e)}

def execute_with_retry(query_func, max_retries=5, delay=0.2):
    """
    Executes a database query operation with exponential retry backoff if database is locked or busy.
    """
    for attempt in range(max_retries):
        try:
            return query_func()
        except sqlite3.OperationalError as e:
            if ("locked" in str(e).lower() or "busy" in str(e).lower()) and attempt < max_retries - 1:
                time.sleep(delay * (2 ** attempt))
                continue
            raise e

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

    # StudentPhotos table (stores base64 photo samples directly inside DB for permanent persistence)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS StudentPhotos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT NOT NULL,
        photo_b64 TEXT NOT NULL,
        created_at TEXT NOT NULL,
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

    # Teacher Timetable table (Enhanced schema with FKs and full details)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS teacher_timetable (
        timetable_id INTEGER PRIMARY KEY AUTOINCREMENT,
        teacher_id TEXT NOT NULL,
        subject_id INTEGER,
        subject_code TEXT,
        subject_name TEXT NOT NULL,
        semester TEXT NOT NULL,
        division TEXT NOT NULL DEFAULT 'Division A',
        department TEXT NOT NULL,
        day TEXT NOT NULL,
        start_time TEXT NOT NULL,
        end_time TEXT NOT NULL,
        room_number TEXT NOT NULL,
        lecture_type TEXT NOT NULL DEFAULT 'Theory',
        academic_year TEXT NOT NULL DEFAULT '2025-2026',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(teacher_id) REFERENCES Users(username) ON DELETE CASCADE,
        FOREIGN KEY(subject_id) REFERENCES Subjects(id) ON DELETE SET NULL
    );
    """)

    # Migrate legacy Timetable rows if teacher_timetable is empty
    cursor.execute("SELECT COUNT(*) as cnt FROM teacher_timetable")
    if cursor.fetchone()['cnt'] == 0:
        cursor.execute("SELECT * FROM Timetable")
        legacy_rows = cursor.fetchall()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for row in legacy_rows:
            r = dict(row)
            cursor.execute("""
            INSERT INTO teacher_timetable (teacher_id, subject_name, department, semester, division, day, start_time, end_time, room_number, lecture_type, academic_year, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Theory', '2025-2026', ?, ?)
            """, (
                r.get('teacher_username', 'teacher'),
                r.get('subject_name', 'Subject'),
                r.get('department', 'Computer'),
                r.get('semester', 'Semester 1'),
                r.get('division', 'Division A'),
                r.get('day_of_week', 'Monday'),
                r.get('start_time', '09:00'),
                r.get('end_time', '10:00'),
                r.get('room_number', 'Room 101'),
                r.get('created_at', now_str),
                now_str
            ))

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

    # Default settings
    cursor.execute("INSERT OR IGNORE INTO Settings (key, value) VALUES ('recognition_threshold', ?)",
                   (str(config.RECOGNITION_THRESHOLD),))

    # Auto-migrate legacy/old timetable time slots to new Lecture Schedule timing
    time_mappings = [
        (('09:00', '10:00'), ('10:30', '11:30')),
        (('10:00', '11:00'), ('11:30', '12:30')),
        (('11:15', '12:15'), ('13:10', '14:10')),
        (('12:15', '13:15'), ('14:10', '15:10')),
        (('14:00', '15:00'), ('15:30', '16:30')),
        (('15:00', '16:00'), ('16:30', '17:30')),
        (('16:00', '17:00'), ('16:30', '17:30')),
    ]
    for old_s, new_s in time_mappings:
        cursor.execute("UPDATE teacher_timetable SET start_time = ?, end_time = ? WHERE start_time = ? AND end_time = ?", (new_s[0], new_s[1], old_s[0], old_s[1]))
        cursor.execute("UPDATE Timetable SET start_time = ?, end_time = ? WHERE start_time = ? AND end_time = ?", (new_s[0], new_s[1], old_s[0], old_s[1]))

    conn.commit()
    conn.close()

    # Trigger automatic startup scanning and persistence recovery
    try:
        run_startup_database_recovery()
    except Exception as e_rec:
        database_logger.error(f"Startup persistence recovery error: {e_rec}")

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
    """
    Inserts student into Students table, immediately commits transaction, and verifies presence.
    If insertion fails or record cannot be verified, rollbacks and raises an exception.
    """
    student_id = str(student_id).strip()
    roll_number = str(roll_number).strip()
    name = str(name).strip()
    department = str(department).strip()
    semester = str(semester).strip()
    division = str(division).strip()
    email = str(email).strip()
    phone = str(phone).strip()

    conn = get_connection()
    try:
        cursor = conn.cursor()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("""
        INSERT INTO Students (id, roll_number, name, department, semester, division, email, phone, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            roll_number = excluded.roll_number,
            name = excluded.name,
            department = excluded.department,
            semester = excluded.semester,
            division = excluded.division,
            email = excluded.email,
            phone = excluded.phone
        """, (student_id, roll_number, name, department, semester, division, email, phone, now_str))
        conn.commit()

        # Immediate verification after commit
        cursor.execute("SELECT id FROM Students WHERE id = ?", (student_id,))
        row = cursor.fetchone()
        if not row:
            conn.rollback()
            raise RuntimeError(f"Verification failed: Student '{student_id}' was not found in SQLite database after insertion.")
        database_logger.info(f"Successfully inserted and verified student {student_id} ({name}) in database.")
    except Exception as e:
        conn.rollback()
        database_logger.error(f"Failed to insert student {student_id}: {e}")
        raise e
    finally:
        conn.close()

def get_all_students():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM Students ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_departments():
    """Returns list of distinct departments from database."""
    try:
        conn = get_connection()
        c = conn.cursor()
        c.execute("SELECT DISTINCT department FROM students WHERE department IS NOT NULL AND department != ''")
        rows = c.fetchall()
        depts = [r[0] for r in rows if r[0]]
        if not depts:
            depts = ['Computer Science', 'Information Technology', 'Electronics', 'Mechanical', 'Civil']
        return depts
    except Exception:
        return ['Computer Science', 'Information Technology', 'Electronics', 'Mechanical', 'Civil']

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

# Student Photos Storage Functions
def save_student_photos(student_id, photo_b64_list):
    """
    Persists student sample photos as base64 in SQLite StudentPhotos table for permanent backup.
    """
    if not photo_b64_list:
        return
    conn = get_connection()
    try:
        cursor = conn.cursor()
        now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("DELETE FROM StudentPhotos WHERE student_id = ?", (str(student_id),))
        for b64 in photo_b64_list:
            if b64:
                cursor.execute("""
                INSERT INTO StudentPhotos (student_id, photo_b64, created_at)
                VALUES (?, ?, ?)
                """, (str(student_id), str(b64), now_str))
        conn.commit()
        database_logger.info(f"Saved {len(photo_b64_list)} photos to SQLite StudentPhotos for student {student_id}.")
    except Exception as e:
        conn.rollback()
        database_logger.error(f"Error saving photos for student {student_id}: {e}")
        raise e
    finally:
        conn.close()

def get_student_photos(student_id):
    """
    Retrieves base64 photo strings for a given student from SQLite.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT photo_b64 FROM StudentPhotos WHERE student_id = ? ORDER BY id ASC", (str(student_id),))
    rows = cursor.fetchall()
    conn.close()
    return [r['photo_b64'] for r in rows]

# Embeddings Functions
def save_embedding(student_id, embedding_vector):
    """
    Saves face embedding vector into Embeddings table, commits, and verifies persistence.
    """
    student_id = str(student_id).strip()
    if isinstance(embedding_vector, np.ndarray):
        emb_list = embedding_vector.tolist()
    else:
        emb_list = list(embedding_vector)

    emb_json = json.dumps(emb_list)
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("""
        INSERT INTO Embeddings (student_id, embedding, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(student_id) DO UPDATE SET
            embedding = excluded.embedding,
            updated_at = excluded.updated_at
        """, (student_id, emb_json, now_str))
        conn.commit()

        # Immediate verification
        cursor.execute("SELECT student_id FROM Embeddings WHERE student_id = ?", (student_id,))
        if not cursor.fetchone():
            conn.rollback()
            raise RuntimeError(f"Embedding verification failed for student '{student_id}'.")
        database_logger.info(f"Successfully saved and verified embedding vector for student {student_id}.")
    except Exception as e:
        conn.rollback()
        database_logger.error(f"Failed to save embedding for student {student_id}: {e}")
        raise e
    finally:
        conn.close()

def get_student_embedding(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT embedding FROM Embeddings WHERE student_id = ?", (str(student_id),))
    row = cursor.fetchone()
    conn.close()
    if row and row['embedding']:
        try:
            return np.array(json.loads(row['embedding']), dtype=np.float32)
        except Exception:
            return None
    return None

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

def run_startup_database_recovery():
    """
    Runs automated integrity check and startup recovery scan:
    - Restores missing dataset folders from StudentPhotos in SQLite.
    - Automatically regenerates missing face embeddings.
    """
    integ = check_db_integrity()
    if integ.get('status') == 'corrupted':
        err_msg = f"Database integrity check failed: {integ.get('message')}"
        database_logger.critical(err_msg)
        print(f"CRITICAL: {err_msg}")
        return

    students = get_all_students()
    if not students:
        return

    restored_datasets = 0
    restored_embeddings = 0

    for s in students:
        sid = str(s['id'])
        student_dir = os.path.join(config.DATASET_DIR, sid)
        os.makedirs(student_dir, exist_ok=True)

        image_files = [f for f in os.listdir(student_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        
        # 1. Restore missing dataset photos from StudentPhotos SQLite table
        if not image_files:
            db_photos = get_student_photos(sid)
            if db_photos:
                from camera import decode_base64_image
                import cv2
                for idx, b64_str in enumerate(db_photos):
                    try:
                        img = decode_base64_image(b64_str)
                        if img is not None and img.size > 0:
                            fname = f"sample_{idx+1:02d}.jpg"
                            fpath = os.path.join(student_dir, fname)
                            cv2.imwrite(fpath, img)
                    except Exception as err:
                        database_logger.error(f"Error restoring photo {idx} for {sid}: {err}")
                image_files = [f for f in os.listdir(student_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
                if image_files:
                    restored_datasets += 1
                    database_logger.info(f"[Recovery] Restored {len(image_files)} dataset photos for student {sid} from SQLite.")

        # 2. Automatically regenerate missing embeddings
        emb = get_student_embedding(sid)
        if emb is None and image_files:
            try:
                from train import generate_embedding_for_student
                success, msg = generate_embedding_for_student(sid)
                if success:
                    restored_embeddings += 1
                    database_logger.info(f"[Recovery] Regenerated missing face embedding for student {sid}.")
            except Exception as err:
                database_logger.error(f"Error regenerating embedding for {sid}: {err}")

    if restored_datasets > 0 or restored_embeddings > 0:
        database_logger.info(f"[Startup Recovery Summary] Restored {restored_datasets} dataset folders, regenerated {restored_embeddings} embeddings.")

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
        if timetable_id is not None:
            cursor.execute(
                "SELECT id FROM Attendance WHERE student_id=? AND date=? AND timetable_id=?",
                (student_id, date_str, timetable_id)
            )
        else:
            cursor.execute(
                "SELECT id FROM Attendance WHERE student_id=? AND date=? AND subject_name=?",
                (student_id, date_str, subject_name or 'General Attendance Session')
            )
        if cursor.fetchone():
            return False

        cursor.execute("""
        INSERT INTO Attendance (student_id, date, time, status, timetable_id, subject_name, semester, division)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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
    cursor.execute("PRAGMA table_info(Users);")
    user_cols = [col['name'] for col in cursor.fetchall()]
    select_cols = "id, username, full_name, department, role, created_at"
    if 'email' in user_cols:
        select_cols += ", email"
    cursor.execute(f"SELECT {select_cols} FROM Users WHERE role = 'teacher' ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def add_user(username, password, full_name='', department='', role='teacher', email=''):
    conn = get_connection()
    cursor = conn.cursor()
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    pass_hash = generate_password_hash(password)
    try:
        cursor.execute("PRAGMA table_info(Users);")
        user_cols = [col['name'] for col in cursor.fetchall()]
        if 'email' in user_cols:
            cursor.execute("""
            INSERT INTO Users (username, password_hash, full_name, department, role, email, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (username.strip(), pass_hash, full_name.strip(), department.strip(), role, email.strip(), now_str))
        else:
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

def create_teacher_user(username, password, full_name='', department='', email='', role='teacher'):
    success, msg = add_user(username=username, password=password, full_name=full_name, department=department, role=role, email=email)
    return {'success': success, 'message': msg}

def delete_user(user_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Users WHERE id = ? AND username != ?", (user_id, config.DEFAULT_ADMIN_USER))
    conn.commit()
    conn.close()

def delete_teacher_user(user_id):
    delete_user(user_id)

# Timetable & Intelligent Detection Functions

def check_timetable_conflict(teacher_id, day, start_time, end_time, room_number, ignore_id=None):
    """
    Checks for scheduling conflicts:
    1. Same teacher having an overlapping lecture at the same day and time.
    2. Same room being occupied by another lecture at the same day and time.
    """
    conn = get_connection()
    cursor = conn.cursor()

    query_teacher = """
    SELECT timetable_id, subject_name, start_time, end_time, room_number
    FROM teacher_timetable
    WHERE teacher_id = ? AND day = ? 
      AND NOT (end_time <= ? OR start_time >= ?)
    """
    params_teacher = [teacher_id, day, start_time, end_time]
    if ignore_id:
        query_teacher += " AND timetable_id != ?"
        params_teacher.append(ignore_id)

    cursor.execute(query_teacher, params_teacher)
    conflict = cursor.fetchone()
    if conflict:
        conn.close()
        return True, f"Conflict: Teacher '{teacher_id}' already has '{conflict['subject_name']}' ({conflict['start_time']}-{conflict['end_time']}) scheduled on {day}."

    if room_number:
        query_room = """
        SELECT timetable_id, teacher_id, subject_name, start_time, end_time
        FROM teacher_timetable
        WHERE room_number = ? AND day = ?
          AND NOT (end_time <= ? OR start_time >= ?)
        """
        params_room = [room_number, day, start_time, end_time]
        if ignore_id:
            query_room += " AND timetable_id != ?"
            params_room.append(ignore_id)

        cursor.execute(query_room, params_room)
        r_conflict = cursor.fetchone()
        if r_conflict:
            conn.close()
            return True, f"Conflict: Room '{room_number}' is already booked by '{r_conflict['teacher_id']}' for '{r_conflict['subject_name']}' ({r_conflict['start_time']}-{r_conflict['end_time']}) on {day}."

    conn.close()
    return False, ""

def get_teacher_timetable(teacher_username=None, semester=None, division=None, day_of_week=None):
    conn = get_connection()
    cursor = conn.cursor()

    query = """
    SELECT 
        tt.timetable_id as id,
        tt.timetable_id,
        tt.teacher_id,
        tt.teacher_id as teacher_username,
        u.full_name as teacher_name,
        tt.subject_id,
        tt.subject_code,
        tt.subject_name,
        tt.department,
        tt.semester,
        tt.division,
        tt.day as day_of_week,
        tt.day,
        tt.start_time,
        tt.end_time,
        tt.room_number,
        tt.lecture_type,
        tt.academic_year,
        tt.created_at,
        tt.updated_at
    FROM teacher_timetable tt
    LEFT JOIN Users u ON tt.teacher_id = u.username
    WHERE 1=1
    """
    params = []

    if teacher_username and str(teacher_username).strip() not in ['', 'None', 'all', 'All Teachers']:
        query += " AND (tt.teacher_id = ? OR u.full_name LIKE ?)"
        params.extend([teacher_username.strip(), f"%{teacher_username.strip()}%"])
    if semester and str(semester).strip() not in ['', 'None', 'all', 'All Semesters']:
        query += " AND (tt.semester = ? OR tt.semester LIKE ?)"
        params.extend([semester.strip(), f"%{semester.strip()}%"])
    if division and str(division).strip() not in ['', 'None', 'all', 'All Divisions']:
        query += " AND (tt.division = ? OR tt.division LIKE ?)"
        params.extend([division.strip(), f"%{division.strip()}%"])
    if day_of_week:
        query += " AND (tt.day = ? OR tt.day LIKE ?)"
        params.extend([day_of_week, f"%{day_of_week}%"])

    query += """
    ORDER BY CASE tt.day
        WHEN 'Monday' THEN 1
        WHEN 'Tuesday' THEN 2
        WHEN 'Wednesday' THEN 3
        WHEN 'Thursday' THEN 4
        WHEN 'Friday' THEN 5
        WHEN 'Saturday' THEN 6
        WHEN 'Sunday' THEN 7
        ELSE 8
    END, tt.start_time ASC
    """

    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_timetable(teacher_username=None, semester=None, division=None, day_of_week=None):
    return get_teacher_timetable(teacher_username, semester, division, day_of_week)

def add_teacher_timetable_entry(teacher_id, subject_name, department, semester, division, day, start_time, end_time, room_number='', lecture_type='Theory', academic_year='2025-2026', subject_code=''):
    conn = get_connection()
    cursor = conn.cursor()

    teacher_id = teacher_id.strip()
    cursor.execute("SELECT username FROM Users WHERE username = ?", (teacher_id,))
    u_row = cursor.fetchone()
    if not u_row:
        cursor.execute("SELECT username FROM Users WHERE role = 'teacher' LIMIT 1")
        fallback = cursor.fetchone()
        teacher_id = fallback[0] if fallback else 'teacher'

    has_conflict, conflict_msg = check_timetable_conflict(teacher_id, day.strip(), start_time.strip(), end_time.strip(), room_number.strip())
    if has_conflict:
        conn.close()
        return False, conflict_msg, None

    subject_id = None
    cursor.execute("SELECT id, code FROM Subjects WHERE name = ? LIMIT 1", (subject_name.strip(),))
    s_row = cursor.fetchone()
    if s_row:
        subject_id = s_row['id']
        if not subject_code and s_row['code']:
            subject_code = s_row['code']

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    INSERT INTO teacher_timetable (
        teacher_id, subject_id, subject_code, subject_name, department, semester, division, day, start_time, end_time, room_number, lecture_type, academic_year, created_at, updated_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        teacher_id, subject_id, subject_code.strip(), subject_name.strip(),
        department.strip(), semester.strip(), division.strip(), day.strip(),
        start_time.strip(), end_time.strip(), room_number.strip() or 'Room 101',
        lecture_type.strip(), academic_year.strip(), now_str, now_str
    ))

    tt_id = cursor.lastrowid

    cursor.execute("""
    INSERT INTO Timetable (teacher_username, subject_name, department, semester, division, day_of_week, start_time, end_time, room_number, created_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (teacher_id, subject_name.strip(), department.strip(), semester.strip(), division.strip(), day.strip(), start_time.strip(), end_time.strip(), room_number.strip(), now_str))

    conn.commit()
    conn.close()
    return True, "Timetable entry added successfully.", tt_id

def add_timetable_entry(teacher_username, subject_name, department, semester, day_of_week, start_time, end_time, room_number='', division='Division A'):
    success, msg, _ = add_teacher_timetable_entry(teacher_username, subject_name, department, semester, division, day_of_week, start_time, end_time, room_number)
    return success

def update_teacher_timetable_entry(timetable_id, teacher_id, subject_name, department, semester, division, day, start_time, end_time, room_number='', lecture_type='Theory', academic_year='2025-2026', subject_code=''):
    conn = get_connection()
    cursor = conn.cursor()

    has_conflict, conflict_msg = check_timetable_conflict(teacher_id.strip(), day.strip(), start_time.strip(), end_time.strip(), room_number.strip(), ignore_id=timetable_id)
    if has_conflict:
        conn.close()
        return False, conflict_msg

    subject_id = None
    cursor.execute("SELECT id, code FROM Subjects WHERE name = ? LIMIT 1", (subject_name.strip(),))
    s_row = cursor.fetchone()
    if s_row:
        subject_id = s_row['id']
        if not subject_code and s_row['code']:
            subject_code = s_row['code']

    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
    UPDATE teacher_timetable SET
        teacher_id = ?,
        subject_id = ?,
        subject_code = ?,
        subject_name = ?,
        department = ?,
        semester = ?,
        division = ?,
        day = ?,
        start_time = ?,
        end_time = ?,
        room_number = ?,
        lecture_type = ?,
        academic_year = ?,
        updated_at = ?
    WHERE timetable_id = ?
    """, (
        teacher_id.strip(), subject_id, subject_code.strip(), subject_name.strip(),
        department.strip(), semester.strip(), division.strip(), day.strip(),
        start_time.strip(), end_time.strip(), room_number.strip(),
        lecture_type.strip(), academic_year.strip(), now_str, timetable_id
    ))
    conn.commit()
    conn.close()
    return True, "Timetable slot updated successfully."

def delete_teacher_timetable_entry(entry_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM teacher_timetable WHERE timetable_id = ?", (entry_id,))
    cursor.execute("DELETE FROM Timetable WHERE id = ?", (entry_id,))
    conn.commit()
    conn.close()

def delete_timetable_entry(entry_id):
    delete_teacher_timetable_entry(entry_id)

def get_active_lecture_for_teacher(teacher_id, day_of_week=None, time_str=None, slot_id=None):
    conn = get_connection()
    cursor = conn.cursor()

    if slot_id:
        cursor.execute("""
        SELECT tt.*, tt.timetable_id as id, tt.teacher_id as teacher_username, tt.day as day_of_week, u.full_name as teacher_name
        FROM teacher_timetable tt
        LEFT JOIN Users u ON tt.teacher_id = u.username
        WHERE tt.timetable_id = ?
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

    cursor.execute("""
    SELECT tt.*, tt.timetable_id as id, tt.teacher_id as teacher_username, tt.day as day_of_week, u.full_name as teacher_name
    FROM teacher_timetable tt
    LEFT JOIN Users u ON tt.teacher_id = u.username
    WHERE tt.teacher_id = ? AND tt.day = ? AND tt.start_time <= ? AND tt.end_time >= ?
    ORDER BY tt.start_time ASC
    LIMIT 1
    """, (teacher_id, day_of_week, time_str, time_str))
    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)

    cursor.execute("""
    SELECT tt.*, tt.timetable_id as id, tt.teacher_id as teacher_username, tt.day as day_of_week, u.full_name as teacher_name
    FROM teacher_timetable tt
    LEFT JOIN Users u ON tt.teacher_id = u.username
    WHERE tt.teacher_id = ? AND tt.day = ? AND tt.start_time > ?
    ORDER BY tt.start_time ASC
    LIMIT 1
    """, (teacher_id, day_of_week, time_str))
    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)

    cursor.execute("""
    SELECT tt.*, tt.timetable_id as id, tt.teacher_id as teacher_username, tt.day as day_of_week, u.full_name as teacher_name
    FROM teacher_timetable tt
    LEFT JOIN Users u ON tt.teacher_id = u.username
    WHERE tt.teacher_id = ? AND tt.day = ?
    ORDER BY tt.start_time ASC
    LIMIT 1
    """, (teacher_id, day_of_week))
    row = cursor.fetchone()
    if row:
        conn.close()
        return dict(row)

    cursor.execute("""
    SELECT tt.*, tt.timetable_id as id, tt.teacher_id as teacher_username, tt.day as day_of_week, u.full_name as teacher_name
    FROM teacher_timetable tt
    LEFT JOIN Users u ON tt.teacher_id = u.username
    WHERE tt.teacher_id = ?
    ORDER BY tt.start_time ASC
    LIMIT 1
    """, (teacher_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_active_timetable_slot(teacher_username=None, day_of_week=None, time_str=None, slot_id=None):
    if teacher_username:
        return get_active_lecture_for_teacher(teacher_username, day_of_week, time_str, slot_id)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT timetable_id as id, teacher_id as teacher_username, day as day_of_week, * FROM teacher_timetable ORDER BY timetable_id DESC LIMIT 1")
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_teacher_dashboard_stats(teacher_id):
    conn = get_connection()
    cursor = conn.cursor()

    now = datetime.datetime.now()
    today_day = now.strftime("%A")
    today_date = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    cursor.execute("""
    SELECT tt.*, u.full_name as teacher_name
    FROM teacher_timetable tt
    LEFT JOIN Users u ON tt.teacher_id = u.username
    WHERE tt.teacher_id = ? AND tt.day = ?
    ORDER BY tt.start_time ASC
    """, (teacher_id, today_day))
    today_slots = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT COUNT(*) as cnt FROM teacher_timetable WHERE teacher_id = ?", (teacher_id,))
    weekly_classes = cursor.fetchone()['cnt']

    current_lecture = None
    next_lecture = None
    remaining_classes = 0
    completed_classes = 0

    for slot in today_slots:
        if slot['start_time'] <= current_time <= slot['end_time']:
            current_lecture = slot
        elif slot['start_time'] > current_time:
            remaining_classes += 1
            if not next_lecture:
                next_lecture = slot
        elif slot['end_time'] < current_time:
            completed_classes += 1

    cursor.execute("""
    SELECT COUNT(DISTINCT student_id) as present
    FROM Attendance
    WHERE date = ? AND (timetable_id IN (SELECT timetable_id FROM teacher_timetable WHERE teacher_id = ?) OR timetable_id IS NULL)
    """, (today_date, teacher_id))
    present_today = cursor.fetchone()['present']

    cursor.execute("SELECT COUNT(*) as total FROM Students")
    total_students = cursor.fetchone()['total']

    cursor.execute("SELECT DISTINCT timetable_id FROM Attendance WHERE date = ?", (today_date,))
    conducted_tt_ids = set([r['timetable_id'] for r in cursor.fetchall() if r['timetable_id']])
    attendance_pending = sum(1 for s in today_slots if s['timetable_id'] not in conducted_tt_ids)

    reminder_message = None
    if next_lecture:
        try:
            start_12h = datetime.datetime.strptime(next_lecture['start_time'], "%H:%M").strftime("%I:%M %p")
        except Exception:
            start_12h = next_lecture['start_time']
        reminder_message = f"Your next lecture is {next_lecture['subject_name']} for {next_lecture['semester']} {next_lecture['division']} at {start_12h} in Room {next_lecture['room_number']}."
    elif current_lecture:
        try:
            end_12h = datetime.datetime.strptime(current_lecture['end_time'], "%H:%M").strftime("%I:%M %p")
        except Exception:
            end_12h = current_lecture['end_time']
        reminder_message = f"You are currently teaching {current_lecture['subject_name']} for {current_lecture['semester']} {current_lecture['division']} in Room {current_lecture['room_number']} (until {end_12h})."
    elif today_slots:
        reminder_message = f"All {len(today_slots)} lectures for today ({today_day}) are completed."
    else:
        reminder_message = f"No classes scheduled for today ({today_day})."

    conn.close()
    return {
        'today_classes': len(today_slots),
        'today_slots': today_slots,
        'current_lecture': current_lecture,
        'next_lecture': next_lecture,
        'weekly_classes': weekly_classes,
        'remaining_classes': remaining_classes,
        'completed_classes': completed_classes,
        'present_today': present_today,
        'total_students': total_students,
        'attendance_pending': attendance_pending,
        'reminder_message': reminder_message,
        'today_day': today_day,
        'today_date': today_date
    }

def seed_100_teachers_and_timetables():
    conn = get_connection()
    cursor = conn.cursor()

    pass_hash = generate_password_hash("teacher123")
    now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    departments = ["Electronic & Communication", "Electrical", "Mechanical", "Civil", "Computer", "Environment"]
    subjects_pool = [
        ("CS401", "Digital Signal Processing", "Computer", "Semester 4"),
        ("CS402", "Data Structures & Algorithms", "Computer", "Semester 4"),
        ("CS403", "Database Management Systems", "Computer", "Semester 4"),
        ("CS601", "Artificial Intelligence & ML", "Computer", "Semester 6"),
        ("CS602", "Computer Networks", "Computer", "Semester 6"),
        ("EV501", "Environmental Engineering", "Environment", "Semester 5"),
        ("EV502", "Waste Management", "Environment", "Semester 5"),
        ("EC301", "Digital Electronics", "Electronic & Communication", "Semester 3"),
        ("EE401", "Control Systems", "Electrical", "Semester 4"),
        ("ME501", "Thermodynamics", "Mechanical", "Semester 5")
    ]

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]
    slots = [
        ("10:30", "11:30"),
        ("11:30", "12:30"),
        ("13:10", "14:10"),
        ("14:10", "15:10"),
        ("15:30", "16:30"),
        ("16:30", "17:30")
    ]
    divisions = ["Division A", "Division B"]

    teachers_created = 0
    tt_created = 0

    for i in range(1, 101):
        t_username = f"teacher{i}"
        t_name = f"Prof. Faculty {i}"
        dept = departments[(i - 1) % len(departments)]

        cursor.execute("SELECT id FROM Users WHERE username = ?", (t_username,))
        if not cursor.fetchone():
            cursor.execute("""
            INSERT INTO Users (username, password_hash, full_name, department, role, created_at)
            VALUES (?, ?, ?, ?, 'teacher', ?)
            """, (t_username, pass_hash, t_name, dept, now_str))
            teachers_created += 1

        for slot_idx in range(3):
            day = days[(i + slot_idx) % len(days)]
            slot_t = slots[(i + slot_idx) % len(slots)]
            subj_info = subjects_pool[(i + slot_idx) % len(subjects_pool)]
            div = divisions[(i + slot_idx) % len(divisions)]
            room = f"Room E{100 + ((i + slot_idx) % 30)}"
            l_type = "Lab" if slot_idx == 2 else "Theory"

            cursor.execute("""
            SELECT timetable_id FROM teacher_timetable
            WHERE (teacher_id = ? OR room_number = ?) AND day = ? AND start_time = ?
            """, (t_username, room, day, slot_t[0]))

            if not cursor.fetchone():
                cursor.execute("""
                INSERT INTO teacher_timetable (
                    teacher_id, subject_code, subject_name, department, semester, division, day, start_time, end_time, room_number, lecture_type, academic_year, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '2025-2026', ?, ?)
                """, (
                    t_username, subj_info[0], subj_info[1], dept, subj_info[3], div, day, slot_t[0], slot_t[1], room, l_type, now_str, now_str
                ))
                tt_created += 1

    conn.commit()
    conn.close()
    return teachers_created, tt_created


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

# --- Student Photos & Backup Sync Functions ---

def save_student_photos(student_id, photos_b64_list):
    if not photos_b64_list:
        return
    def _action():
        conn = get_connection()
        try:
            cursor = conn.cursor()
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            for photo_b64 in photos_b64_list:
                cursor.execute(
                    "INSERT INTO StudentPhotos (student_id, photo_b64, created_at) VALUES (?, ?, ?)",
                    (str(student_id), photo_b64, now_str)
                )
            conn.commit()
        finally:
            conn.close()

    execute_with_retry(_action)

def get_student_photos(student_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT photo_b64 FROM StudentPhotos WHERE student_id = ? ORDER BY id ASC", (str(student_id),))
    rows = cursor.fetchall()
    conn.close()
    return [r['photo_b64'] for r in rows]

def export_database_json():
    """
    Exports a full JSON snapshot dump of database records for permanent cloud persistence.
    """
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM Students")
    students = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM Embeddings")
    embeddings = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM StudentPhotos")
    photos = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM Users")
    users = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM Timetable")
    timetable = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM Attendance")
    attendance = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        'version': '1.0',
        'exported_at': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'students': students,
        'embeddings': embeddings,
        'photos': photos,
        'users': users,
        'timetable': timetable,
        'attendance': attendance
    }

def import_database_json(data):
    """
    Restores database tables from JSON dump data.
    """
    if not isinstance(data, dict):
        return False, "Invalid JSON data structure."

    conn = get_connection()
    cursor = conn.cursor()

    try:
        if 'students' in data:
            for s in data['students']:
                cursor.execute("""
                INSERT OR REPLACE INTO Students (id, roll_number, name, department, semester, division, email, phone, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (s['id'], s['roll_number'], s['name'], s['department'], s['semester'], s.get('division', 'Division A'), s.get('email', ''), s.get('phone', ''), s.get('created_at', '')))

        if 'photos' in data:
            for p in data['photos']:
                cursor.execute("""
                INSERT OR REPLACE INTO StudentPhotos (student_id, photo_b64, created_at)
                VALUES (?, ?, ?)
                """, (p['student_id'], p['photo_b64'], p.get('created_at', '')))

        if 'embeddings' in data:
            for e in data['embeddings']:
                cursor.execute("""
                INSERT OR REPLACE INTO Embeddings (student_id, embedding, updated_at)
                VALUES (?, ?, ?)
                """, (e['student_id'], e['embedding'], e.get('updated_at', '')))

        if 'users' in data:
            for u in data['users']:
                cursor.execute("""
                INSERT OR REPLACE INTO Users (username, password_hash, full_name, department, role, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """, (u['username'], u['password_hash'], u.get('full_name', ''), u.get('department', ''), u.get('role', 'teacher'), u.get('created_at', '')))

        if 'timetable' in data:
            for t in data['timetable']:
                cursor.execute("""
                INSERT OR REPLACE INTO Timetable (teacher_username, subject_name, department, semester, division, day_of_week, start_time, end_time, room_number, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (t['teacher_username'], t['subject_name'], t['department'], t['semester'], t.get('division', 'Division A'), t['day_of_week'], t['start_time'], t['end_time'], t.get('room_number', ''), t.get('created_at', '')))

        if 'attendance' in data:
            for a in data['attendance']:
                cursor.execute("""
                INSERT OR IGNORE INTO Attendance (student_id, timetable_id, subject_name, semester, division, date, time, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (a['student_id'], a.get('timetable_id'), a.get('subject_name', ''), a.get('semester', ''), a.get('division', ''), a['date'], a['time'], a.get('status', 'Present')))

        conn.commit()
        conn.close()

        # Re-trigger embedding generation for any missing embeddings
        from train import train_all_students
        train_all_students()

        return True, "Database successfully restored from JSON backup."
    except Exception as err:
        conn.rollback()
        conn.close()
        return False, f"Import failed: {err}"

def sync_backup_seed():
    """
    Saves a JSON snapshot seed to database/backup_seed.json.
    """
    try:
        data = export_database_json()
        target_path = os.path.join(config.BASE_DIR, 'database', 'backup_seed.json')
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Could not sync backup seed: {e}")


