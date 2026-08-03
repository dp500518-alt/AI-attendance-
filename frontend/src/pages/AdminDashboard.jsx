import React, { useEffect, useState } from 'react';
import { dashboardService } from '../services/api';
import { StatCard } from '../components/StatCard';

export const AdminDashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    dashboardService.getAdminStats()
      .then((res) => setData(res.data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-container">Loading Admin Dashboard...</div>;

  const stats = data?.stats || {};
  const today = data?.today_attendance || [];

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: '1.5rem', fontWeight: 700 }}>Admin Executive Dashboard</h2>

      <div className="stat-grid">
        <StatCard icon="🎓" title="Total Registered Students" value={stats.total_students || 0} type="primary" />
        <StatCard icon="✅" title="Present Today" value={stats.present_today || 0} type="success" />
        <StatCard icon="❌" title="Absent Today" value={stats.absent_today || 0} type="danger" />
        <StatCard icon="🧠" title="Face Embeddings" value={data?.embedded_count || 0} type="info" />
      </div>

      <div className="glass-card" style={{ marginTop: '2rem' }}>
        <h3 style={{ marginTop: 0, marginBottom: '1rem' }}>Today's Live Attendance Records</h3>
        <div className="table-responsive">
          <table className="custom-table">
            <thead>
              <tr>
                <th>Student ID</th>
                <th>Name</th>
                <th>Subject</th>
                <th>Teacher</th>
                <th>Timestamp</th>
                <th>Confidence</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {today.length === 0 ? (
                <tr>
                  <td colSpan="7" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
                    No attendance records marked yet today.
                  </td>
                </tr>
              ) : (
                today.map((rec, idx) => (
                  <tr key={idx}>
                    <td><b>{rec.student_id}</b></td>
                    <td>{rec.student_name || 'N/A'}</td>
                    <td>{rec.subject_name}</td>
                    <td>{rec.teacher_name}</td>
                    <td>{rec.timestamp}</td>
                    <td>{(rec.confidence * 100).toFixed(1)}%</td>
                    <td><span className="badge badge-success">Present</span></td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
