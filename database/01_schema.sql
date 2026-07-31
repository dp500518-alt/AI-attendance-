-- MySQL 8 Schema for AI Smart Attendance System
-- Generated for 1000 Users (900 Students, 100 Teachers)

CREATE DATABASE IF NOT EXISTS smart_attendance_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE smart_attendance_db;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS attendance;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS timetable;
DROP TABLE IF EXISTS subjects;
DROP TABLE IF EXISTS teachers;
DROP TABLE IF EXISTS face_embeddings;
DROP TABLE IF EXISTS students;
DROP TABLE IF EXISTS dashboard_stats;
SET FOREIGN_KEY_CHECKS = 1;

-- 1. Students Table
CREATE TABLE students (
    student_id VARCHAR(20) PRIMARY KEY,
    enrollment_number VARCHAR(30) NOT NULL UNIQUE,
    roll_number VARCHAR(20) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    full_name VARCHAR(105) NOT NULL,
    gender ENUM('Male', 'Female', 'Other') NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(15) NOT NULL UNIQUE,
    semester VARCHAR(20) NOT NULL,
    division VARCHAR(10) NOT NULL,
    department VARCHAR(100) NOT NULL,
    date_of_birth DATE NOT NULL,
    admission_year INT NOT NULL,
    parent_name VARCHAR(100) NOT NULL,
    parent_phone VARCHAR(15) NOT NULL,
    address TEXT NOT NULL,
    city VARCHAR(50) NOT NULL,
    state VARCHAR(50) NOT NULL,
    attendance_percentage DECIMAL(5, 2) DEFAULT 0.00,
    profile_photo VARCHAR(255) DEFAULT NULL,
    face_embedding_path VARCHAR(255) DEFAULT NULL,
    status ENUM('Active', 'Inactive', 'Graduated') DEFAULT 'Active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sem_div (semester, division),
    INDEX idx_enrollment (enrollment_number)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 2. Teachers Table
CREATE TABLE teachers (
    teacher_id INT PRIMARY KEY,
    employee_id VARCHAR(30) NOT NULL UNIQUE,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100) NOT NULL UNIQUE,
    phone VARCHAR(15) NOT NULL UNIQUE,
    designation VARCHAR(50) NOT NULL,
    specialization VARCHAR(100) NOT NULL,
    experience INT NOT NULL,
    joining_date DATE NOT NULL,
    profile_photo VARCHAR(255) DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 3. Subjects Table
CREATE TABLE subjects (
    subject_id INT PRIMARY KEY,
    subject_code VARCHAR(20) NOT NULL UNIQUE,
    subject_name VARCHAR(100) NOT NULL,
    semester VARCHAR(20) NOT NULL,
    credits INT NOT NULL DEFAULT 4,
    teacher_id INT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE,
    INDEX idx_subject_sem (semester)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 4. Timetable Table
CREATE TABLE timetable (
    timetable_id INT PRIMARY KEY,
    semester VARCHAR(20) NOT NULL,
    division VARCHAR(10) NOT NULL,
    day_of_week ENUM('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday') NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    subject_id INT NOT NULL,
    teacher_id INT NOT NULL,
    room_number VARCHAR(30) NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE,
    INDEX idx_timetable_slot (day_of_week, start_time, end_time),
    INDEX idx_timetable_sem_div (semester, division)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 5. Attendance Table
CREATE TABLE attendance (
    attendance_id BIGINT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20) NOT NULL,
    teacher_id INT NOT NULL,
    subject_id INT NOT NULL,
    semester VARCHAR(20) NOT NULL,
    division VARCHAR(10) NOT NULL,
    lecture_date DATE NOT NULL,
    lecture_time TIME NOT NULL,
    attendance_status ENUM('Present', 'Absent', 'Late', 'Medical Leave') NOT NULL,
    AI_confidence DECIMAL(5, 2) DEFAULT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    FOREIGN KEY (teacher_id) REFERENCES teachers(teacher_id) ON DELETE CASCADE,
    FOREIGN KEY (subject_id) REFERENCES subjects(subject_id) ON DELETE CASCADE,
    UNIQUE KEY idx_unique_student_lecture (student_id, lecture_date, subject_id, lecture_time),
    INDEX idx_att_date_status (lecture_date, attendance_status),
    INDEX idx_att_student (student_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 6. Notifications Table
CREATE TABLE notifications (
    notification_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20) NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
    status ENUM('Unread', 'Read') DEFAULT 'Unread',
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
    INDEX idx_notif_student (student_id, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 7. Dashboard Statistics Table
CREATE TABLE dashboard_stats (
    stat_id INT AUTO_INCREMENT PRIMARY KEY,
    total_students INT NOT NULL,
    total_teachers INT NOT NULL,
    todays_attendance_count INT NOT NULL,
    current_active_lecture VARCHAR(100) DEFAULT NULL,
    todays_total_classes INT NOT NULL,
    overall_attendance_pct DECIMAL(5, 2) NOT NULL,
    unknown_faces_count INT DEFAULT 0,
    students_below_75_pct INT NOT NULL,
    students_below_50_pct INT NOT NULL,
    students_below_40_pct INT NOT NULL,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 8. Face Embeddings Table
CREATE TABLE face_embeddings (
    embedding_id INT AUTO_INCREMENT PRIMARY KEY,
    student_id VARCHAR(20) NOT NULL UNIQUE,
    embedding_path VARCHAR(255) NOT NULL,
    vector_dimension INT DEFAULT 512,
    status ENUM('Active', 'Retraining', 'Archived') DEFAULT 'Active',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
