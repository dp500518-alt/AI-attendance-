import os
import cv2
import traceback
import config
import database
from logger import registration_logger
from camera import decode_base64_image
from train import generate_embedding_for_student

def register_new_student(student_id, roll_number, name, department, semester, sample_images_b64=None, division='Division A', email='', phone=''):
    """
    Registers student in SQLite database, creates dataset/<student_id>/ directory,
    saves captured face samples (disk + SQLite StudentPhotos), generates and saves face embeddings,
    verifies database integrity and persistence at every step, and logs all events to registration.log.
    """
    student_id = str(student_id).strip()
    roll_number = str(roll_number).strip()
    name = str(name).strip()
    department = str(department).strip()
    semester = str(semester).strip()
    division = str(division).strip()
    email = str(email).strip()
    phone = str(phone).strip()

    registration_logger.info(f"=== [Registration Started] Student ID: {student_id}, Roll No: {roll_number}, Name: {name}, Dept: {department}, Sem: {semester}, Div: {division} ===")

    # Step 1: Input Validation
    if not student_id or not roll_number or not name:
        err_msg = "Validation failed: Student ID, Roll Number, and Name are required."
        registration_logger.error(f"[Step 1 Failed] {err_msg}")
        return False, err_msg

    # Check for duplicates in SQLite Students table
    try:
        existing_student = database.get_student(student_id)
        if existing_student:
            err_msg = f"Student with ID '{student_id}' already exists."
            registration_logger.warning(f"[Step 1 Check] {err_msg}")
            return False, err_msg
    except Exception as e:
        err_msg = f"Database query error during duplicate check: {e}"
        registration_logger.error(f"[Step 1 Error] {err_msg}\n{traceback.format_exc()}")
        return False, err_msg

    # Step 2 & 3: Insert Student in SQLite & Commit & Verify
    try:
        database.add_student(student_id, roll_number, name, department, semester, division, email, phone)
        registration_logger.info(f"[Step 2 & 3 Passed] Student '{student_id}' ({name}) successfully inserted and verified in SQLite Students table.")
    except Exception as e:
        err_msg = f"Student insertion into SQLite database failed: {e}"
        registration_logger.error(f"[Step 2/3 Failed] {err_msg}\n{traceback.format_exc()}")
        return False, err_msg

    # Step 4: Create Dataset Folder
    student_dir = os.path.join(config.DATASET_DIR, student_id)
    try:
        os.makedirs(student_dir, exist_ok=True)
        registration_logger.info(f"[Step 4 Passed] Dataset folder created at: {student_dir}")
    except Exception as e:
        err_msg = f"Could not create dataset directory at {student_dir}: {e}"
        registration_logger.error(f"[Step 4 Failed] {err_msg}\n{traceback.format_exc()}")
        return False, err_msg

    # Step 5 & 6: Save and Verify Captured Images on Local Disk (D:\SmartAttendanceServer\dataset\<student_id>\)
    saved_count = 0
    if sample_images_b64:
        for idx, img_b64 in enumerate(sample_images_b64):
            try:
                img_bgr = decode_base64_image(img_b64)
                if img_bgr is not None and img_bgr.size > 0:
                    filename = f"sample_{idx + 1:02d}.jpg"
                    filepath = os.path.join(student_dir, filename)
                    cv2.imwrite(filepath, img_bgr)
                    if os.path.exists(filepath):
                        saved_count += 1
            except Exception as e:
                registration_logger.error(f"[Step 5 Image Error] Error saving sample {idx} for {student_id}: {e}")

        registration_logger.info(f"[Step 5 & 6 Passed] {saved_count} / {len(sample_images_b64)} image files saved and verified in {student_dir}")

        # Step 7: Save photos into SQLite StudentPhotos table for permanent backup
        try:
            database.save_student_photos(student_id, sample_images_b64)
            registration_logger.info(f"[Step 7 Passed] {saved_count} photos stored in SQLite StudentPhotos table.")
        except Exception as e:
            registration_logger.error(f"[Step 7 Error] Failed saving photos to StudentPhotos table: {e}\n{traceback.format_exc()}")
            return False, f"Failed saving student photos to database: {e}"

    # Step 8, 9 & 10: Generate and Verify Embeddings
    embedding_msg = ""
    if saved_count > 0:
        try:
            success, msg = generate_embedding_for_student(student_id)
            if not success:
                err_msg = f"Embedding generation failed: {msg}"
                registration_logger.error(f"[Step 8/9/10 Failed] {err_msg}")
                return False, err_msg

            # Verify embedding vector exists in SQLite Embeddings table
            emb = database.get_student_embedding(student_id)
            if emb is None:
                err_msg = f"Embedding verification failed for student ID '{student_id}' in SQLite Embeddings table."
                registration_logger.error(f"[Step 10 Failed] {err_msg}")
                return False, err_msg

            registration_logger.info(f"[Step 8, 9, 10 Passed] Face embedding vector generated and verified for student '{student_id}'.")
            embedding_msg = f" Embeddings: {msg}"
        except Exception as e:
            err_msg = f"Embedding generation/verification exception: {e}"
            registration_logger.error(f"[Step 8/9/10 Error] {err_msg}\n{traceback.format_exc()}")
            return False, err_msg

        # Trigger automatic background classifier model retraining
        try:
            from model_trainer import trainer
            trainer.start_training_async()
            registration_logger.info("[Background Training] AI Model Retraining initiated in background.")
            embedding_msg += " (Background AI Training initiated)"
        except Exception as e_tr:
            registration_logger.error(f"Error launching background trainer: {e_tr}")

    # Step 11: Sync backup seed and verify DB integrity
    database.sync_backup_seed()
    integ = database.check_db_integrity()
    if integ.get('status') != 'healthy':
        err_msg = f"Database integrity check failed after registration: {integ.get('message')}"
        registration_logger.critical(f"[Step 11 Failed] {err_msg}")
        return False, err_msg

    final_msg = f"Student '{name}' (ID: {student_id}) registered successfully with {saved_count} photos.{embedding_msg}"
    registration_logger.info(f"=== [Registration Completed] {final_msg} ===")
    return True, final_msg
