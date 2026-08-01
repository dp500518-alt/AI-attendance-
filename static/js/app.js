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

// 3. Webcam & Upload Helper for Registration Page
let regWebcamStream = null;
let regCapturedSamples = [];

async function startRegistrationWebcam(videoElemId) {
    const video = document.getElementById(videoElemId);
    if (!video) return;

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        alert("⚠️ Mobile Camera Notice:\n\nBrowsers block live webcam streams over HTTP.\n\nPlease use the 'Upload Face Photos' option below to snap photos!");
        return;
    }

    try {
        regWebcamStream = await navigator.mediaDevices.getUserMedia({
            video: { width: 640, height: 480, facingMode: "user" }
        });
        video.srcObject = regWebcamStream;
    } catch (err) {
        console.error("Webcam access error:", err);
        alert("Could not access webcam. Please grant camera permissions or use the direct 'Upload Face Photos' option.");
    }
}

function stopRegistrationWebcam() {
    if (regWebcamStream) {
        regWebcamStream.getTracks().forEach(track => track.stop());
        regWebcamStream = null;
    }
}

async function captureRegistrationSamples(videoElemId, totalCount = 15, progressBarId, statusTextId) {
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

    // Optimized 320x240 resolution @ 0.50 JPEG quality (~15-20 KB per frame)
    // 15 photos = ~250 KB total base64 JSON payload (prevents Vercel 4.5MB 413 error)
    const canvas = document.createElement('canvas');
    canvas.width = 320;
    canvas.height = 240;
    const ctx = canvas.getContext('2d');

    for (let i = 1; i <= totalCount; i++) {
        ctx.drawImage(video, 0, 0, 320, 240);
        const b64Data = canvas.toDataURL('image/jpeg', 0.50);
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
    
    // Store JSON in hidden form field
    const samplesJsonElem = document.getElementById('samples_json');
    if (samplesJsonElem) {
        samplesJsonElem.value = JSON.stringify(regCapturedSamples);
    }

    if (submitBtn) submitBtn.disabled = false;
    if (startBtn) startBtn.disabled = false;
}

// Client-side compressed photo upload for registration (when webcam is not used/available)
async function handleRegisterFileUpload(fileInputElem, progressBarId, statusTextId) {
    const files = fileInputElem.files;
    if (!files || files.length === 0) return;

    const progressBar = document.getElementById(progressBarId);
    const statusText = document.getElementById(statusTextId);
    const submitBtn = document.getElementById('submitRegBtn');

    regCapturedSamples = [];
    const totalFiles = files.length;
    let processedCount = 0;

    for (let i = 0; i < totalFiles; i++) {
        const file = files[i];
        if (!file.type.startsWith('image/')) continue;

        try {
            const b64Data = await compressImageFileToBase64(file, 320, 240, 0.50);
            regCapturedSamples.push(b64Data);
            processedCount++;

            const pct = Math.round((processedCount / totalFiles) * 100);
            if (progressBar) {
                progressBar.style.width = pct + '%';
                progressBar.setAttribute('aria-valuenow', pct);
            }
            if (statusText) {
                statusText.innerText = `Processed ${processedCount} of ${totalFiles} uploaded photos (${pct}%)`;
            }
        } catch (err) {
            console.error("Error processing file:", file.name, err);
        }
    }

    const samplesJsonElem = document.getElementById('samples_json');
    if (samplesJsonElem) {
        samplesJsonElem.value = JSON.stringify(regCapturedSamples);
    }

    if (statusText) {
        statusText.innerText = `Processed ${regCapturedSamples.length} photo(s) successfully! Ready to save.`;
    }
    if (submitBtn && regCapturedSamples.length > 0) {
        submitBtn.disabled = false;
    }
}

// Generic Image Resizer / Compressor returning base64 JPEG
function compressImageFileToBase64(file, maxW = 1280, maxH = 960, quality = 0.70) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                let w = img.width;
                let h = img.height;

                if (w > maxW || h > maxH) {
                    if (w / maxW > h / maxH) {
                        h = Math.round((h * maxW) / w);
                        w = maxW;
                    } else {
                        w = Math.round((w * maxH) / h);
                        h = maxH;
                    }
                }

                const canvas = document.createElement('canvas');
                canvas.width = w;
                canvas.height = h;
                const ctx = canvas.getContext('2d');
                ctx.drawImage(img, 0, 0, w, h);
                resolve(canvas.toDataURL('image/jpeg', quality));
            };
            img.onerror = reject;
            img.src = e.target.result;
        };
        reader.onerror = reject;
        reader.readAsDataURL(file);
    });
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
                width: { ideal: 1280 },
                height: { ideal: 720 },
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

    const maxW = 1280;
    const maxH = 960;
    let w = video.videoWidth || 1280;
    let h = video.videoHeight || 720;

    if (w > maxW || h > maxH) {
        if (w / maxW > h / maxH) {
            h = Math.round((h * maxW) / w);
            w = maxW;
        } else {
            w = Math.round((w * maxH) / h);
            h = maxH;
        }
    }

    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, w, h);
    return canvas.toDataURL('image/jpeg', 0.75);
}

// 5. Client-Side Image Compressor for Classroom Photo Form Upload
async function compressAndSubmitClassroomForm(event, formElem) {
    const fileInput = formElem.querySelector('input[type="file"][name="classroom_photo"]');
    if (!fileInput || !fileInput.files || fileInput.files.length === 0) {
        return true;
    }

    const file = fileInput.files[0];
    // If file is already small (< 800KB), submit directly
    if (file.size < 800 * 1024) {
        return true;
    }

    event.preventDefault(); // Intercept raw large upload

    const submitBtn = formElem.querySelector('button[type="submit"]');
    const originalText = submitBtn ? submitBtn.innerHTML : '';
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Compressing & Uploading...';
    }

    try {
        const b64Data = await compressImageFileToBase64(file, 1280, 960, 0.75);
        
        // Convert base64 to Blob
        const res = await fetch(b64Data);
        const blob = await res.blob();
        const compressedFile = new File([blob], file.name || "classroom.jpg", { type: "image/jpeg" });

        // Replace file input files via DataTransfer API
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(compressedFile);
        fileInput.files = dataTransfer.files;

        // Submit form
        formElem.submit();
    } catch (err) {
        console.error("Compression failed, proceeding with standard submit:", err);
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
        formElem.submit();
    }
    return false;
}
