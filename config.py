import os
import shutil

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_MODELS_DIR = os.path.join(BASE_DIR, 'models')

def is_container_environment():
    """
    Detects whether the app is running locally or in a container/serverless environment.
    Checks environment variables and container runtime indicator files.
    """
    if os.environ.get('STORAGE_MODE') == 'container':
        return True
    if os.environ.get('STORAGE_MODE') == 'local':
        return False

    env_indicators = [
        'IS_CONTAINER', 'CONTAINER', 'DOCKER_CONTAINER', 'VERCEL',
        'KUBERNETES_SERVICE_HOST', 'CONTAINER_ENV', 'RENDER', 'RAILWAY_STATIC_URL', 'HEROKU_APP_ID'
    ]
    for env in env_indicators:
        if os.environ.get(env):
            return True

    if os.path.exists('/.dockerenv') or os.path.exists('/run/.containerenv'):
        return True

    try:
        if os.path.exists('/proc/1/cgroup'):
            with open('/proc/1/cgroup', 'r') as f:
                content = f.read()
                if 'docker' in content or 'kubepods' in content or 'containerd' in content:
                    return True
    except Exception:
        pass

    return False

IS_CONTAINER_ENV = is_container_environment()

# Data directory handling: Container Environment vs Permanent Local Host Storage
if IS_CONTAINER_ENV:
    # Never use /tmp for permanent data in container environments
    DEFAULT_CONTAINER_ROOT = os.environ.get('PERSISTENT_STORAGE_PATH', os.path.join(BASE_DIR, 'persistent_data'))
    DATA_DIR = os.environ.get('DATA_DIR', DEFAULT_CONTAINER_ROOT)
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception:
        DATA_DIR = os.path.join(BASE_DIR, 'persistent_data')
        os.makedirs(DATA_DIR, exist_ok=True)
else:
    DEFAULT_PERMANENT_ROOT = r'D:\SmartAttendanceServer'
    try:
        os.makedirs(DEFAULT_PERMANENT_ROOT, exist_ok=True)
        DATA_DIR = os.environ.get('DATA_DIR', DEFAULT_PERMANENT_ROOT)
    except Exception as e:
        print(f"Notice: Could not access {DEFAULT_PERMANENT_ROOT} ({e}), falling back to BASE_DIR.")
        DATA_DIR = os.environ.get('DATA_DIR', BASE_DIR)

# Persistent Database & Object Storage Configurations
DATABASE_URL = os.environ.get('DATABASE_URL') or os.environ.get('POSTGRES_URL') or os.environ.get('SQLITE_PATH')
S3_BUCKET = os.environ.get('S3_BUCKET', os.environ.get('AWS_S3_BUCKET', 'smart-attendance-storage'))
S3_ENDPOINT = os.environ.get('S3_ENDPOINT', os.environ.get('AWS_ENDPOINT_URL', ''))
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# Core Permanent Directories
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
