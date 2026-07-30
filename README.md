# Smart Attendance AI - Face Recognition Attendance System

A production-grade, AI-powered Smart Attendance System built with Python 3.12+, Flask, OpenCV, InsightFace/YuNet/SFace face recognition embeddings, SQLite database, and a responsive Bootstrap 5 dashboard.

![Smart Attendance System](https://img.shields.io/badge/Python-3.12+-blue.svg)
![Framework](https://img.shields.io/badge/Flask-3.0-green.svg)
![AI-Vision](https://img.shields.io/badge/OpenCV-YuNet%20%2F%20SFace-orange.svg)

---

## Features

1. **Student Registration**:
   - Register students with Student ID, Roll Number, Name, Department, and Semester.
   - Live webcam feed capturing 25 high-quality face sample photos automatically.
   - Stored in `dataset/<StudentID>/`.

2. **AI Face Embedding Generation**:
   - Computes normalized 128-d / 512-d floating point feature vectors for each student.
   - Cosine Similarity vector matching for high accuracy.
   - Automatically prevents duplicate student registrations.

3. **Multi-Face Classroom Attendance**:
   - Upload a single classroom photo OR capture a picture via webcam.
   - Detects all visible faces in the classroom picture simultaneously.
   - Annotates output image with **Green Bounding Boxes** for recognized enrolled students and **Red Bounding Boxes** for unknown individuals.
   - Prevents duplicate attendance marking for the same student on the same day.

4. **Interactive Responsive Dashboard**:
   - Real-time statistics: Total Students, Present Today, Absent Today, Attendance Rate (%).
   - Today's live attendance activity log table.
   - Quick action shortcuts.

5. **Security & System Management**:
   - Admin authentication with bcrypt/werkzeug password hashing.
   - Session management.
   - Customizable Cosine Similarity confidence threshold.
   - One-click embedding re-training.
   - Dark Mode UI toggle.

6. **Attendance History & Export**:
   - Filter logs by date range, department, or student name/ID.
   - One-click instant CSV export download.

---

## Project Structure

```
SmartAttendance/
├── app.py                  # Flask web backend & API endpoints
├── config.py               # Path configurations & recognition parameters
├── camera.py               # OpenCV VideoCapture & Base64 decoding
├── register.py             # Student registration & dataset photo capture
├── recognize.py            # AI Face Engine (Detection & Cosine Similarity Embeddings)
├── attendance.py           # Multi-face classroom photo recognition logic
├── database.py             # SQLite helper (Students, Attendance, Embeddings, Users)
├── train.py                # Embedding trainer from dataset images
├── utils.py                # CSV exporter & system diagnostics
├── requirements.txt        # Python dependency manifest
├── dataset/                # Student face photo dataset
├── embeddings/             # Serialized backup embedding files (.npy)
├── captured/               # Uploaded classroom photos & annotated results
├── attendance/             # Exported attendance CSV files
├── database/               # SQLite database file (smart_attendance.db)
├── models/                 # Pre-trained ONNX YuNet & SFace AI models
├── static/
│   ├── css/
│   │   └── style.css       # Glassmorphic CSS design system & Dark Mode variables
│   └── js/
│       └── app.js          # Webcam capture JavaScript & UI state handlers
└── templates/              # Jinja2 HTML5 views
    ├── base.html           # Base layout with sidebar & dark mode toggle
    ├── login.html          # Admin Login page
    ├── index.html          # Dashboard (Stats, metrics & quick actions)
    ├── register.html       # Student Registration & batch webcam photo capture
    ├── classroom.html      # Classroom photo upload & live capture attendance
    ├── history.html        # Filterable attendance logs & CSV report download
    ├── students.html       # Student directory & management
    └── settings.html       # System settings, threshold tuning & admin password
```

---

## Installation & Setup

### 1. Prerequisites
- Python 3.12 or newer installed on your system.
- Standard webcam (optional for live webcam capture).

### 2. Install Dependencies
Open a command prompt or terminal in the project folder and run:

```bash
pip install -r requirements.txt
```

### 3. Run Application
Start the Flask web application:

```bash
python app.py
```

Open your browser and navigate to:
**http://127.0.0.1:5000**

---

## Default Credentials

- **Username**: `admin`
- **Password**: `admin123`

*(You can change the admin password at any time in the **System Settings** page).*

---

## Workflow Guide

1. **Register Students**:
   - Go to **Register Student**.
   - Enter Student ID, Roll No, Name, Department, and Semester.
   - Click **Start Camera** and then **Capture 25 Photos**.
   - Click **Save Student & Train Embeddings**.

2. **Take Attendance**:
   - Go to **Classroom Photo**.
   - Upload a photo of the classroom OR click **Snap Classroom Photo** using the webcam.
   - The AI will automatically detect all visible faces, draw green boxes around recognized students, red boxes around strangers/unknowns, and record attendance for today!

3. **View & Export**:
   - View real-time stats on the **Dashboard**.
   - Go to **Attendance Log** to filter records and click **Download CSV Report**.

---

## Tech Stack & AI Algorithms

- **Backend**: Flask 3.0, SQLite3, Werkzeug
- **AI Vision**: OpenCV (`cv2.FaceDetectorYN`, `cv2.FaceRecognizerSF`), InsightFace, NumPy
- **Embedding Alignment**: SFace / ArcFace 128-d normalized vector representation
- **Matching Metric**: Cosine Similarity:
  $$\text{Similarity}(\mathbf{u}, \mathbf{v}) = \frac{\mathbf{u} \cdot \mathbf{v}}{\|\mathbf{u}\|_2 \|\mathbf{v}\|_2}$$
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5, Bootstrap Icons
