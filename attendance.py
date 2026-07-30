import os
import cv2
import datetime
import config
import database
from recognize import face_engine
from camera import encode_bgr_to_base64

def process_classroom_image(img_bgr, custom_threshold=None, manual_slot=None):
    """
    Intelligent Classroom Photo Attendance Processor:
    1. Determines current timestamp & day of week.
    2. Queries active timetable slot or accepts manual slot override.
    3. Scopes candidate embeddings ONLY to students enrolled in target Semester & Division.
    4. Runs face recognition.
    5. Saves attendance bound to timetable_id, subject, semester, and division.
    6. Triggers low-attendance notification if student falls below 50%.
    """
    if img_bgr is None or img_bgr.size == 0:
        return False, "Invalid image data provided.", None

    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    date_today = now.strftime("%Y-%m-%d")
    time_now = now.strftime("%H:%M:%S")
    day_name = now.strftime("%A")
    time_hm = now.strftime("%H:%M")

    # 1. Active Timetable Slot Detection
    active_slot = manual_slot or database.get_active_timetable_slot(day_of_week=day_name, time_str=time_hm)

    target_sem = active_slot.get('semester') if active_slot else None
    target_div = active_slot.get('division') if active_slot else None
    subject_name = active_slot.get('subject_name') if active_slot else 'General Classroom'
    timetable_id = active_slot.get('id') if active_slot else None
    teacher_name = active_slot.get('teacher_name') or active_slot.get('teacher_username') if active_slot else None

    # 2. Save raw classroom photo
    raw_filename = f"classroom_{timestamp}.jpg"
    raw_filepath = os.path.join(config.CAPTURED_DIR, raw_filename)
    cv2.imwrite(raw_filepath, img_bgr)

    # 3. Retrieve student embeddings filtered by target Semester & Division if active slot detected
    all_embeddings = database.get_all_embeddings()

    if target_sem and target_div:
        candidate_students = database.get_students_by_sem_div(semester=target_sem, division=target_div)
        candidate_ids = {s['id'] for s in candidate_students}
        known_embeddings = {sid: vec for sid, vec in all_embeddings.items() if sid in candidate_ids}
        all_students = candidate_students
    else:
        known_embeddings = all_embeddings
        all_students = database.get_all_students()

    student_map = {s['id']: s for s in all_students}
    student_names = {s['id']: f"{s['name']} ({s['roll_number']})" for s in all_students}

    # 4. Multi-face recognition
    threshold = custom_threshold if custom_threshold is not None else config.RECOGNITION_THRESHOLD
    recognition_results = face_engine.recognize_faces(img_bgr, known_embeddings, threshold=threshold)

    # 5. Annotate image
    annotated_bgr = face_engine.annotate_image(img_bgr, recognition_results, student_names_map=student_names)
    annotated_filename = f"annotated_{timestamp}.jpg"
    annotated_filepath = os.path.join(config.CAPTURED_DIR, annotated_filename)
    cv2.imwrite(annotated_filepath, annotated_bgr)

    # 6. Mark Attendance for recognized scoped students
    marked_present = []
    already_marked = []
    unknown_count = 0

    for res in recognition_results:
        sid = res['student_id']
        matched = res['matched']
        sim = res['similarity']

        if matched and sid in student_map:
            student_info = student_map[sid]
            sem_val = target_sem or student_info['semester']
            div_val = target_div or student_info.get('division', 'Division A')

            inserted = database.mark_attendance(
                student_id=sid,
                status='Present',
                date_str=date_today,
                time_str=time_now,
                timetable_id=timetable_id,
                subject_name=subject_name,
                semester=sem_val,
                division=div_val
            )

            record = {
                'student_id': sid,
                'name': student_info['name'],
                'roll_number': student_info['roll_number'],
                'department': student_info['department'],
                'semester': sem_val,
                'division': div_val,
                'subject': subject_name,
                'confidence': f"{int(sim * 100)}%",
                'status': 'Present',
                'is_new': inserted
            }

            if inserted:
                marked_present.append(record)
            else:
                already_marked.append(record)

            # Check low attendance warning threshold
            check_and_notify_student_attendance(sid, student_info['name'])
        else:
            unknown_count += 1

    annotated_b64 = encode_bgr_to_base64(annotated_bgr)

    summary = {
        'timestamp': timestamp,
        'date': date_today,
        'time': time_now,
        'day': day_name,
        'active_slot': active_slot,
        'subject_name': subject_name,
        'semester': target_sem or 'All Semesters',
        'division': target_div or 'All Divisions',
        'teacher_name': teacher_name,
        'total_detected': len(recognition_results),
        'newly_marked_present': marked_present,
        'already_marked_present': already_marked,
        'unknown_count': unknown_count,
        'annotated_image_b64': annotated_b64,
        'raw_filename': raw_filename,
        'annotated_filename': annotated_filename
    }

    if active_slot:
        msg = f"Auto-detected lecture '{subject_name}' ({target_sem} {target_div}). Marked {len(marked_present)} present, {len(already_marked)} already marked."
    else:
        msg = f"Processed classroom photo: {len(marked_present)} newly marked present, {len(already_marked)} already marked."

    return True, msg, summary

def check_and_notify_student_attendance(student_id, student_name):
    """
    Checks if student attendance falls below 50% and automatically issues warning notifications.
    """
    summary = database.get_student_attendance_summary(student_id)
    total_conducted = max(1, summary['total_attended'])
    pct = round((summary['total_attended'] / total_conducted) * 100, 1)

    if pct < 50.0:
        title = "Short Attendance Warning!"
        msg = f"Warning: Your attendance has fallen to {pct}%. Please attend upcoming lectures."
        database.create_notification(target_user=student_id, title=title, message=msg, channel="website")

