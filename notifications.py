import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import config
import database

def send_short_attendance_alert(student_id, student_name, current_pct, email=None, phone=None):
    """
    Triggers multi-channel notification alert when student attendance falls below configured threshold (50%).
    Channels: Website Notification DB, Email, SMS (hook), WhatsApp (hook).
    """
    title = "⚠️ Short Attendance Warning (<50%)"
    message = f"Warning: Your overall attendance has fallen to {current_pct}%. Please attend upcoming lectures regularly to avoid detention."

    # 1. Website Notification (In-App)
    database.create_notification(target_user=student_id, title=title, message=message, channel="website")

    # 2. Email Notification (if SMTP configured & email available)
    if email:
        send_email_notification(to_email=email, subject=title, body=message)

    # 3. SMS & WhatsApp hooks
    if phone:
        send_sms_notification(phone=phone, message=message)
        send_whatsapp_notification(phone=phone, message=message)

    return True

def send_email_notification(to_email, subject, body):
    """
    Sends email alert using SMTP if configured in config or environment.
    """
    smtp_server = os.environ.get('SMTP_SERVER')
    smtp_port = int(os.environ.get('SMTP_PORT', 587))
    smtp_user = os.environ.get('SMTP_USER')
    smtp_pass = os.environ.get('SMTP_PASS')

    if not (smtp_server and smtp_user and smtp_pass):
        # Logged for audit trail
        print(f"[Email Notification Ready] To: {to_email} | Subject: {subject}")
        return False

    try:
        msg = MIMEMultipart()
        msg['From'] = smtp_user
        msg['To'] = to_email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print("Email sending error:", e)
        return False

def send_sms_notification(phone, message):
    """
    Future-ready SMS gateway integration hook (Twilio/AWS SNS ready).
    """
    print(f"[SMS Gateway Hook Ready] Phone: {phone} | Msg: {message}")
    return True

def send_whatsapp_notification(phone, message):
    """
    Future-ready WhatsApp API gateway hook (Twilio WhatsApp / Meta Cloud API ready).
    """
    print(f"[WhatsApp Gateway Hook Ready] Phone: {phone} | Msg: {message}")
    return True
