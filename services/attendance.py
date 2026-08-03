import os
import cv2
import datetime
import config
import database
from recognize import face_engine
from camera import encode_bgr_to_base64

def process_classroom_image(img_bgr, custom_threshold=None, manual_slot=None, teacher_username=None, slot_id=None):
    """
    Wrapper for single classroom photo attendance processing.
    """
    if img_bgr is None or img_bgr.size == 0:
        return False, "Invalid image data provided.", None
    return process_multiple_classroom_images([img_bgr], custom_threshold, manual_slot, teacher_username, slot_id)

def process_multiple_classroom_images(img_bgr_list, custom_threshold=None, manual_slot=None, teacher_username=None, slot_id=None):
    """
    Intelligent Multi-Photo Classroom Attendance Processor:
    1. Determines current timestamp & day of week.
    2. Queries active timetable slot automatically (or accepts slot_id / manual_slot).
    3. Scopes candidate embeddings ONLY to students enrolled in target Semester & Division.
    4. Runs multi-face recognition across ALL provided photos (e.g. Left, Center, Right of room).
    5. Saves attendance bound to timetable_id, subject, semester, division, and teacher.
    6. Aggregates recognized faces so students in ANY photo are marked Present once.
    7. Triggers low-attendance notification if student falls below 50%.
    """
    if not img_bgr_list:
        return False, "No valid images provided.", None

    valid_imgs = [img for img in img_bgr_list if img is not None and img.size > 0]
    if not valid_imgs:
        return False, "Invalid image data provided.", None

    now = datetime.datetime.now()
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    date_today = now.strftime("%Y-%m-%d")
    time_now = now.strftime("%H:%M:%S")
    day_name = now.strftime("%A")
    time_hm = now.strftime("%H:%M")

    # 1. Active Timetable Slot Auto-Detection
    active_slot = manual_slot or database.get_active_timetable_slot(
        teacher_username=teacher_username,
        day_of_week=day_name,
        time_str=time_hm,
        slot_id=slot_id
    )

    target_sem = active_slot.get('semester') if active_slot else None
    target_div = active_slot.get('division') if active_slot else None
    subject_name = active_slot.get('subject_name') if active_slot else 'General Attendance Session'
    timetable_id = active_slot.get('id') if active_slot else None
    teacher_name = (active_slot.get('teacher_name') or active_slot.get('teacher_username')) if active_slot else (teacher_username or 'Faculty')
    room_number = active_slot.get('room_number') if active_slot else 'N/A'

    # 2. Retrieve student embeddings filtered by target Semester & Division
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
    threshold = custom_threshold if custom_threshold is not None else config.RECOGNITION_THRESHOLD

    marked_present = []
    already_marked = []
    seen_student_ids = set()
    annotated_images_info = []
    total_detected = 0
    total_unknown = 0

    for idx, img_bgr in enumerate(valid_imgs):
        sub_ts = f"{timestamp}_{idx+1}"
        raw_filename = f"classroom_{sub_ts}.jpg"
        raw_filepath = os.path.join(config.CAPTURED_DIR, raw_filename)
        cv2.imwrite(raw_filepath, img_bgr)

        # Multi-face recognition on frame
        recognition_results = face_engine.recognize_faces(img_bgr, known_embeddings, threshold=threshold)
        total_detected += len(recognition_results)

        # Annotate image
        annotated_bgr = face_engine.annotate_image(img_bgr, recognition_results, student_names_map=student_names)
        annotated_filename = f"annotated_{sub_ts}.jpg"
        annotated_filepath = os.path.join(config.CAPTURED_DIR, annotated_filename)
        cv2.imwrite(annotated_filepath, annotated_bgr)

        annotated_b64 = encode_bgr_to_base64(annotated_bgr)
        annotated_images_info.append({
            'index': idx + 1,
            'filename': annotated_filename,
            'b64': annotated_b64,
            'detected_count': len(recognition_results)
        })

        for res in recognition_results:
            sid = res['student_id']
            matched = res['matched']
            sim = res['similarity']

            if matched and sid in student_map:
                if sid not in seen_student_ids:
                    seen_student_ids.add(sid)
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

                    check_and_notify_student_attendance(sid, student_info['name'])
            else:
                total_unknown += 1

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
        'room_number': room_number,
        'total_detected': total_detected,
        'newly_marked_present': marked_present,
        'already_marked_present': already_marked,
        'unknown_count': total_unknown,
        'annotated_images': annotated_images_info,
        'annotated_image_b64': annotated_images_info[0]['b64'] if annotated_images_info else '',
        'photos_processed_count': len(valid_imgs)
    }

    photo_label = "photo" if len(valid_imgs) == 1 else "photos"
    if active_slot:
        msg = f"Zero-Input AI Context Active: Processed {len(valid_imgs)} classroom {photo_label} for '{subject_name}' ({target_sem}, {target_div}) | Faculty: {teacher_name} | Room: {room_number}."
    else:
        msg = f"General Attendance Mode Active: Processed {len(valid_imgs)} classroom {photo_label}. Matched faces across registered students."

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


def mark_attendance(student_id, status='Present', subject_name='General Lecture', teacher_name=None, confidence=0.0):
    """
    Marks attendance for a single student in SQLite DB and triggers short attendance warnings if applicable.
    """
    student = database.get_student(student_id)
    sem = student.get('semester') if student else None
    div = student.get('division') if student else None

    inserted = database.mark_attendance(
        student_id=student_id,
        status=status,
        subject_name=subject_name,
        semester=sem,
        division=div
    )
    if student and inserted:
        try:
            check_and_notify_student_attendance(student_id, student.get('name', 'Student'))
        except Exception:
            pass
    return inserted


