import React, { useEffect, useState } from 'react';
import { systemService } from '../services/api';

export const Settings = () => {
  const [settings, setSettings] = useState({ recognition_threshold: 0.40, min_face_size: 60, camera_index: 0 });
  const [msg, setMsg] = useState('');

  useEffect(() => {
    systemService.getSettings()
      .then((res) => setSettings(res.data.settings || {}))
      .catch(console.error);
  }, []);

  const handleSave = async (e) => {
    e.preventDefault();
    await systemService.updateSettings(settings);
    setMsg('Settings updated successfully!');
    setTimeout(() => setMsg(''), 3000);
  };

  return (
    <div className="page-container" style={{ maxWidth: '650px' }}>
      <h2 style={{ marginBottom: '1.5rem', fontWeight: 700 }}>System Configuration Settings</h2>

      {msg && <div style={{ padding: '0.8rem', background: 'rgba(16, 185, 129, 0.2)', color: '#10b981', borderRadius: '8px', marginBottom: '1rem' }}>{msg}</div>}

      <div className="glass-card">
        <form onSubmit={handleSave}>
          <div className="form-group">
            <label>Face Recognition Similarity Threshold (Cosine Distance)</label>
            <input
              type="number"
              step="0.01"
              className="form-control"
              value={settings.recognition_threshold}
              onChange={(e) => setSettings({ ...settings, recognition_threshold: parseFloat(e.target.value) })}
            />
            <small style={{ color: 'var(--text-muted)' }}>Lower = stricter matching. Higher = looser matching.</small>
          </div>

          <div className="form-group">
            <label>Minimum Face Size (Pixels)</label>
            <input
              type="number"
              className="form-control"
              value={settings.min_face_size}
              onChange={(e) => setSettings({ ...settings, min_face_size: parseInt(e.target.value) })}
            />
          </div>

          <div className="form-group">
            <label>Webcam Device Hardware Index</label>
            <input
              type="number"
              className="form-control"
              value={settings.camera_index}
              onChange={(e) => setSettings({ ...settings, camera_index: parseInt(e.target.value) })}
            />
          </div>

          <button type="submit" className="btn-primary" style={{ width: '100%', marginTop: '1rem' }}>
            Save Configuration Settings
          </button>
        </form>
      </div>
    </div>
  );
};
