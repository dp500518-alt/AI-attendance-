/**
 * AI Smart Attendance System - Vanilla JavaScript API Client
 * Interacts with Flask REST API Server on http://localhost:5000/api
 */

const API_BASE = window.location.origin.includes('5000') 
  ? '/api' 
  : 'http://localhost:5000/api';

async function apiFetch(endpoint, options = {}) {
  const defaultHeaders = {
    'Accept': 'application/json',
  };

  if (!(options.body instanceof FormData)) {
    defaultHeaders['Content-Type'] = 'application/json';
    if (options.body && typeof options.body === 'object') {
      options.body = JSON.stringify(options.body);
    }
  }

  options.headers = { ...defaultHeaders, ...options.headers };
  options.credentials = 'include';

  try {
    const response = await fetch(`${API_BASE}${endpoint}`, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw new Error(data.message || `HTTP error! status: ${response.status}`);
    }
    return data;
  } catch (error) {
    console.error(`API Fetch Error [${endpoint}]:`, error);
    throw error;
  }
}

// REST API Helper Modules
const API = {
  auth: {
    login: (username, password) => apiFetch('/auth/login', { method: 'POST', body: { username, password } }),
    logout: () => apiFetch('/auth/logout', { method: 'POST' }),
    me: () => apiFetch('/auth/me'),
  },
  dashboard: {
    getStats: () => apiFetch('/dashboard/stats'),
    getStudentDashboard: (user) => apiFetch(`/student/dashboard?username=${encodeURIComponent(user || '')}`),
    getTeacherDashboard: (teacher) => apiFetch(`/teacher/dashboard?teacher=${encodeURIComponent(teacher || '')}`),
  },
  students: {
    list: (dept = '', sem = '', q = '') => apiFetch(`/students?dept=${dept}&sem=${sem}&q=${q}`),
    register: (data) => apiFetch('/register', { method: 'POST', body: data }),
    delete: (id) => apiFetch(`/students/delete/${id}`, { method: 'DELETE' }),
  },
  teachers: {
    list: () => apiFetch('/teachers'),
    create: (data) => apiFetch('/teachers', { method: 'POST', body: data }),
    delete: (id) => apiFetch(`/teachers/delete/${id}`, { method: 'DELETE' }),
  },
  timetable: {
    get: (sem = 'Semester 1', div = 'Division A') => apiFetch(`/timetable?semester=${encodeURIComponent(sem)}&division=${encodeURIComponent(div)}`),
    add: (data) => apiFetch('/timetable', { method: 'POST', body: data }),
    edit: (id, data) => apiFetch(`/timetable/edit/${id}`, { method: 'POST', body: data }),
    delete: (id) => apiFetch(`/timetable/delete/${id}`, { method: 'POST' }),
    ocrUpload: (formData) => apiFetch('/timetable/ocr_upload', { method: 'POST', body: formData }),
    saveOcr: (entries) => apiFetch('/timetable/save_ocr', { method: 'POST', body: { entries } }),
  },
  classroom: {
    upload: (formData) => apiFetch('/classroom/upload', { method: 'POST', body: formData }),
    snap: (b64, subject, teacher) => apiFetch('/classroom/snap', { method: 'POST', body: { image_b64: b64, subject_name: subject, teacher_name: teacher } }),
  },
  system: {
    history: (date = '', dept = '', subject = '') => apiFetch(`/history?date=${date}&department=${dept}&subject=${subject}`),
    analytics: () => apiFetch('/analytics'),
    subjects: () => apiFetch('/subjects'),
    addSubject: (data) => apiFetch('/subjects', { method: 'POST', body: data }),
    deleteSubject: (id) => apiFetch(`/subjects/delete/${id}`, { method: 'POST' }),
    trainingStatus: () => apiFetch('/training/status'),
    trainingLogs: () => apiFetch('/training/logs'),
    startTraining: () => apiFetch('/training/train', { method: 'POST' }),
    diagnostics: () => apiFetch('/diagnostics'),
    settings: () => apiFetch('/settings'),
    updateSettings: (data) => apiFetch('/settings/update', { method: 'POST', body: data }),
  }
};

window.API = API;
