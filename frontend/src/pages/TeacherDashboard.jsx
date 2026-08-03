import React, { useEffect, useState } from 'react';
import { dashboardService } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { StatCard } from '../components/StatCard';
import { Link } from 'react-router-dom';

export const TeacherDashboard = () => {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardService.getTeacherDashboard(user?.username)
      .then((res) => setData(res.data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [user]);

  if (loading) return <div className="page-container">Loading Faculty Portal...</div>;

  const t_stats = data?.t_stats || {};
  const timetable = data?.my_timetable || [];
  const low_att = data?.low_attendance_students || [];

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: '1.5rem', fontWeight: 700 }}>Faculty Dashboard - Welcome, Prof. {user?.full_name}!</h2>

      <div className="stat-grid">
        <StatCard icon="📅" title="Lectures Today" value={t_stats.lectures_today || 0} type="primary" />
        <StatCard icon="🎓" title="Students Tracked" value={t_stats.students_tracked || 0} type="success" />
        <StatCard icon="⚠️" title="Low Attendance Alerts" value={low_att.length} type="warning" />
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '2fr 1fr', gap: '1.5rem', marginTop: '1.5rem' }}>
        <div className="glass-card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h3 style={{ margin: 0 }}>My Schedule</h3>
            <Link to="/classroom" className="btn-primary" style={{ padding: '0.4rem 0.8rem', fontSize: '0.85rem' }}>
              📷 Start Live Classroom
            </Link>
          </div>

          <table className="custom-table">
            <thead>
              <tr>
                <th>Day</th>
                <th>Time Slot</th>
                <th>Subject</th>
                <th>Classroom</th>
              </tr>
            </thead>
            <tbody>
              {timetable.map((item, idx) => (
                <tr key={idx}>
                  <td><b>{item.day_of_week}</b></td>
                  <td>{item.time_slot}</td>
                  <td>{item.subject_name}</td>
                  <td>{item.classroom_room}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="glass-card">
          <h3 style={{ marginTop: 0, color: 'var(--danger)' }}>Shortage Warning List</h3>
          <ul style={{ paddingLeft: '1.2rem', margin: 0 }}>
            {low_att.map((st, i) => (
              <li key={i} style={{ marginBottom: '0.5rem', fontSize: '0.9rem' }}>
                <b>{st.name}</b> ({st.id}) - <span style={{ color: 'var(--danger)', fontWeight: 600 }}>{st.percentage}%</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
};
