import os
import shutil
import logging
import config

logger = logging.getLogger("storage_manager")

class StorageManager:
    """
    100% Local PC Permanent Storage Manager for Smart Attendance System.
    Stores all datasets, models, embeddings, logs, and SQLite database directly inside D:\\SmartAttendanceServer.
    """
    def __init__(self):
        self.data_dir = config.DATA_DIR
        self._ensure_directories()

    def _ensure_directories(self):
        """Creates all 10 local permanent subdirectories inside D:\\SmartAttendanceServer."""
        for d in config.ALL_DIRS:
            try:
                os.makedirs(d, exist_ok=True)
            except Exception as e:
                logger.error(f"Error creating local directory {d}: {e}")

    def is_object_storage_connected(self):
        """Local application mode active."""
        return False

    def persist_student_photo(self, student_id, filename, image_bytes_or_bgr):
        """Saves student face sample photo directly to D:\\SmartAttendanceServer\\dataset\\<student_id>\\."""
        student_dir = os.path.join(config.DATASET_DIR, str(student_id))
        os.makedirs(student_dir, exist_ok=True)
        local_filepath = os.path.join(student_dir, filename)

        if isinstance(image_bytes_or_bgr, bytes):
            with open(local_filepath, 'wb') as f:
                f.write(image_bytes_or_bgr)
        else:
            import cv2
            cv2.imwrite(local_filepath, image_bytes_or_bgr)
        return True

    def persist_model_artifact(self, artifact_filename):
        """Verifies trained classifier model artifact exists in D:\\SmartAttendanceServer\\models\\."""
        local_path = os.path.join(config.MODELS_DIR, artifact_filename)
        return os.path.exists(local_path)

    def restore_model_artifact(self, artifact_filename):
        """Ensures model artifact is available in D:\\SmartAttendanceServer\\models\\."""
        dest_path = os.path.join(config.MODELS_DIR, artifact_filename)
        if not os.path.exists(dest_path) and os.path.exists(os.path.join(config.REPO_MODELS_DIR, artifact_filename)):
            try:
                shutil.copy2(os.path.join(config.REPO_MODELS_DIR, artifact_filename), dest_path)
            except Exception:
                pass
        return os.path.exists(dest_path)

    def reconnect_and_sync(self):
        """
        Executed on app startup. Ensures local directories, SQLite database,
        datasets, embeddings, and models in D:\\SmartAttendanceServer are ready.
        """
        self._ensure_directories()
        import database
        db_status = database.check_db_integrity()
        logger.info(f"100% Local Storage initialized at {config.DATA_DIR}. DB Status: {db_status.get('status')}")

storage_manager = StorageManager()
