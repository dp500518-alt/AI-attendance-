import os
import cv2
import datetime
import config
import database
from recognize import face_engine
from camera import encode_bgr_to_base64

def process_classroom_image(img_bgr, custom_threshold=None):
    """
    Processes a classroom photo (multi-face):
    1. Saves original photo to captured/
    2. Retrieves known embeddings from DB
    3. Runs multi-face recognition
    4. Annotates image with green (matched) and red (unknown) bounding boxes
    5. Marks attendance for recognized students in SQLite DB
    6. Returns structured summary and annotated image
    """
    if img_bgr is None or img_bgr.size == 0:
        return False, "Invalid image data provided.", None

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    date_today = datetime.datetime.now().strftime("%Y-%m-%d")
    time_now = datetime.datetime.now().strftime("%H:%M:%S")

    # 1. Save raw classroom photo
    raw_filename = f"classroom_{timestamp}.jpg"
    raw_filepath = os.path.join(config.CAPTURED_DIR, raw_filename)
    cv2.imwrite(raw_filepath, img_bgr)

    # 2. Get embeddings & student lookup map
    known_embeddings = database.get_all_embeddings()
    all_students = database.get_all_students()
    student_map = {s['id']: s for s in all_students}
    student_names = {s['id']: f"{s['name']} ({s['roll_number']})" for s in all_students}

    # 3. Multi-face recognition
    threshold = custom_threshold if custom_threshold is not None else config.RECOGNITION_THRESHOLD
    recognition_results = face_engine.recognize_faces(img_bgr, known_embeddings, threshold=threshold)

    # 4. Annotate image
    annotated_bgr = face_engine.annotate_image(img_bgr, recognition_results, student_names_map=student_names)
    annotated_filename = f"annotated_{timestamp}.jpg"
    annotated_filepath = os.path.join(config.CAPTURED_DIR, annotated_filename)
    cv2.imwrite(annotated_filepath, annotated_bgr)

    # 5. Mark Attendance for recognized students
    marked_present = []
    already_marked = []
    unknown_count = 0

    for res in recognition_results:
        sid = res['student_id']
        matched = res['matched']
        sim = res['similarity']

        if matched and sid in student_map:
            inserted = database.mark_attendance(sid, status='Present', date_str=date_today, time_str=time_now)
            student_info = student_map[sid]
            record = {
                'student_id': sid,
                'name': student_info['name'],
                'roll_number': student_info['roll_number'],
                'department': student_info['department'],
                'semester': student_info['semester'],
                'confidence': f"{int(sim * 100)}%",
                'status': 'Present',
                'is_new': inserted
            }
            if inserted:
                marked_present.append(record)
            else:
                already_marked.append(record)
        else:
            unknown_count += 1

    # Encode annotated image to base64 for immediate UI rendering
    annotated_b64 = encode_bgr_to_base64(annotated_bgr)

    summary = {
        'timestamp': timestamp,
        'date': date_today,
        'time': time_now,
        'total_detected': len(recognition_results),
        'newly_marked_present': marked_present,
        'already_marked_present': already_marked,
        'unknown_count': unknown_count,
        'annotated_image_b64': annotated_b64,
        'raw_filename': raw_filename,
        'annotated_filename': annotated_filename
    }

    msg = f"Processed classroom photo: {len(marked_present)} newly marked present, {len(already_marked)} already marked, {unknown_count} unknown faces."
    return True, msg, summary
