import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { Sidebar } from './components/Sidebar';
import { Navbar } from './components/Navbar';

import { Login } from './pages/Login';
import { AdminDashboard } from './pages/AdminDashboard';
import { StudentDashboard } from './pages/StudentDashboard';
import { TeacherDashboard } from './pages/TeacherDashboard';
import { Students } from './pages/Students';
import { RegisterStudent } from './pages/RegisterStudent';
import { Teachers } from './pages/Teachers';
import { Timetable } from './pages/Timetable';
import { OCRPreview } from './pages/OCRPreview';
import { Classroom } from './pages/Classroom';
import { Analytics } from './pages/Analytics';
import { Training } from './pages/Training';
import { Settings } from './pages/Settings';
import { Diagnostics } from './pages/Diagnostics';
import { Subjects } from './pages/Subjects';
import { History } from './pages/History';

const ProtectedLayout = ({ children }) => {
  const { user, loading } = useAuth();

  if (loading) return <div style={{ padding: '2rem' }}>Loading Portal...</div>;
  if (!user) return <Navigate to="/login" replace />;

  return (
    <div className="app-container">
      <Sidebar />
      <div className="main-content">
        <Navbar />
        {children}
      </div>
    </div>
  );
};

export const App = () => {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<Login />} />
          
          <Route path="/" element={<ProtectedLayout><AdminDashboard /></ProtectedLayout>} />
          <Route path="/student/dashboard" element={<ProtectedLayout><StudentDashboard /></ProtectedLayout>} />
          <Route path="/teacher/dashboard" element={<ProtectedLayout><TeacherDashboard /></ProtectedLayout>} />
          <Route path="/students" element={<ProtectedLayout><Students /></ProtectedLayout>} />
          <Route path="/register-student" element={<ProtectedLayout><RegisterStudent /></ProtectedLayout>} />
          <Route path="/teachers" element={<ProtectedLayout><Teachers /></ProtectedLayout>} />
          <Route path="/timetable" element={<ProtectedLayout><Timetable /></ProtectedLayout>} />
          <Route path="/ocr-preview" element={<ProtectedLayout><OCRPreview /></ProtectedLayout>} />
          <Route path="/classroom" element={<ProtectedLayout><Classroom /></ProtectedLayout>} />
          <Route path="/analytics" element={<ProtectedLayout><Analytics /></ProtectedLayout>} />
          <Route path="/training" element={<ProtectedLayout><Training /></ProtectedLayout>} />
          <Route path="/settings" element={<ProtectedLayout><Settings /></ProtectedLayout>} />
          <Route path="/diagnostics" element={<ProtectedLayout><Diagnostics /></ProtectedLayout>} />
          <Route path="/subjects" element={<ProtectedLayout><Subjects /></ProtectedLayout>} />
          <Route path="/history" element={<ProtectedLayout><History /></ProtectedLayout>} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
};

export default App;
