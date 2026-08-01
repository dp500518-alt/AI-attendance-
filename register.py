import os
import cv2
import config
import database
from camera import decode_base64_image
from train import generate_embedding_for_student

def register_new_student(student_id, roll_number, name, department, semester, sample_images_b64=None, division='Division A', email='', phone=''):
    """
    Registers student in DB, creates dataset/<student_id>/ directory,
    saves captured face samples, and triggers face embedding generation.
    """
    student_id = str(student_id).strip()
    roll_number = str(roll_number).strip()
    name = str(name).strip()
    department = str(department).strip()
    semester = str(semester).strip()
    division = str(division).strip()
    email = str(email).strip()
    phone = str(phone).strip()

    if not student_id or not roll_number or not name:
        return False, "Student ID, Roll Number, and Name are required."

    # Check duplicate
    existing_student = database.get_student(student_id)
    if existing_student:
        return False, f"Student with ID '{student_id}' already exists."

    # Create dataset folder
    student_dir = os.path.join(config.DATASET_DIR, student_id)
    os.makedirs(student_dir, exist_ok=True)

    saved_count = 0

    # Save images to disk and DB if provided
    if sample_images_b64:
        for idx, img_b64 in enumerate(sample_images_b64):
            try:
                img_bgr = decode_base64_image(img_b64)
                if img_bgr is not None and img_bgr.size > 0:
                    filename = f"sample_{idx + 1:02d}.jpg"
                    filepath = os.path.join(student_dir, filename)
                    cv2.imwrite(filepath, img_bgr)
                    saved_count += 1
            except Exception as e:
                print(f"Error saving image sample {idx}: {e}")
        
        # Persist photos inside SQLite database table for permanent container survival
        try:
            database.save_student_photos(student_id, sample_images_b64)
        except Exception as e:
            print(f"Error saving photos to DB: {e}")

    # Add student entry to Database
    try:
        database.add_student(student_id, roll_number, name, department, semester, division, email, phone)
    except Exception as e:
        return False, f"Database insertion failed: {e}"

    # Sync snapshot JSON seed for permanent repo/cloud persistence
    database.sync_backup_seed()

    # Generate Embeddings if sample photos saved
    embedding_msg = ""
    if saved_count > 0:
        success, msg = generate_embedding_for_student(student_id)
        embedding_msg = f" Embeddings: {msg}" if success else f" Warning: {msg}"

    return True, f"Student '{name}' registered successfully with {saved_count} photos.{embedding_msg}"
