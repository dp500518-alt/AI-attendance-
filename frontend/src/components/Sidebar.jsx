import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export const Sidebar = () => {
  const { user } = useAuth();
  const role = user?.role || 'admin';

  return (
    <aside className="app-sidebar">
      <div className="sidebar-header">
        <div className="brand-icon">⚡</div>
        <div className="brand-text">AI Attendance</div>
      </div>

      <ul className="nav-links">
        {role === 'admin' && (
          <>
            <li className="nav-item">
              <NavLink to="/" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📊 Dashboard
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/students" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                🎓 Students Directory
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/register-student" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                ➕ Register Student
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/teachers" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                👨‍🏫 Teacher Directory
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/classroom" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📷 Live Classroom
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/timetable" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📅 Timetable Schedule
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/ocr-preview" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📑 OCR Timetable
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/subjects" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📚 Subjects
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/history" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📜 Attendance Logs
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/analytics" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📈 Analytics & Reports
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/training" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                🧠 AI Model Training
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/settings" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                ⚙️ System Settings
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/diagnostics" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                🔍 Diagnostics
              </NavLink>
            </li>
          </>
        )}

        {role === 'teacher' && (
          <>
            <li className="nav-item">
              <NavLink to="/teacher/dashboard" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                👨‍🏫 Teacher Dashboard
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/classroom" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📷 Live Classroom
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/timetable" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📅 Timetable Schedule
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/students" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                🎓 Students List
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/history" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📜 Attendance Logs
              </NavLink>
            </li>
          </>
        )}

        {role === 'student' && (
          <>
            <li className="nav-item">
              <NavLink to="/student/dashboard" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                🎓 My Dashboard
              </NavLink>
            </li>
            <li className="nav-item">
              <NavLink to="/timetable" className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}>
                📅 My Timetable
              </NavLink>
            </li>
          </>
        )}
      </ul>
    </aside>
  );
};
