import os
import cv2
import numpy as np
import config
import database
from recognize import face_engine

def generate_embedding_for_student(student_id):
    """
    Scans dataset/<student_id>/ folder (or loads photos from SQLite DB),
    extracts embeddings from all images, computes normalized mean embedding vector, and updates SQLite DB.
    """
    student_id = str(student_id).strip()
    student_dir = os.path.join(config.DATASET_DIR, student_id)
    os.makedirs(student_dir, exist_ok=True)

    image_files = [f for f in os.listdir(student_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    
    # Auto-restore from StudentPhotos table in SQLite if disk folder is missing/empty
    if not image_files:
        db_photos = database.get_student_photos(student_id)
        if db_photos:
            from camera import decode_base64_image
            for idx, b64_str in enumerate(db_photos):
                try:
                    img = decode_base64_image(b64_str)
                    if img is not None and img.size > 0:
                        fname = f"sample_{idx+1:02d}.jpg"
                        fpath = os.path.join(student_dir, fname)
                        cv2.imwrite(fpath, img)
                except Exception as e:
                    print(f"Error restoring photo sample {idx} from DB: {e}")
            image_files = [f for f in os.listdir(student_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

    if not image_files:
        print(f"No face images found for student {student_id} on disk or database.")
        return False, "No face images found."

    embeddings = []
    processed_count = 0

    for img_name in image_files:
        img_path = os.path.join(student_dir, img_name)
        img_bgr = cv2.imread(img_path)
        if img_bgr is None:
            continue

        faces = face_engine.detect_and_extract(img_bgr)
        if faces:
            # Use largest detected face in photo
            largest_face = max(faces, key=lambda f: f['bbox'][2] * f['bbox'][3])
            embeddings.append(largest_face['embedding'])
            processed_count += 1

    if not embeddings:
        return False, f"Could not detect valid faces in the dataset photos for {student_id}."

    # Compute mean embedding vector and normalize
    mean_embedding = np.mean(embeddings, axis=0)
    norm = np.linalg.norm(mean_embedding)
    if norm > 0:
        mean_embedding = mean_embedding / norm

    # Save to SQLite database
    database.save_embedding(str(student_id), mean_embedding)

    # Save backup serialization file in embeddings/ and persistent storage
    backup_file = os.path.join(config.EMBEDDINGS_DIR, f"{student_id}.npy")
    np.save(backup_file, mean_embedding)
    try:
        from storage_manager import storage_manager
        storage_manager.upload_file(backup_file, f"embeddings/{student_id}.npy")
    except Exception as e:
        print(f"Notice: Could not persist embedding for {student_id} to object storage: {e}")

    print(f"Successfully generated embedding for {student_id} from {processed_count} images.")
    return True, f"Generated embedding from {processed_count} photos."

def train_all_students():
    """
    Re-generates embeddings for all students and triggers full background classifier training.
    """
    from model_trainer import trainer
    database.init_db()
    students = database.get_all_students()
    results = {}

    for s in students:
        sid = s['id']
        success, msg = generate_embedding_for_student(sid)
        results[sid] = {'success': success, 'message': msg}

    # Trigger background model training pipeline
    started, train_msg = trainer.start_training_async()
    print(f"Background Classifier Training: {train_msg}")

    return results

if __name__ == '__main__':
    database.init_db()
    print("Training embeddings and classifier model for all registered students...")
    res = train_all_students()
    print("Embedding generation finished:", res)
