import os
import time
import urllib.request
import cv2
import numpy as np
import config

class FaceEngine:
    def __init__(self):
        self.yunet = None
        self.sface = None
        self.insight_app = None
        self.yolo_model = None
        self._init_models()

    def _ensure_model_file(self, url, file_path):
        if not os.path.exists(file_path):
            print(f"Downloading model file to {file_path}...")
            try:
                urllib.request.urlretrieve(url, file_path)
                print("Model download complete.")
            except Exception as e:
                print(f"Failed to download model from {url}: {e}")

    def _init_models(self):
        # 1. Try InsightFace if installed
        try:
            import insightface
            from insightface.app import FaceAnalysis
            self.insight_app = FaceAnalysis(name='buffalo_l', providers=['CPUExecutionProvider'])
            self.insight_app.prepare(ctx_id=0, det_size=(640, 640))
            print("InsightFace FaceAnalysis initialized successfully.")
            return
        except Exception as e:
            print(f"InsightFace initialization skipped or fallback needed: {e}")

        # 2. Try OpenCV YuNet + SFace (SOTA lightweight 128-d embedding)
        try:
            self._ensure_model_file(config.YUNET_MODEL_URL, config.YUNET_PATH)
            self._ensure_model_file(config.SFACE_MODEL_URL, config.SFACE_PATH)

            if os.path.exists(config.YUNET_PATH) and os.path.exists(config.SFACE_PATH):
                from hardware_manager import hardware_manager
                backend, target = hardware_manager.get_opencv_dnn_target_backend()

                self.yunet = cv2.FaceDetectorYN.create(
                    model=config.YUNET_PATH,
                    config="",
                    input_size=(320, 320),
                    score_threshold=0.6,
                    nms_threshold=0.3,
                    top_k=5000,
                    backend_id=backend,
                    target_id=target
                )
                self.sface = cv2.FaceRecognizerSF.create(
                    model=config.SFACE_PATH,
                    config="",
                    backend_id=backend,
                    target_id=target
                )
                active_target, provider = hardware_manager.resolve_inference_target()
                print(f"OpenCV YuNet & SFace models loaded successfully on {active_target} ({provider}).")
                return
        except Exception as e:
            print(f"OpenCV YuNet/SFace initialization error: {e}")

        # 3. Fallback Haar Cascade + SFace/Hist features if needed
        print("Using OpenCV Haar Cascade fallback face detector.")
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.haar_cascade = cv2.CascadeClassifier(cascade_path)

    def detect_and_extract(self, img_bgr):
        """
        Detects faces in img_bgr and extracts 128-d or 512-d normalized embedding for each face.
        Returns list of dicts:
        [{'bbox': (x, y, w, h), 'embedding': np_ndarray}, ...]
        """
        if img_bgr is None or img_bgr.size == 0:
            return []

        h, w, _ = img_bgr.shape
        results = []

        # A) InsightFace pipeline
        if self.insight_app is not None:
            try:
                faces = self.insight_app.get(img_bgr)
                for f in faces:
                    bbox = f.bbox.astype(int)  # [x1, y1, x2, y2]
                    x1, y1, x2, y2 = bbox[0], bbox[1], bbox[2], bbox[3]
                    bw, bh = x2 - x1, y2 - y1
                    emb = f.embedding
                    norm_emb = emb / (np.linalg.norm(emb) + 1e-10)
                    results.append({
                        'bbox': (max(0, x1), max(0, y1), max(1, bw), max(1, bh)),
                        'embedding': norm_emb
                    })
                return results
            except Exception as e:
                print(f"InsightFace inference error: {e}")

        # B) OpenCV YuNet + SFace pipeline
        if self.yunet is not None and self.sface is not None:
            try:
                self.yunet.setInputSize((w, h))
                _, faces = self.yunet.detect(img_bgr)

                if faces is not None:
                    for face in faces:
                        bbox = face[0:4].astype(int)
                        x, y, bw, bh = bbox[0], bbox[1], bbox[2], bbox[3]

                        # Align & crop face feature vector using SFace
                        aligned_face = self.sface.alignCrop(img_bgr, face)
                        feat = self.sface.feature(aligned_face)
                        feat = feat.flatten()
                        norm_feat = feat / (np.linalg.norm(feat) + 1e-10)

                        results.append({
                            'bbox': (max(0, x), max(0, y), max(1, bw), max(1, bh)),
                            'embedding': norm_feat
                        })
                
                # If YuNet detected faces, return results
                if results:
                    return results

                # Passport Photo Fallback for SFace: If YuNet found no faces (e.g. tightly cropped passport photo),
                # extract embedding directly from center/full image
                try:
                    aligned_face = cv2.resize(img_bgr, (112, 112))
                    feat = self.sface.feature(aligned_face).flatten()
                    norm_feat = feat / (np.linalg.norm(feat) + 1e-10)
                    return [{
                        'bbox': (0, 0, w, h),
                        'embedding': norm_feat
                    }]
                except Exception as ex_pf:
                    print(f"Passport fallback extraction error: {ex_pf}")
            except Exception as e:
                print(f"YuNet/SFace extraction error: {e}")

        # C) Haar Cascade fallback with Color Histogram / Raw Vector embedding
        if hasattr(self, 'haar_cascade'):
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            faces = self.haar_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
            for (x, y, bw, bh) in faces:
                face_roi = gray[y:y+bh, x:x+bw]
                face_resized = cv2.resize(face_roi, (64, 64))
                emb = face_resized.flatten().astype(np.float32)
                norm_emb = emb / (np.linalg.norm(emb) + 1e-10)
                results.append({
                    'bbox': (x, y, bw, bh),
                    'embedding': norm_emb
                })

        # Passport Photo Fallback for Haar Cascade / Raw feature
        if not results and img_bgr is not None and img_bgr.size > 0:
            gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
            face_resized = cv2.resize(gray, (64, 64))
            emb = face_resized.flatten().astype(np.float32)
            norm_emb = emb / (np.linalg.norm(emb) + 1e-10)
            results.append({
                'bbox': (0, 0, w, h),
                'embedding': norm_emb
            })

        return results

    @staticmethod
    def cosine_similarity(vec1, vec2):
        """Calculates cosine similarity between two 1D vectors."""
        vec1 = np.asarray(vec1, dtype=np.float32)
        vec2 = np.asarray(vec2, dtype=np.float32)

        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        # Standardize vector length if mismatch occurs
        if vec1.shape != vec2.shape:
            min_dim = min(vec1.shape[0], vec2.shape[0])
            vec1 = vec1[:min_dim]
            vec2 = vec2[:min_dim]
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def recognize_faces(self, img_bgr, known_embeddings, threshold=None):
        """
        Detects faces in img_bgr and predicts Student ID using trained SVM/MLP classifier.
        Hot-reloads classifier in-memory if face_classifier.pkl timestamp updates.
        Falls back to cosine similarity if classifier is unavailable.
        """
        t_start = time.time()
        if threshold is None:
            threshold = config.RECOGNITION_THRESHOLD

        detected_faces = self.detect_and_extract(img_bgr)
        matches = []

        # Check and hot-reload classifier if modified on disk
        self._check_and_reload_classifier()

        classifier = getattr(self, '_cached_classifier', None)
        label_encoder = getattr(self, '_cached_label_encoder', None)

        for face in detected_faces:
            emb = face['embedding']
            best_id = "Unknown"
            best_score = 0.0

            # 1. Use Trained Classifier (SVM / MLP) if available
            if classifier is not None and label_encoder is not None:
                try:
                    probs = classifier.predict_proba([emb])[0]
                    best_idx = np.argmax(probs)
                    score = float(probs[best_idx])

                    if score >= threshold:
                        predicted_id = label_encoder.inverse_transform([best_idx])[0]
                        best_id = str(predicted_id)
                        best_score = score
                    else:
                        best_id = "Unknown"
                        best_score = score
                except Exception as e_clf:
                    classifier = None

            # 2. Fallback to Cosine Similarity matching against DB embeddings
            if classifier is None:
                for student_id, known_emb in known_embeddings.items():
                    sim = self.cosine_similarity(emb, known_emb)
                    if sim > best_score:
                        best_score = sim
                        best_id = student_id

            is_matched = (best_score >= threshold) and (best_id != "Unknown")
            rec_time_ms = round((time.time() - t_start) * 1000, 2)

            matches.append({
                'bbox': face['bbox'],
                'student_id': best_id if is_matched else "Unknown",
                'similarity': round(best_score, 4),
                'confidence': round(best_score * 100, 1),
                'recognition_time_ms': rec_time_ms,
                'matched': is_matched
            })

        # Log recognition event & record latency in hardware_manager
        total_time_ms = round((time.time() - t_start) * 1000, 2)
        try:
            from hardware_manager import hardware_manager
            hardware_manager.record_inference_time(total_time_ms)

            from logger import recognition_logger
            matched_count = sum(1 for m in matches if m['matched'])
            recognition_logger.info(f"Processed {len(matches)} face(s), {matched_count} matched in {total_time_ms}ms on {hardware_manager.resolve_inference_target()[0]}")
        except Exception:
            pass

        return matches

    def reconfigure_hardware(self):
        """Re-initializes models with updated hardware execution provider targets."""
        print("Reconfiguring AI models for updated hardware target...")
        self._init_models()

    def _check_and_reload_classifier(self):
        """Hot-reloads classifier model if modified on disk without server restart."""
        try:
            from model_trainer import CLASSIFIER_PATH, load_classifier_and_encoder
            if not os.path.exists(CLASSIFIER_PATH):
                self._cached_classifier = None
                self._cached_label_encoder = None
                return

            mtime = os.path.getmtime(CLASSIFIER_PATH)
            last_mtime = getattr(self, '_last_model_mtime', 0)

            if mtime > last_mtime or getattr(self, '_cached_classifier', None) is None:
                clf, enc = load_classifier_and_encoder()
                if clf is not None and enc is not None:
                    self._cached_classifier = clf
                    self._cached_label_encoder = enc
                    self._last_model_mtime = mtime
                    print(f"Hot-reloaded trained AI classifier (mtime: {mtime}).")
        except Exception as e:
            print(f"Error checking/reloading classifier model: {e}")

    def annotate_image(self, img_bgr, recognition_results, student_names_map=None):
        """
        Draws green boxes & labels for matched students, red boxes for unknowns.
        """
        if student_names_map is None:
            student_names_map = {}

        annotated = img_bgr.copy()

        for res in recognition_results:
            (x, y, w, h) = res['bbox']
            student_id = res['student_id']
            sim = res['similarity']
            matched = res['matched']

            color = (0, 220, 0) if matched else (0, 0, 220)  # Green for matched, Red for unknown
            display_name = student_names_map.get(student_id, student_id)

            if matched:
                label = f"{display_name} ({int(sim * 100)}%)"
            else:
                label = f"Unknown ({int(sim * 100)}%)"

            # Draw rectangle
            cv2.rectangle(annotated, (x, y), (x + w, y + h), color, 2)

            # Draw label box
            text_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(annotated, (x, max(0, y - 25)), (x + text_size[0] + 10, max(0, y)), color, -1)
            cv2.putText(annotated, label, (x + 5, max(15, y - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)

        return annotated

# Global Singleton Instance
face_engine = FaceEngine()
