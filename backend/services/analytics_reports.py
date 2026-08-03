import os
import io
import datetime
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import database

def generate_analytics_data(date_from=None, date_to=None, sem=None, div=None, subject=None):
    """
    Computes comprehensive attendance analytics:
    1. Overall summary counters
    2. Trend data for Line Chart (Daily attendance counts)
    3. Distribution data for Pie Chart (Good >75%, Warning 50-75%, Critical <50%)
    4. Subject breakdown for Bar Chart
    5. Weekday distribution for Heatmap grid
    """
    records = database.get_attendance_history(date_filter=date_from, sem_filter=sem, div_filter=div, subject_filter=subject)
    students = database.get_all_students()

    total_students = len(students) or 1
    total_records = len(records)

    # 1. Daily trend (Line Chart)
    daily_counts = {}
    for r in records:
        d = r['date']
        daily_counts[d] = daily_counts.get(d, 0) + 1

    sorted_dates = sorted(daily_counts.keys())
    trend_labels = sorted_dates[-14:] # Last 14 days
    trend_values = [daily_counts[d] for d in trend_labels]

    # 2. Subject-wise breakdown (Bar Chart)
    subject_counts = {}
    for r in records:
        subj = r.get('subject_name') or 'General'
        subject_counts[subj] = subject_counts.get(subj, 0) + 1

    bar_labels = list(subject_counts.keys())
    bar_values = list(subject_counts.values())

    # 3. Status Distribution (Pie Chart)
    low_list = database.get_short_attendance_students(threshold=50.0)
    critical_cnt = len(low_list)

    # Calculate status buckets for all students
    good_cnt = 0
    warning_cnt = 0
    total_dates = len(sorted_dates) or 1

    for s in students:
        sid = s['id']
        att_cnt = sum(1 for r in records if r['student_id'] == sid)
        pct = round((att_cnt / total_dates) * 100, 1)
        if pct < 50.0:
            pass # counted in critical
        elif pct <= 75.0:
            warning_cnt += 1
        else:
            good_cnt += 1

    pie_labels = ['Good (>75%)', 'Warning (50-75%)', 'Critical (<50%)']
    pie_values = [good_cnt, warning_cnt, critical_cnt]

    # 4. Weekday Heatmap (Mon-Fri)
    weekday_counts = {'Monday': 0, 'Tuesday': 0, 'Wednesday': 0, 'Thursday': 0, 'Friday': 0, 'Saturday': 0, 'Sunday': 0}
    for r in records:
        try:
            dt = datetime.datetime.strptime(r['date'], "%Y-%m-%d")
            wname = dt.strftime("%A")
            weekday_counts[wname] = weekday_counts.get(wname, 0) + 1
        except Exception:
            pass

    return {
        'total_students': total_students,
        'total_records': total_records,
        'critical_count': critical_cnt,
        'trend_labels': trend_labels,
        'trend_values': trend_values,
        'bar_labels': bar_labels,
        'bar_values': bar_values,
        'pie_labels': pie_labels,
        'pie_values': pie_values,
        'weekday_counts': weekday_counts
    }

def export_excel_report(records, title="Attendance_Report"):
    """
    Generates styled Excel report workbook with openpyxl.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Attendance Logs"

    # Header title
    ws.merge_cells('A1:H1')
    title_cell = ws['A1']
    title_cell.value = f"AI Smart Attendance System - {title}"
    title_cell.font = Font(name='Calibri', size=16, bold=True, color='FFFFFF')
    title_cell.fill = PatternFill(start_color='1E293B', end_color='1E293B', fill_type='solid')
    title_cell.alignment = Alignment(horizontal='center', vertical='center')
    ws.row_dimensions[1].height = 40

    headers = ["Date", "Time", "Student ID", "Roll Number", "Name", "Department", "Semester & Division", "Status"]
    ws.append([])
    ws.append(headers)

    header_fill = PatternFill(start_color='3B82F6', end_color='3B82F6', fill_type='solid')
    header_font = Font(name='Calibri', size=11, bold=True, color='FFFFFF')

    for col_num in range(1, len(headers) + 1):
        cell = ws.cell(row=3, column=col_num)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal='center', vertical='center')

    for r in records:
        sem_div = f"{r.get('semester', '')} {r.get('division', '')}".strip()
        ws.append([
            r.get('date', ''),
            r.get('time', ''),
            r.get('student_id', ''),
            r.get('roll_number', ''),
            r.get('name', ''),
            r.get('department', ''),
            sem_div,
            r.get('status', 'Present')
        ])

    # Auto column width
    for col in ws.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = openpyxl.utils.get_column_letter(col[0].column)
        ws.column_dimensions[col_letter].width = max(max_len + 3, 12)

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)
    return output.getvalue()

def export_pdf_report(records, title="Attendance_Report"):
    """
    Generates styled PDF report document using ReportLab.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=30)
    story = []
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=18,
        textColor=colors.HexColor('#0F172A'),
        spaceAfter=12,
        alignment=1
    )

    story.append(Paragraph(f"AI Smart Attendance - {title}", title_style))
    story.append(Paragraph(f"Generated on: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 15))

    table_data = [["Date", "Time", "Student ID", "Roll No", "Name", "Department", "Sem / Div", "Status"]]

    for r in records:
        sem_div = f"{r.get('semester', '')} {r.get('division', '')}".strip()
        table_data.append([
            r.get('date', ''),
            r.get('time', ''),
            r.get('student_id', ''),
            r.get('roll_number', ''),
            r.get('name', ''),
            r.get('department', ''),
            sem_div,
            r.get('status', 'Present')
        ])

    t = Table(table_data, colWidths=[65, 55, 65, 55, 110, 85, 60, 50])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3B82F6')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 9),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#F8FAFC')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('FONTSIZE', (0, 1), (-1, -1), 8),
    ]))

    story.append(t)
    doc.build(story)

    buffer.seek(0)
    return buffer.getvalue()
