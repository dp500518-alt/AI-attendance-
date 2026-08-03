import os
import shutil

# config.py lives in backend/config/ — go up one level to get the backend root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# ONNX model files live in the repo root models/ folder (d:\smart\models\)
REPO_MODELS_DIR = os.path.join(os.path.dirname(BASE_DIR), 'models')

# Storage Root Selection:
#   Windows local PC  → D:\SmartAttendanceServer
#   Vercel/serverless → /tmp/smart_attendance_data  (only writable path)
#   Render/other Linux→ backend/data
if os.name == 'nt' and os.path.exists('D:\\'):
    DEFAULT_PERMANENT_ROOT = r'D:\SmartAttendanceServer'
elif os.path.isdir('/tmp'):
    # Vercel and most serverless platforms: /tmp is the only writable directory
    DEFAULT_PERMANENT_ROOT = '/tmp/smart_attendance_data'
else:
    DEFAULT_PERMANENT_ROOT = os.path.join(BASE_DIR, 'data')

DATA_DIR = os.environ.get('DATA_DIR', DEFAULT_PERMANENT_ROOT)
try:
    os.makedirs(DATA_DIR, exist_ok=True)
except Exception as e:
    print(f"Notice: Could not create {DATA_DIR} ({e}), falling back to /tmp.")
    DATA_DIR = '/tmp/smart_attendance_data'
    os.makedirs(DATA_DIR, exist_ok=True)

# Core Local Permanent Directories inside D:\SmartAttendanceServer
MODELS_DIR = os.path.join(DATA_DIR, 'models')
DATASET_DIR = os.path.join(DATA_DIR, 'dataset')
EMBEDDINGS_DIR = os.path.join(DATA_DIR, 'embeddings')
CAPTURED_DIR = os.path.join(DATA_DIR, 'captured')
ATTENDANCE_DIR = os.path.join(DATA_DIR, 'attendance')
DB_DIR = os.path.join(DATA_DIR, 'database')
LOGS_DIR = os.path.join(DATA_DIR, 'logs')
BACKUPS_DIR = os.path.join(DATA_DIR, 'backups')
TRAINING_DIR = os.path.join(DATA_DIR, 'training')
UPLOADS_DIR = os.path.join(DATA_DIR, 'uploads')
DB_PATH = os.path.join(DB_DIR, 'smart_attendance.db')

# Specific Rotated Log File Paths
DATABASE_LOG_PATH = os.path.join(LOGS_DIR, 'database.log')
SERVER_LOG_PATH = os.path.join(LOGS_DIR, 'server.log')
RECOGNITION_LOG_PATH = os.path.join(LOGS_DIR, 'recognition.log')
TRAINING_LOG_PATH = os.path.join(LOGS_DIR, 'training.log')
BACKUP_LOG_PATH = os.path.join(LOGS_DIR, 'backup.log')
ATTENDANCE_LOG_PATH = os.path.join(LOGS_DIR, 'attendance.log')
ERRORS_LOG_PATH = os.path.join(LOGS_DIR, 'errors.log')
REGISTRATION_LOG_PATH = os.path.join(LOGS_DIR, 'registration.log')

# Create necessary directories
ALL_DIRS = [DATA_DIR, DATASET_DIR, EMBEDDINGS_DIR, CAPTURED_DIR, ATTENDANCE_DIR, DB_DIR, MODELS_DIR, LOGS_DIR, BACKUPS_DIR, TRAINING_DIR, UPLOADS_DIR]
for path in ALL_DIRS:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"Directory creation notice for {path}: {e}")

def auto_migrate_legacy_data():
    r"""
    Safely migrates legacy data from project workspace into D:\SmartAttendanceServer\
    if it exists and has not yet been copied. Never deletes workspace originals.
    """
    if DATA_DIR == BASE_DIR:
        return  # Same directory, no migration needed

    migrations = [
        (os.path.join(BASE_DIR, 'database'), DB_DIR),
        (os.path.join(BASE_DIR, 'dataset'), DATASET_DIR),
        (os.path.join(BASE_DIR, 'embeddings'), EMBEDDINGS_DIR),
        (os.path.join(BASE_DIR, 'models'), MODELS_DIR),
    ]

    for src_dir, dest_dir in migrations:
        if os.path.exists(src_dir) and os.path.isdir(src_dir):
            for root, dirs, files in os.walk(src_dir):
                rel_path = os.path.relpath(root, src_dir)
                target_root = os.path.join(dest_dir, rel_path) if rel_path != '.' else dest_dir
                os.makedirs(target_root, exist_ok=True)
                for file in files:
                    src_file = os.path.join(root, file)
                    dest_file = os.path.join(target_root, file)
                    if not os.path.exists(dest_file):
                        try:
                            shutil.copy2(src_file, dest_file)
                            print(f"[Migration] Copied {file} -> {target_root}")
                        except Exception as err:
                            print(f"[Migration Error] Could not copy {file}: {err}")

# Trigger automatic migration on import
try:
    auto_migrate_legacy_data()
except Exception as e:
    print(f"Auto-migration notice: {e}")

# Face Recognition Settings
RECOGNITION_THRESHOLD = 0.50  # Cosine similarity threshold for matching
MIN_FACE_SIZE = (40, 40)
SAMPLE_PHOTO_COUNT = 25

# Security & App Settings
SECRET_KEY = os.environ.get('SECRET_KEY', 'smart-attendance-secret-key-2026')
DEFAULT_ADMIN_USER = os.environ.get('ADMIN_USER', 'admin')
DEFAULT_ADMIN_PASS = os.environ.get('ADMIN_PASS', 'admin123')
CAMERA_INDEX = int(os.environ.get('CAMERA_INDEX', 0))

# Model URLs for auto-download (YuNet & SFace ONNX models)
YUNET_MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
SFACE_MODEL_URL = "https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx"

YUNET_PATH = os.path.join(MODELS_DIR, 'face_detection_yunet_2023mar.onnx')
if not os.path.exists(YUNET_PATH) and os.path.exists(os.path.join(REPO_MODELS_DIR, 'face_detection_yunet_2023mar.onnx')):
    YUNET_PATH = os.path.join(REPO_MODELS_DIR, 'face_detection_yunet_2023mar.onnx')

SFACE_PATH = os.path.join(MODELS_DIR, 'face_recognition_sface_2021dec.onnx')
if not os.path.exists(SFACE_PATH) and os.path.exists(os.path.join(REPO_MODELS_DIR, 'face_recognition_sface_2021dec.onnx')):
    SFACE_PATH = os.path.join(REPO_MODELS_DIR, 'face_recognition_sface_2021dec.onnx')

YOLO_MODEL_PATH = os.path.join(MODELS_DIR, 'yolov8n.pt')
if not os.path.exists(YOLO_MODEL_PATH) and os.path.exists(os.path.join(REPO_MODELS_DIR, 'yolov8n.pt')):
    YOLO_MODEL_PATH = os.path.join(REPO_MODELS_DIR, 'yolov8n.pt')
