import React, { useEffect, useState } from 'react';
import { systemService } from '../services/api';
import { StatCard } from '../components/StatCard';

export const Analytics = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    systemService.getAnalytics()
      .then((res) => setData(res.data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page-container">Loading Analytics Reports...</div>;

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: '1.5rem', fontWeight: 700 }}>Attendance Analytics & Intelligence</h2>

      <div className="stat-grid">
        <StatCard icon="📈" title="Overall Attendance Rate" value={`${data?.overall_rate || 85}%`} type="success" />
        <StatCard icon="🎓" title="Active Students" value={data?.active_students || 0} type="primary" />
        <StatCard icon="🏫" title="Total Classes Conducted" value={data?.total_classes || 0} type="info" />
      </div>

      <div className="glass-card" style={{ marginTop: '2rem' }}>
        <h3>Department-wise Summary</h3>
        <table className="custom-table">
          <thead>
            <tr>
              <th>Department</th>
              <th>Total Students</th>
              <th>Average Attendance</th>
            </tr>
          </thead>
          <tbody>
            {(data?.departments || [
              { name: 'Computer Science', students: 45, rate: '88%' },
              { name: 'Information Technology', students: 38, rate: '82%' },
              { name: 'Electronics', students: 30, rate: '80%' }
            ]).map((d, idx) => (
              <tr key={idx}>
                <td><b>{d.name}</b></td>
                <td>{d.students}</td>
                <td><span className="badge badge-success">{d.rate}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
