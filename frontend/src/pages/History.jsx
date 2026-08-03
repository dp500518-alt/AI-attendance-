import React, { useEffect, useState } from 'react';
import { systemService } from '../services/api';

export const History = () => {
  const [logs, setLogs] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    systemService.getHistory()
      .then((res) => setLogs(res.data.logs || []))
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: '1.5rem', fontWeight: 700 }}>Attendance Historical Logs</h2>

      <div className="glass-card">
        <table className="custom-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Student ID</th>
              <th>Student Name</th>
              <th>Subject</th>
              <th>Teacher</th>
              <th>Confidence</th>
              <th>Timestamp</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="7" style={{ textAlign: 'center' }}>Loading history...</td></tr>
            ) : logs.length === 0 ? (
              <tr><td colSpan="7" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No historical logs found.</td></tr>
            ) : (
              logs.map((log, idx) => (
                <tr key={idx}>
                  <td><b>{log.id}</b></td>
                  <td>{log.student_id}</td>
                  <td>{log.student_name || 'N/A'}</td>
                  <td>{log.subject_name}</td>
                  <td>{log.teacher_name}</td>
                  <td>{(log.confidence * 100).toFixed(1)}%</td>
                  <td>{log.timestamp}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
