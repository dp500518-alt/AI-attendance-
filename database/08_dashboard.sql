USE smart_attendance_db;

INSERT INTO dashboard_stats (
    total_students, 
    total_teachers, 
    todays_attendance_count, 
    current_active_lecture, 
    todays_total_classes, 
    overall_attendance_pct, 
    unknown_faces_count, 
    students_below_75_pct, 
    students_below_50_pct, 
    students_below_40_pct
) VALUES (
    900,
    100,
    742,
    'DSP Lecture (Semester 4, Division B)',
    48,
    85.19,
    2,
    213,
    81,
    6
);
