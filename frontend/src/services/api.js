import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:5000/api';

export const api = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

export const authService = {
  login: (username, password) => api.post('/auth/login', { username, password }),
  logout: () => api.post('/auth/logout'),
  getCurrentUser: () => api.get('/auth/me'),
};

export const dashboardService = {
  getAdminStats: () => api.get('/dashboard/stats'),
  getStudentDashboard: (username) => api.get(`/student/dashboard?username=${encodeURIComponent(username || '')}`),
  getTeacherDashboard: (teacher) => api.get(`/teacher/dashboard?teacher=${encodeURIComponent(teacher || '')}`),
};

export const studentService = {
  getStudents: (dept = '', sem = '', q = '') => api.get(`/students?dept=${dept}&sem=${sem}&q=${q}`),
  registerStudent: (data) => api.post('/register', data),
  deleteStudent: (studentId) => api.delete(`/students/delete/${studentId}`),
};

export const teacherService = {
  getTeachers: () => api.get('/teachers'),
  createTeacher: (data) => api.post('/teachers', data),
  deleteTeacher: (userId) => api.delete(`/teachers/delete/${userId}`),
};

export const timetableService = {
  getTimetable: (semester = 'Semester 1', division = 'Division A') =>
    api.get(`/timetable?semester=${encodeURIComponent(semester)}&division=${encodeURIComponent(division)}`),
  addEntry: (data) => api.post('/timetable', data),
  editEntry: (id, data) => api.post(`/timetable/edit/${id}`, data),
  deleteEntry: (id) => api.post(`/timetable/delete/${id}`),
  ocrUpload: (formData) => api.post('/timetable/ocr_upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  saveOcr: (entries) => api.post('/timetable/save_ocr', { entries }),
};

export const classroomService = {
  uploadPhoto: (formData) => api.post('/classroom/upload', formData, { headers: { 'Content-Type': 'multipart/form-data' } }),
  snapLive: (image_b64, subject_name, teacher_name) => api.post('/classroom/snap', { image_b64, subject_name, teacher_name }),
};

export const systemService = {
  getHistory: (date = '', dept = '', subject = '') => api.get(`/history?date=${date}&department=${dept}&subject=${subject}`),
  getAnalytics: () => api.get('/analytics'),
  getSubjects: () => api.get('/subjects'),
  addSubject: (data) => api.post('/subjects', data),
  deleteSubject: (id) => api.post(`/subjects/delete/${id}`),
  getNotifications: () => api.get('/notifications'),
  markNotifRead: (id) => api.post(`/notifications/read/${id}`),
  getTrainingStatus: () => api.get('/training/status'),
  getTrainingLogs: () => api.get('/training/logs'),
  startTraining: () => api.post('/training/train'),
  getDiagnostics: () => api.get('/diagnostics'),
  getSettings: () => api.get('/settings'),
  updateSettings: (data) => api.post('/settings/update', data),
};
