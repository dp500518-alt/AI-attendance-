import React, { useEffect, useState } from 'react';
import { dashboardService } from '../services/api';
import { useAuth } from '../context/AuthContext';
import { StatCard } from '../components/StatCard';

export const StudentDashboard = () => {
  const { user } = useAuth();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardService.getStudentDashboard(user?.username)
      .then((res) => setData(res.data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [user]);

  if (loading) return <div className="page-container">Loading Student Portal...</div>;

  const student = data?.student || {};
  const summary = data?.summary || { total_classes: 0, attended: 0, percentage: 0 };
  const timetable = data?.timetable || [];

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: '1.5rem', fontWeight: 700 }}>Student Portal - Welcome, {student.name}!</h2>

      <div className="stat-grid">
        <StatCard icon="📊" title="Attendance Rate" value={`${summary.percentage}%`} type={summary.percentage >= 75 ? 'success' : 'danger'} />
        <StatCard icon="✅" title="Attended Classes" value={summary.attended} type="primary" />
        <StatCard icon="📚" title="Total Classes" value={summary.total_classes} type="info" />
      </div>

      <div className="glass-card" style={{ marginTop: '2rem' }}>
        <h3 style={{ marginTop: 0 }}>My Weekly Timetable Schedule</h3>
        <div className="table-responsive">
          <table className="custom-table">
            <thead>
              <tr>
                <th>Day</th>
                <th>Time Slot</th>
                <th>Subject</th>
                <th>Faculty</th>
                <th>Classroom</th>
              </tr>
            </thead>
            <tbody>
              {timetable.map((t, i) => (
                <tr key={i}>
                  <td><b>{t.day_of_week}</b></td>
                  <td>{t.time_slot}</td>
                  <td>{t.subject_name}</td>
                  <td>{t.teacher_name}</td>
                  <td>{t.classroom_room}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
