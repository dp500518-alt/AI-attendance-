import re
import json
import threading
import datetime
import urllib.request
import os
import database
import notifications

def get_client_ip(request):
    """
    Extracts the client's public or real IP address from HTTP request headers.
    """
    if not request:
        return '127.0.0.1'

    # Check common proxy headers
    x_forwarded_for = request.headers.get('X-Forwarded-For')
    if x_forwarded_for:
        # X-Forwarded-For can contain comma-separated IPs: client, proxy1, proxy2
        ip = x_forwarded_for.split(',')[0].strip()
        if ip:
            return ip

    x_real_ip = request.headers.get('X-Real-IP')
    if x_real_ip:
        return x_real_ip.strip()

    return request.remote_addr or '127.0.0.1'

def get_location_from_ip(ip_address):
    """
    Resolves IP address to approximate Country, State/Region, City, Lat/Lon, and Timezone.
    Handles private/local IPs gracefully with realistic defaults.
    """
    default_loc = {
        'country': 'India',
        'state': 'Gujarat',
        'city': 'Surat',
        'latitude': 21.1702,
        'longitude': 72.8311,
        'timezone': 'Asia/Kolkata'
    }

    if not ip_address or ip_address in ['127.0.0.1', '::1', 'localhost'] or ip_address.startswith(('192.168.', '10.', '172.16.', '172.31.')):
        # For local dev / loopback, try fetching real public IP from ipify/ip-api
        try:
            req = urllib.request.Request("http://ip-api.com/json/?fields=status,country,regionName,city,lat,lon,timezone,query", headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=2.5) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('status') == 'success':
                    return {
                        'country': data.get('country') or 'India',
                        'state': data.get('regionName') or 'Gujarat',
                        'city': data.get('city') or 'Surat',
                        'latitude': float(data.get('lat') or 21.1702),
                        'longitude': float(data.get('lon') or 72.8311),
                        'timezone': data.get('timezone') or 'Asia/Kolkata'
                    }
        except Exception:
            pass
        return default_loc

    # Query ip-api for external public IP
    try:
        url = f"http://ip-api.com/json/{ip_address}?fields=status,country,regionName,city,lat,lon,timezone"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            if data.get('status') == 'success':
                return {
                    'country': data.get('country') or 'India',
                    'state': data.get('regionName') or 'Gujarat',
                    'city': data.get('city') or 'Surat',
                    'latitude': float(data.get('lat') or 21.1702),
                    'longitude': float(data.get('lon') or 72.8311),
                    'timezone': data.get('timezone') or 'Asia/Kolkata'
                }
    except Exception as e:
        print("IP Geolocation API notice:", e)

    return default_loc

def parse_user_agent(ua_string):
    """
    Parses User-Agent string to extract Browser Name, Operating System, and Device Type.
    """
    if not ua_string:
        return {'browser': 'Unknown Browser', 'os': 'Unknown OS', 'device_type': 'Desktop'}

    ua = ua_string

    # 1. Device Type Detection
    if re.search(r'Mobile|Android|iPhone|iPod|BlackBerry|IEMobile|Opera Mini', ua, re.IGNORECASE):
        device_type = 'Mobile'
    elif re.search(r'iPad|Tablet|Nexus 7|Nexus 10|Kindle|PlayBook', ua, re.IGNORECASE):
        device_type = 'Tablet'
    else:
        device_type = 'Desktop'

    # 2. Operating System Detection
    if re.search(r'Windows NT 10.0', ua):
        os_name = 'Windows 11/10'
    elif re.search(r'Windows NT 6.3', ua):
        os_name = 'Windows 8.1'
    elif re.search(r'Windows NT 6.1', ua):
        os_name = 'Windows 7'
    elif re.search(r'Windows', ua, re.IGNORECASE):
        os_name = 'Windows'
    elif re.search(r'Android', ua, re.IGNORECASE):
        os_match = re.search(r'Android\s*([0-9.]+)', ua, re.IGNORECASE)
        os_name = f"Android {os_match.group(1)}" if os_match else 'Android'
    elif re.search(r'iPhone|iPad|iPod', ua, re.IGNORECASE):
        os_match = re.search(r'OS\s*([0-9_]+)', ua, re.IGNORECASE)
        os_ver = os_match.group(1).replace('_', '.') if os_match else ''
        os_name = f"iOS {os_ver}".strip()
    elif re.search(r'Mac OS X', ua, re.IGNORECASE):
        os_name = 'macOS'
    elif re.search(r'Linux', ua, re.IGNORECASE):
        os_name = 'Linux'
    else:
        os_name = 'Unknown OS'

    # 3. Browser Detection
    if re.search(r'Edg/|Edge/', ua, re.IGNORECASE):
        browser = 'Microsoft Edge'
    elif re.search(r'OPR/|Opera', ua, re.IGNORECASE):
        browser = 'Opera'
    elif re.search(r'Chrome/', ua, re.IGNORECASE) and not re.search(r'Chromium/', ua, re.IGNORECASE):
        browser = 'Google Chrome'
    elif re.search(r'Firefox/', ua, re.IGNORECASE):
        browser = 'Mozilla Firefox'
    elif re.search(r'Safari/', ua, re.IGNORECASE) and not re.search(r'Chrome/', ua, re.IGNORECASE):
        browser = 'Apple Safari'
    else:
        browser = 'Web Browser'

    return {
        'browser': browser,
        'os': os_name,
        'device_type': device_type
    }

def process_login_security(username, role, full_name, request_obj, session_id, status='Success', registered_email=None):
    """
    Main Security Processor:
    1. Extracts IP & Location data.
    2. Parses User-Agent details.
    3. Checks database to detect if login is from a NEW device/location.
    4. Records entry into LoginHistory table.
    5. Sends asynchronous security alert email if login originates from a new device/location.
    """
    ip_addr = get_client_ip(request_obj)
    loc_info = get_location_from_ip(ip_addr)
    ua_str = request_obj.headers.get('User-Agent', '') if request_obj else ''
    ua_info = parse_user_agent(ua_str)

    now = datetime.datetime.now()
    login_date = now.strftime("%Y-%m-%d")
    login_time = now.strftime("%H:%M:%S")
    created_at_str = now.strftime("%Y-%m-%d %H:%M:%S")

    # Check if user has logged in from this browser + OS + city before
    is_new_device = 0
    if status == 'Success':
        prior_logins = database.get_user_prior_success_logins(username)
        if not prior_logins:
            # First ever login for this account
            is_new_device = 1
        else:
            matching = [
                l for l in prior_logins
                if l.get('browser') == ua_info['browser'] and l.get('os') == ua_info['os'] and l.get('city') == loc_info['city']
            ]
            if not matching:
                is_new_device = 1

    # Record login attempt to Database
    login_id = database.add_login_history(
        username=username,
        role=role,
        full_name=full_name,
        login_date=login_date,
        login_time=login_time,
        ip_address=ip_addr,
        country=loc_info['country'],
        state=loc_info['state'],
        city=loc_info['city'],
        latitude=loc_info['latitude'],
        longitude=loc_info['longitude'],
        timezone=loc_info['timezone'],
        browser=ua_info['browser'],
        os_name=ua_info['os'],
        device_type=ua_info['device_type'],
        user_agent=ua_str,
        is_new_device=is_new_device,
        status=status,
        session_id=session_id,
        created_at=created_at_str
    )

    # Send Security Email in background thread if new device detected & status is Success
    if status == 'Success' and is_new_device == 1:
        if not registered_email:
            registered_email = database.get_user_email(username, role)

        if registered_email:
            display_time = now.strftime("%d %B %Y, %I:%M %p")
            location_str = f"{loc_info['city']}, {loc_info['state']}, {loc_info['country']}"

            # Async background email sending
            t = threading.Thread(
                target=send_security_alert_email,
                args=(registered_email, full_name or username, display_time, location_str, ua_info['browser'], ua_info['os'], ip_addr)
            )
            t.daemon = True
            t.start()

    return {
        'login_id': login_id,
        'ip_address': ip_addr,
        'location': loc_info,
        'ua_info': ua_info,
        'is_new_device': bool(is_new_device)
    }

def send_security_alert_email(email, full_name, login_time_str, location_str, browser, os_name, ip_address):
    """
    Formats and delivers the Security Login Alert email.
    """
    subject = "New Login Detected"
    body = f"""Hello {full_name},

A new login to your AI Attendance account was detected.

Time:
{login_time_str}

Location:
{location_str}

Browser:
{browser}

Operating System:
{os_name}

IP Address:
{ip_address}

If this was you, no action is required.

If you do not recognize this login, please change your password immediately.
"""

    notifications.send_email_notification(to_email=email, subject=subject, body=body)
