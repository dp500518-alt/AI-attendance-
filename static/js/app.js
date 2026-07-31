/**
 * Smart Attendance Application Frontend JavaScript
 */

document.addEventListener('DOMContentLoaded', () => {
    initThemeToggle();
    initFlashAutoDismiss();
    initMobileSidebar();
});

// 0. Mobile Navigation Sidebar Toggle
function initMobileSidebar() {
    const sidebar = document.getElementById('appSidebar');
    const toggleBtn = document.getElementById('sidebarToggleBtn');
    const closeBtn = document.getElementById('sidebarCloseBtn');
    const backdrop = document.getElementById('sidebarBackdrop');

    if (!sidebar) return;

    function openSidebar() {
        sidebar.classList.add('show');
        if (backdrop) backdrop.classList.add('show');
        document.body.style.overflow = 'hidden';
    }

    function closeSidebar() {
        sidebar.classList.remove('show');
        if (backdrop) backdrop.classList.remove('show');
        document.body.style.overflow = '';
    }

    if (toggleBtn) toggleBtn.addEventListener('click', openSidebar);
    if (closeBtn) closeBtn.addEventListener('click', closeSidebar);
    if (backdrop) backdrop.addEventListener('click', closeSidebar);

    // Auto-close sidebar on navigating links on mobile screens
    const navLinks = sidebar.querySelectorAll('.nav-link');
    navLinks.forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth < 992) {
                closeSidebar();
            }
        });
    });
}


// 1. Light Mode Enforcer
function initThemeToggle() {
    localStorage.removeItem('smart_attendance_theme');
    document.documentElement.removeAttribute('data-theme');
    document.documentElement.setAttribute('data-theme', 'light');
}

// 2. Auto Dismiss Flash Messages after 5s
function initFlashAutoDismiss() {
    setTimeout(() => {
        const alerts = document.querySelectorAll('.alert-dismissible');
        alerts.forEach(alert => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        });
    }, 5000);
}

// 3. Webcam Helper for Registration Page
let regWebcamStream = null;
let regCapturedSamples = [];

async function startRegistrationWebcam(videoElemId) {
    const video = document.getElementById(videoElemId);
    if (!video) return;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert("⚠️ Mobile Camera Security Notice:\n\nBrowsers block live webcam streams over plain HTTP network IP (http://192.168.29.113:5000).\n\nPlease use the 'Choose File / Take Photo' button on your phone to snap a photo directly!");
        return;
    }

    try {
        regWebcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: "user" }
        });
        video.srcObject = regWebcamStream;
    } catch (err) {
        console.error("Webcam access error:", err);
        alert("Could not access webcam. On mobile network IP (HTTP), browsers block live camera stream. Please grant camera permissions or use the direct 'Take Photo / Upload' option.");
    }
}

function stopRegistrationWebcam() {
    if (regWebcamStream) {
        regWebcamStream.getTracks().forEach(track => track.stop());
        regWebcamStream = null;
    }
}

async function captureRegistrationSamples(videoElemId, totalCount = 25, progressBarId, statusTextId) {
    const video = document.getElementById(videoElemId);
    const progressBar = document.getElementById(progressBarId);
    const statusText = document.getElementById(statusTextId);
    const startBtn = document.getElementById('startCaptureBtn');
    const submitBtn = document.getElementById('submitRegBtn');

    if (!video || !regWebcamStream) {
        alert("Webcam is not active. Please start camera first.");
        return;
    }

    if (startBtn) startBtn.disabled = true;
    regCapturedSamples = [];

    // Compress to 480x360 for fast upload
    const canvas = document.createElement('canvas');
    canvas.width = 480;
    canvas.height = 360;
    const ctx = canvas.getContext('2d');

    for (let i = 1; i <= totalCount; i++) {
        ctx.drawImage(video, 0, 0, 480, 360);
        const b64Data = canvas.toDataURL('image/jpeg', 0.65);
        regCapturedSamples.push(b64Data);

        const pct = Math.round((i / totalCount) * 100);
        if (progressBar) {
            progressBar.style.width = pct + '%';
            progressBar.setAttribute('aria-valuenow', pct);
        }
        if (statusText) {
            statusText.innerText = `Captured ${i} of ${totalCount} face photos (${pct}%)`;
        }

        // Delay 100ms between frame snaps
        await new Promise(r => setTimeout(r, 100));
    }

    if (statusText) {
        statusText.innerText = `Captured all ${totalCount} face photos successfully! Ready to save.`;
    }
    if (submitBtn) submitBtn.disabled = false;
    if (startBtn) startBtn.disabled = false;
}

// 4. Live Classroom Webcam Capture Helper (Rear & Front Camera Support)
let classroomWebcamStream = null;
let classroomFacingMode = 'environment'; // Default to Rear / Back camera for mobile phones

async function startClassroomWebcam(videoElemId, mode = 'environment') {
    const video = document.getElementById(videoElemId);
    if (!video) return;

    if (mode) {
        classroomFacingMode = mode;
    }

    // Stop existing stream if running
    if (classroomWebcamStream) {
        classroomWebcamStream.getTracks().forEach(track => track.stop());
        classroomWebcamStream = null;
    }

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert("⚠️ Mobile Camera Security Notice:\n\nBrowsers require HTTPS or localhost for live camera stream.\n\nPlease use Option 1 ('Snap Photo with Rear Camera') on your phone!");
        return;
    }

    try {
        classroomWebcamStream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 1920 },
                height: { ideal: 1080 },
                facingMode: { ideal: classroomFacingMode }
            }
        });
        video.srcObject = classroomWebcamStream;
    } catch (err) {
        console.warn("Retrying camera stream with basic constraints:", err);
        try {
            classroomWebcamStream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: classroomFacingMode }
            });
            video.srcObject = classroomWebcamStream;
        } catch (fallbackErr) {
            console.error("Camera access failed:", fallbackErr);
            alert("Unable to open camera feed. Please use Option 1 ('Snap Photo with Rear Camera / Upload') on your mobile phone.");
        }
    }
}

async function toggleClassroomCamera(videoElemId) {
    classroomFacingMode = (classroomFacingMode === 'environment') ? 'user' : 'environment';
    await startClassroomWebcam(videoElemId, classroomFacingMode);
}

function captureClassroomPhoto(videoElemId) {
    const video = document.getElementById(videoElemId);
    if (!video || !classroomWebcamStream) {
        alert("Camera stream is not active. Please start camera first.");
        return null;
    }

    const canvas = document.createElement('canvas');
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.85);
}
