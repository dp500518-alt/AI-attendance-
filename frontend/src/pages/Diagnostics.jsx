import React, { useEffect, useState } from 'react';
import { systemService } from '../services/api';

export const Diagnostics = () => {
  const [diag, setDiag] = useState(null);

  useEffect(() => {
    systemService.getDiagnostics().then((res) => setDiag(res.data)).catch(console.error);
  }, []);

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: '1.5rem', fontWeight: 700 }}>System Storage & AI Diagnostics</h2>

      <div className="glass-card">
        <h3>System Storage Metrics</h3>
        <p><b>Storage Root:</b> <code>{diag?.storage_root}</code></p>
        <p><b>Database Location:</b> <code>{diag?.db_location}</code></p>
        <p><b>Dataset Location:</b> <code>{diag?.dataset_location}</code></p>
        <p><b>Embeddings Location:</b> <code>{diag?.embeddings_location}</code></p>

        <hr style={{ border: 'none', borderTop: '1px solid var(--card-border)', margin: '1.5rem 0' }} />

        <h3>Storage & Database Counts</h3>
        <ul>
          <li>Total Registered Students: <b>{diag?.total_students}</b></li>
          <li>Dataset Folders: <b>{diag?.total_dataset_folders}</b></li>
          <li>Extracted Embeddings: <b>{diag?.total_embeddings}</b></li>
          <li>Database Integrity Check: <span className="badge badge-success">{diag?.db_integrity || 'OK'}</span></li>
          <li>Disk Free Space: <b>{diag?.free_gb} GB</b> / <b>{diag?.total_gb} GB</b></li>
        </ul>
      </div>
    </div>
  );
};
