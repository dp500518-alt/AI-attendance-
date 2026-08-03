# AI Smart Attendance - Backend (Flask REST API & AI Engine)

The core REST API backend and AI engine for the AI Smart Attendance System powered by **Flask**, **OpenCV (YuNet + SFace)**, and **Ultralytics YOLOv8**.

## Architecture & Data Storage
- **Permanent Storage Root**: `D:\SmartAttendanceServer`
- **Database**: SQLite WAL Mode (`database/smart_attendance.db`)
- **AI Modules**:
  - Detection: `ai/recognition/camera.py`, `ai/recognition/recognize.py`
  - Classifier Training: `ai/training/train.py`, `ai/training/model_trainer.py`

## Running Backend Server

```bash
# Install dependencies
pip install -r requirements.txt

# Start REST API Server (port 5000)
python app.py
```
