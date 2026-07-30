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


// 1. Dark Mode Toggle
function initThemeToggle() {
    const themeBtn = document.getElementById('themeToggleBtn');
    if (!themeBtn) return;

    const savedTheme = localStorage.getItem('smart_attendance_theme') ||
        (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');

    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);

    themeBtn.addEventListener('click', () => {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('smart_attendance_theme', newTheme);
        updateThemeIcon(newTheme);
    });
}

function updateThemeIcon(theme) {
    const themeBtn = document.getElementById('themeToggleBtn');
    if (themeBtn) {
        themeBtn.innerHTML = theme === 'dark' ?
            '<i class="bi bi-sun-fill text-warning"></i>' :
            '<i class="bi bi-moon-stars-fill text-secondary"></i>';
    }
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

    try {
        regWebcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: "user" }
        });
        video.srcObject = regWebcamStream;
    } catch (err) {
        console.error("Webcam access error:", err);
        alert("Could not access webcam. Please ensure camera permissions are granted.");
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

// 4. Live Classroom Webcam Capture Helper
let classroomWebcamStream = null;

async function startClassroomWebcam(videoElemId) {
    const video = document.getElementById(videoElemId);
    if (!video) return;

    try {
        classroomWebcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 1280, height: 720, facingMode: "environment" }
        });
        video.srcObject = classroomWebcamStream;
    } catch (err) {
        console.error("Classroom webcam error:", err);
        alert("Unable to open camera feed.");
    }
}

function captureClassroomPhoto(videoElemId) {
    const video = document.getElementById(videoElemId);
    if (!video || !classroomWebcamStream) {
        alert("Camera stream is not active.");
        return null;
    }

    const canvas = document.createElement('canvas');
    canvas.width = 960;
    canvas.height = 540;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.75);
}
