import os
import time
import json
import pickle
import threading
import datetime
import cv2
import numpy as np
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, precision_recall_fscore_support, confusion_matrix
from sklearn.model_selection import train_test_split

import config
import database
from recognize import face_engine

# Path configurations for trained model artifacts
MODEL_DIR = config.MODELS_DIR
CLASSIFIER_PATH = os.path.join(MODEL_DIR, 'face_classifier.pkl')
LABEL_ENCODER_PATH = os.path.join(MODEL_DIR, 'label_encoder.pkl')
METADATA_PATH = os.path.join(MODEL_DIR, 'training_metadata.json')
DATE_FILE_PATH = os.path.join(MODEL_DIR, 'training_date.txt')

try:
    os.makedirs(MODEL_DIR, exist_ok=True)
except Exception as e:
    print(f"MODEL_DIR creation notice: {e}")


def augment_image(img_bgr, target_count=20):
    """
    Generates at least target_count augmented face image variations from 1 input photo.
    Applies: Rotation, Brightness, Contrast, Zoom, Translation, Gaussian Blur, Noise, Gamma, Color Jitter.
    CRITICAL: Never flips images horizontally.
    """
    if img_bgr is None or img_bgr.size == 0:
        return []

    h, w = img_bgr.shape[:2]
    augmented = []
    
    # Always include original image as sample 0
    augmented.append(img_bgr.copy())

    # 1. Rotation variations (-15 deg to +15 deg)
    angles = [-15, -10, -5, 5, 10, 15]
    for angle in angles:
        M = cv2.getRotationMatrix2D((w / 2, h / 2), angle, 1.0)
        rotated = cv2.warpAffine(img_bgr, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
        augmented.append(rotated)

    # 2. Brightness & Contrast variations
    brightness_factors = [0.75, 0.85, 1.15, 1.25]
    for bf in brightness_factors:
        b_img = cv2.convertScaleAbs(img_bgr, alpha=bf, beta=0)
        augmented.append(b_img)

    contrast_factors = [0.8, 1.2, 1.35]
    for cf in contrast_factors:
        c_img = cv2.convertScaleAbs(img_bgr, alpha=cf, beta=10)
        augmented.append(c_img)

    # 3. Slight Zoom / Scale (0.9 to 1.1)
    for scale in [0.92, 1.08]:
        nw, nh = int(w * scale), int(h * scale)
        resized = cv2.resize(img_bgr, (nw, nh))
        if scale > 1.0:
            # Crop center
            cx, cy = (nw - w) // 2, (nh - h) // 2
            z_img = resized[cy:cy + h, cx:cx + w]
        else:
            # Pad border
            top, bottom = (h - nh) // 2, h - nh - (h - nh) // 2
            left, right = (w - nw) // 2, w - nw - (w - nw) // 2
            z_img = cv2.copyMakeBorder(resized, top, bottom, left, right, cv2.BORDER_REPLICATE)
        augmented.append(cv2.resize(z_img, (w, h)))

    # 4. Translation / Shift
    shifts = [(-10, 0), (10, 0), (0, -10), (0, 10), (8, 8), (-8, -8)]
    for dx, dy in shifts:
        M = np.float32([[1, 0, dx], [0, 1, dy]])
        shifted = cv2.warpAffine(img_bgr, M, (w, h), borderMode=cv2.BORDER_REPLICATE)
        augmented.append(shifted)

    # 5. Gaussian Blur & Noise
    blur_img = cv2.GaussianBlur(img_bgr, (5, 5), 0)
    augmented.append(blur_img)

    # Add Gaussian Noise
    noise = np.random.normal(0, 8, img_bgr.shape).astype(np.float32)
    noisy_img = np.clip(img_bgr.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    augmented.append(noisy_img)

    # 6. Gamma Correction
    for gamma in [0.7, 1.4]:
        invGamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** invGamma) * 255 for i in np.arange(0, 256)]).astype("uint8")
        g_img = cv2.LUT(img_bgr, table)
        augmented.append(g_img)

    # 7. Color Jitter (HSV adjustments)
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
    hsv[:, :, 1] = np.clip(hsv[:, :, 1] * 1.2, 0, 255) # Saturation
    hsv_img = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR)
    augmented.append(hsv_img)

    # Trim or ensure we have at least target_count images
    return augmented[:max(target_count, len(augmented))]


class BackgroundTrainer:
    def __init__(self):
        self._lock = threading.Lock()
        self.is_training = False
        self.progress = 0
        self.status_message = "Idle"
        self.logs = []
        self.last_metadata = None

    def log(self, message):
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        print(entry)
        try:
            from logger import training_logger
            training_logger.info(message)
        except Exception:
            pass
        with self._lock:
            self.logs.append(entry)
            if len(self.logs) > 200:
                self.logs.pop(0)

    def set_status(self, progress, status_message):
        with self._lock:
            self.progress = progress
            self.status_message = status_message

    def get_status(self):
        with self._lock:
            meta = load_training_metadata()
            return {
                'is_training': self.is_training,
                'progress': self.progress,
                'status_message': self.status_message,
                'metadata': meta
            }

    def get_logs(self):
        with self._lock:
            return list(self.logs)

    def start_training_async(self):
        if self.is_training:
            return False, "Training is already in progress."

        if os.environ.get('VERCEL'):
            # On Vercel serverless, run synchronously to complete before function response finishes
            self._run_pipeline()
            return True, "Model training completed."
        else:
            thread = threading.Thread(target=self._run_pipeline, daemon=True)
            thread.start()
            return True, "Background model training started."

    def _run_pipeline(self):
        with self._lock:
            self.is_training = True
            self.progress = 0
            self.status_message = "Starting model training..."
            self.logs.clear()

        start_time = time.time()
        try:
            self.log("Initializing database and fetching registered students...")
            database.init_db()
            students = database.get_all_students()

            if not students:
                self.log("Error: No registered students found in database.")
                self.set_status(100, "Failed: No students registered.")
                return

            total_students = len(students)
            self.log(f"Found {total_students} student(s) for face model training.")
            self.set_status(10, "Fetching student photos and performing augmentation...")

            X_embeddings = []
            y_labels = []
            student_names_map = {}

            total_original_images = 0
            total_augmented_images = 0

            for idx, student in enumerate(students):
                sid = student['id']
                sname = student.get('name', sid)
                student_names_map[sid] = sname

                # Load photos from disk or DB
                student_dir = os.path.join(config.DATASET_DIR, str(sid))
                image_files = []
                if os.path.exists(student_dir):
                    image_files = [os.path.join(student_dir, f) for f in os.listdir(student_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]

                raw_photos = []
                for fpath in image_files:
                    img = cv2.imread(fpath)
                    if img is not None and img.size > 0:
                        raw_photos.append(img)

                # Fallback to DB photos if disk is empty
                if not raw_photos:
                    db_photos = database.get_student_photos(sid)
                    if db_photos:
                        from camera import decode_base64_image
                        for b64 in db_photos:
                            img = decode_base64_image(b64)
                            if img is not None and img.size > 0:
                                raw_photos.append(img)

                if not raw_photos:
                    self.log(f"Warning: No photos found for student {sid} ({sname}). Skipping.")
                    continue

                total_original_images += len(raw_photos)
                self.log(f"Processing student {sid} ({sname}): {len(raw_photos)} original photo(s)...")

                # Perform Augmentation for each photo
                student_embeddings = []
                for p_idx, raw_img in enumerate(raw_photos):
                    aug_images = augment_image(raw_img, target_count=20)
                    total_augmented_images += len(aug_images)

                    for aug_img in aug_images:
                        extracted = face_engine.detect_and_extract(aug_img)
                        if extracted:
                            # Largest face
                            largest = max(extracted, key=lambda f: f['bbox'][2] * f['bbox'][3])
                            emb = largest['embedding']
                            student_embeddings.append(emb)

                if not student_embeddings:
                    self.log(f"Warning: Could not extract face embeddings for student {sid}. Skipping.")
                    continue

                for emb in student_embeddings:
                    X_embeddings.append(emb)
                    y_labels.append(str(sid))

                # Update progress
                pct = int(10 + (idx + 1) / total_students * 50)
                self.set_status(pct, f"Extracted embeddings for {idx + 1}/{total_students} students...")

            if not X_embeddings:
                self.log("Error: No valid face embeddings extracted across all students.")
                self.set_status(100, "Failed: No valid face embeddings.")
                return

            X = np.array(X_embeddings, dtype=np.float32)
            y = np.array(y_labels)

            self.log(f"Total extracted embeddings: {len(X)} across {len(set(y))} unique student(s).")
            self.set_status(65, "Encoding labels and preparing classifier training...")

            # Encode Labels
            label_encoder = LabelEncoder()
            y_encoded = label_encoder.fit_transform(y)
            num_classes = len(label_encoder.classes_)

            self.log(f"Fitting classifier model for {num_classes} student class(es)...")

            # Train/Validation Split for Metrics
            if len(X) >= 4 and num_classes >= 2:
                try:
                    X_train, X_val, y_train, y_val = train_test_split(
                        X, y_encoded, test_size=0.25, random_state=42, stratify=y_encoded
                    )
                except Exception:
                    X_train, X_val, y_train, y_val = train_test_split(X, y_encoded, test_size=0.25, random_state=42)
            else:
                X_train, X_val, y_train, y_val = X, X, y_encoded, y_encoded

            # Preferred Model: SVM with RBF Kernel
            self.set_status(75, "Training SVM (RBF Kernel) Classifier...")
            model_type = "SVM (RBF Kernel)"
            
            try:
                if num_classes >= 2:
                    from sklearn.calibration import CalibratedClassifierCV
                    base_svc = SVC(C=10.0, kernel='rbf', gamma='scale', random_state=42)
                    try:
                        classifier = CalibratedClassifierCV(base_svc, cv=3)
                        classifier.fit(X_train, y_train)
                    except Exception:
                        classifier = SVC(C=10.0, kernel='rbf', probability=True, gamma='scale', random_state=42)
                        classifier.fit(X_train, y_train)
                else:
                    # Single class fallback: train MLP Classifier fallback
                    self.log("Single student registered. Training MLP Classifier fallback...")
                    classifier = MLPClassifier(hidden_layer_sizes=(128, 64), max_iter=400, random_state=42)
                    classifier.fit(X_train, y_train)
                    model_type = "MLP Classifier"
            except Exception as e_svm:
                self.log(f"SVM training error ({e_svm}). Falling back to MLP Classifier...")
                classifier = MLPClassifier(hidden_layer_sizes=(128, 64), max_iter=400, random_state=42)
                classifier.fit(X_train, y_train)
                model_type = "MLP Classifier"

            self.set_status(85, "Calculating model evaluation metrics...")

            # Evaluate Metrics
            y_val_pred = classifier.predict(X_val)
            acc = float(accuracy_score(y_val, y_val_pred))
            prec, rec, f1, _ = precision_recall_fscore_support(y_val, y_val_pred, average='weighted', zero_division=0)

            # Confusion Matrix calculation
            cm = confusion_matrix(y_val, y_val_pred)
            class_names = [str(c) for c in label_encoder.classes_]
            cm_dict = {
                'labels': [student_names_map.get(c, c) for c in class_names],
                'matrix': cm.tolist()
            }

            training_time = round(time.time() - start_time, 2)
            now_str = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            metadata = {
                'model_type': model_type,
                'total_students': total_students,
                'trained_students': len(set(y)),
                'total_original_images': total_original_images,
                'total_augmented_images': total_augmented_images,
                'total_embeddings': len(X),
                'accuracy': round(acc * 100, 2),
                'precision': round(float(prec) * 100, 2),
                'recall': round(float(rec) * 100, 2),
                'f1_score': round(float(f1) * 100, 2),
                'training_time_seconds': training_time,
                'training_date': now_str,
                'confusion_matrix': cm_dict,
                'student_names': student_names_map
            }

            self.set_status(95, "Saving trained model artifacts...")

            # Save PKL and metadata files
            with open(CLASSIFIER_PATH, 'wb') as f:
                pickle.dump(classifier, f)

            with open(LABEL_ENCODER_PATH, 'wb') as f:
                pickle.dump(label_encoder, f)

            with open(METADATA_PATH, 'w') as f:
                json.dump(metadata, f, indent=2)

            with open(DATE_FILE_PATH, 'w') as f:
                f.write(now_str)

            # Also persist mean embeddings into DB for backup cosine similarity matching
            for sid in set(y):
                indices = np.where(y == sid)[0]
                mean_emb = np.mean(X[indices], axis=0)
                norm = np.linalg.norm(mean_emb)
                if norm > 0:
                    mean_emb = mean_emb / norm
                database.save_embedding(str(sid), mean_emb)

            self.log(f"Model training finished successfully in {training_time}s! Accuracy: {metadata['accuracy']}%.")
            self.set_status(100, f"Completed: Accuracy {metadata['accuracy']}% ({model_type})")

        except Exception as e:
            self.log(f"Fatal error during model training: {e}")
            import traceback
            self.log(traceback.format_exc())
            self.set_status(100, f"Error: {e}")

        finally:
            with self._lock:
                self.is_training = False


# Global Trainer Singleton
trainer = BackgroundTrainer()


def load_training_metadata():
    """Loads metadata JSON or returns default empty structure."""
    meta_path = METADATA_PATH
    if not os.path.exists(meta_path) and os.path.exists(os.path.join(config.REPO_MODELS_DIR, 'training_metadata.json')):
        meta_path = os.path.join(config.REPO_MODELS_DIR, 'training_metadata.json')

    if os.path.exists(meta_path):
        try:
            with open(meta_path, 'r') as f:
                return json.load(f)
        except Exception:
            pass

    return {
        'model_type': 'None',
        'total_students': 0,
        'trained_students': 0,
        'total_original_images': 0,
        'total_augmented_images': 0,
        'total_embeddings': 0,
        'accuracy': 0.0,
        'precision': 0.0,
        'recall': 0.0,
        'f1_score': 0.0,
        'training_time_seconds': 0.0,
        'training_date': 'Not Trained',
        'confusion_matrix': {'labels': [], 'matrix': []}
    }


def load_classifier_and_encoder():
    """Loads trained SVM/MLP classifier and LabelEncoder if available."""
    clf_path = CLASSIFIER_PATH
    lbl_path = LABEL_ENCODER_PATH

    if not os.path.exists(clf_path) and os.path.exists(os.path.join(config.REPO_MODELS_DIR, 'face_classifier.pkl')):
        clf_path = os.path.join(config.REPO_MODELS_DIR, 'face_classifier.pkl')

    if not os.path.exists(lbl_path) and os.path.exists(os.path.join(config.REPO_MODELS_DIR, 'label_encoder.pkl')):
        lbl_path = os.path.join(config.REPO_MODELS_DIR, 'label_encoder.pkl')

    if os.path.exists(clf_path) and os.path.exists(lbl_path):
        try:
            with open(clf_path, 'rb') as f:
                classifier = pickle.load(f)
            with open(lbl_path, 'rb') as f:
                label_encoder = pickle.load(f)
            return classifier, label_encoder
        except Exception as e:
            print(f"Error loading trained classifier: {e}")

    return None, None


def delete_model_artifacts():
    """Deletes saved model files to reset trained classifier."""
    for p in [CLASSIFIER_PATH, LABEL_ENCODER_PATH, METADATA_PATH, DATE_FILE_PATH]:
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception as e:
                print(f"Error removing {p}: {e}")
    return True
