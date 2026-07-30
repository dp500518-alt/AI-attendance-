import os
import cv2
import numpy as np
import config
import database
from recognize import face_engine

def generate_embedding_for_student(student_id):
    """
    Scans dataset/<student_id>/ folder, extracts embeddings from all images,
    computes normalized mean embedding vector, and updates SQLite DB.
    """
    student_dir = os.path.join(config.DATASET_DIR, str(student_id))
    if not os.path.exists(student_dir):
        print(f"Dataset directory for student {student_id} not found: {student_dir}")
        return False, "Dataset directory not found."

    image_files = [f for f in os.listdir(student_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    if not image_files:
        print(f"No face images found in {student_dir}")
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

    # Save backup serialization file in embeddings/
    backup_file = os.path.join(config.EMBEDDINGS_DIR, f"{student_id}.npy")
    np.save(backup_file, mean_embedding)

    print(f"Successfully generated embedding for {student_id} from {processed_count} images.")
    return True, f"Generated embedding from {processed_count} photos."

def train_all_students():
    """
    Re-generates embeddings for all student folders in dataset/ directory.
    """
    students = database.get_all_students()
    results = {}

    for s in students:
        sid = s['id']
        success, msg = generate_embedding_for_student(sid)
        results[sid] = {'success': success, 'message': msg}

    return results

if __name__ == '__main__':
    database.init_db()
    print("Training embeddings for all registered students...")
    res = train_all_students()
    print("Training finished:", res)
