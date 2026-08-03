import React, { useEffect, useState } from 'react';
import { systemService } from '../services/api';

export const Training = () => {
  const [status, setStatus] = useState(null);
  const [logs, setLogs] = useState([]);

  const loadStatus = () => {
    systemService.getTrainingStatus().then((res) => setStatus(res.data)).catch(console.error);
    systemService.getTrainingLogs().then((res) => setLogs(res.data.logs || [])).catch(console.error);
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 3000);
    return () => clearInterval(interval);
  }, []);

  const handleStartTraining = async () => {
    try {
      await systemService.startTraining();
      loadStatus();
    } catch (err) {
      alert('Error triggering training: ' + err.message);
    }
  };

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0, fontWeight: 700 }}>AI Recognition Model Training</h2>
        <button onClick={handleStartTraining} className="btn-primary">
          🚀 Trigger Async Model Training
        </button>
      </div>

      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <h3>Training Status</h3>
        <p><b>Status:</b> {status?.is_training ? <span className="badge badge-warning">Training in Progress...</span> : <span className="badge badge-success">Idle / Ready</span>}</p>
        <p><b>Last Completed:</b> {status?.last_completed || 'Never'}</p>
      </div>

      <div className="glass-card">
        <h3>Live Training Logs</h3>
        <pre style={{ background: '#0f172a', color: '#38bdf8', padding: '1rem', borderRadius: '8px', maxHeight: '350px', overflowY: 'auto' }}>
          {logs.join('\n') || 'No training logs recorded yet.'}
        </pre>
      </div>
    </div>
  );
};
