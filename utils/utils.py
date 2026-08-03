import os
import csv
import io
import datetime
import config
import database

def export_attendance_to_csv(date_filter=None, dept_filter=None, search_term=None):
    """
    Generates a CSV file of attendance records based on filters.
    Returns (csv_filename, csv_string_content).
    """
    records = database.get_attendance_history(date_filter=date_filter, dept_filter=dept_filter, search_term=search_term)

    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(['Record ID', 'Student ID', 'Roll Number', 'Name', 'Department', 'Semester', 'Date', 'Time', 'Status'])

    for r in records:
        writer.writerow([
            r['id'],
            r['student_id'],
            r['roll_number'],
            r['name'],
            r['department'],
            r['semester'],
            r['date'],
            r['time'],
            r['status']
        ])

    csv_content = output.getvalue()
    output.close()

    # Save CSV copy in attendance/ directory
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"attendance_report_{timestamp}.csv"
    filepath = os.path.join(config.ATTENDANCE_DIR, filename)

    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        f.write(csv_content)

    return filename, csv_content

def get_system_info():
    """Returns general diagnostic and setup info."""
    students = database.get_all_students()
    embeddings = database.get_all_embeddings()
    stats = database.get_dashboard_stats()

    return {
        'total_students': len(students),
        'embedded_students': len(embeddings),
        'stats': stats,
        'dataset_dir': config.DATASET_DIR,
        'threshold': config.get_setting('recognition_threshold', config.RECOGNITION_THRESHOLD)
    }
