import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_MODELS_DIR = os.path.join(BASE_DIR, 'models')

# Data directory handling: Permanent 24/7 Local Storage vs Vercel Serverless
if os.environ.get('VERCEL'):
    DATA_DIR = os.environ.get('DATA_DIR', '/tmp/SmartAttendanceData')
else:
    DEFAULT_PERMANENT_ROOT = r'D:\SmartAttendanceServer'
    try:
        os.makedirs(DEFAULT_PERMANENT_ROOT, exist_ok=True)
        DATA_DIR = os.environ.get('DATA_DIR', DEFAULT_PERMANENT_ROOT)
    except Exception as e:
        print(f"Notice: Could not access {DEFAULT_PERMANENT_ROOT} ({e}), falling back to BASE_DIR.")
        DATA_DIR = os.environ.get('DATA_DIR', BASE_DIR)

MODELS_DIR = os.path.join(DATA_DIR, 'models')
DATASET_DIR = os.path.join(DATA_DIR, 'dataset')
EMBEDDINGS_DIR = os.path.join(DATA_DIR, 'embeddings')
CAPTURED_DIR = os.path.join(DATA_DIR, 'captured')
ATTENDANCE_DIR = os.path.join(DATA_DIR, 'attendance')
DB_DIR = os.path.join(DATA_DIR, 'database')
LOGS_DIR = os.path.join(DATA_DIR, 'logs')
BACKUPS_DIR = os.path.join(DATA_DIR, 'backups')
TRAINING_DIR = os.path.join(DATA_DIR, 'training')
DB_PATH = os.path.join(DB_DIR, 'smart_attendance.db')

# Create necessary directories
for path in [DATA_DIR, DATASET_DIR, EMBEDDINGS_DIR, CAPTURED_DIR, ATTENDANCE_DIR, DB_DIR, MODELS_DIR, LOGS_DIR, BACKUPS_DIR, TRAINING_DIR]:
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        print(f"Directory creation notice for {path}: {e}")

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
