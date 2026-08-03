import os
import shutil
import json
import logging
import config

logger = logging.getLogger("storage_manager")

class StorageManager:
    """
    Unified Persistent Storage Manager supporting Persistent Object Storage (S3 / MinIO / Cloud Object Storage)
    and SQL DB persistence for student face images, trained models, and face embeddings.
    Ensures data is never stored in temporary /tmp directories and is reconnected/synced on startup.
    """
    def __init__(self):
        self.bucket = config.S3_BUCKET
        self.s3_client = None
        self.use_s3 = False
        self._init_object_storage()

    def _init_object_storage(self):
        """Initializes S3/MinIO client if credentials and boto3 are available."""
        if config.AWS_ACCESS_KEY_ID and config.AWS_SECRET_ACCESS_KEY:
            try:
                import boto3
                kwargs = {
                    'aws_access_key_id': config.AWS_ACCESS_KEY_ID,
                    'aws_secret_access_key': config.AWS_SECRET_ACCESS_KEY,
                    'region_name': config.AWS_REGION
                }
                if config.S3_ENDPOINT:
                    kwargs['endpoint_url'] = config.S3_ENDPOINT

                self.s3_client = boto3.client('s3', **kwargs)
                self.use_s3 = True
                logger.info(f"Connected to S3 Persistent Object Storage bucket '{self.bucket}'")
            except Exception as e:
                logger.warning(f"Could not initialize S3 client ({e}). Falling back to persistent volume storage.")
                self.use_s3 = False

    def is_object_storage_connected(self):
        """Returns True if object storage is connected and active."""
        if self.use_s3 and self.s3_client:
            try:
                self.s3_client.head_bucket(Bucket=self.bucket)
                return True
            except Exception:
                return False
        return True # Persistent volume active

    def upload_file(self, local_path, object_key):
        """Uploads a local file to persistent object storage."""
        if not os.path.exists(local_path):
            return False

        if self.use_s3 and self.s3_client:
            try:
                self.s3_client.upload_file(local_path, self.bucket, object_key)
                logger.info(f"Uploaded {local_path} -> s3://{self.bucket}/{object_key}")
                return True
            except Exception as e:
                logger.error(f"S3 upload error for {object_key}: {e}")

        # Fallback to persistent volume storage
        persistent_dest = os.path.join(config.DATA_DIR, object_key)
        os.makedirs(os.path.dirname(persistent_dest), exist_ok=True)
        if local_path != persistent_dest:
            try:
                shutil.copy2(local_path, persistent_dest)
                logger.info(f"Persisted file {local_path} -> {persistent_dest}")
                return True
            except Exception as e:
                logger.error(f"Persistent copy error: {e}")
        return False

    def download_file(self, object_key, destination_path):
        """Downloads an object from persistent object storage to destination path."""
        os.makedirs(os.path.dirname(destination_path), exist_ok=True)

        if self.use_s3 and self.s3_client:
            try:
                self.s3_client.download_file(self.bucket, object_key, destination_path)
                logger.info(f"Downloaded s3://{self.bucket}/{object_key} -> {destination_path}")
                return True
            except Exception as e:
                logger.debug(f"S3 download notice for {object_key}: {e}")

        persistent_src = os.path.join(config.DATA_DIR, object_key)
        if os.path.exists(persistent_src) and persistent_src != destination_path:
            try:
                shutil.copy2(persistent_src, destination_path)
                logger.info(f"Loaded persistent file {persistent_src} -> {destination_path}")
                return True
            except Exception as e:
                logger.error(f"Persistent load error: {e}")
        
        return os.path.exists(destination_path)

    def persist_student_photo(self, student_id, filename, image_bytes_or_bgr):
        """
        Saves student face sample photo to persistent object storage.
        Accepts either image bytes or BGR numpy array.
        """
        student_dir = os.path.join(config.DATASET_DIR, str(student_id))
        os.makedirs(student_dir, exist_ok=True)
        local_filepath = os.path.join(student_dir, filename)

        if isinstance(image_bytes_or_bgr, bytes):
            with open(local_filepath, 'wb') as f:
                f.write(image_bytes_or_bgr)
        else:
            import cv2
            cv2.imwrite(local_filepath, image_bytes_or_bgr)

        object_key = f"dataset/{student_id}/{filename}"
        return self.upload_file(local_filepath, object_key)

    def persist_model_artifact(self, artifact_filename):
        """Persists trained classifier model file (pkl/json) to persistent storage."""
        local_path = os.path.join(config.MODELS_DIR, artifact_filename)
        if os.path.exists(local_path):
            object_key = f"models/{artifact_filename}"
            return self.upload_file(local_path, object_key)
        return False

    def restore_model_artifact(self, artifact_filename):
        """Restores trained classifier model file from persistent storage if missing locally."""
        dest_path = os.path.join(config.MODELS_DIR, artifact_filename)
        if not os.path.exists(dest_path):
            object_key = f"models/{artifact_filename}"
            return self.download_file(object_key, dest_path)
        return True

    def reconnect_and_sync(self):
        """
        Executed on app startup. Connects to persistent DB and Object Storage,
        and syncs trained models, embeddings, and dataset files into working memory.
        """
        logger.info(f"Reconnecting to persistent storage at {config.DATA_DIR}...")
        
        # 1. Re-initialize and test persistent database connection
        import database
        db_status = database.check_db_integrity()
        logger.info(f"Persistent SQL Database connection status: {db_status.get('status')}")

        # 2. Restore trained model artifacts from persistent storage if missing
        model_artifacts = ['face_classifier.pkl', 'label_encoder.pkl', 'training_metadata.json', 'training_date.txt']
        for artifact in model_artifacts:
            self.restore_model_artifact(artifact)

        # 3. Restore student dataset photos from SQL StudentPhotos table if dataset folder is missing
        try:
            students = database.get_all_students()
            for student in students:
                sid = student['id']
                student_dir = os.path.join(config.DATASET_DIR, str(sid))
                if not os.path.exists(student_dir) or not os.listdir(student_dir):
                    photos = database.get_student_photos(sid)
                    if photos:
                        os.makedirs(student_dir, exist_ok=True)
                        from camera import decode_base64_image
                        import cv2
                        for idx, b64_str in enumerate(photos):
                            img = decode_base64_image(b64_str)
                            if img is not None and img.size > 0:
                                fname = f"sample_{idx+1:02d}.jpg"
                                cv2.imwrite(os.path.join(student_dir, fname), img)
                        logger.info(f"Restored {len(photos)} photos for student {sid} from persistent SQL database.")
        except Exception as e:
            logger.error(f"Error restoring student dataset photos on startup: {e}")

        logger.info("Storage reconnect and sync pipeline completed successfully.")

storage_manager = StorageManager()
