import React, { useState } from 'react';
import { timetableService } from '../services/api';

export const OCRPreview = () => {
  const [file, setFile] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!file) return;
    setLoading(true);
    const fd = new FormData();
    fd.append('file', file);
    try {
      const res = await timetableService.ocrUpload(fd);
      setResult(res.data.ocr_result);
    } catch (err) {
      alert('OCR error: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: '1.5rem', fontWeight: 700 }}>Timetable OCR Parser</h2>

      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <form onSubmit={handleUpload} style={{ display: 'flex', gap: '1rem' }}>
          <input type="file" className="form-control" onChange={(e) => setFile(e.target.files[0])} required />
          <button type="submit" className="btn-primary" disabled={loading}>
            {loading ? 'Parsing OCR Image...' : 'Extract Timetable Data'}
          </button>
        </form>
      </div>

      {result && (
        <div className="glass-card">
          <h3>Extracted OCR Entries</h3>
          <pre style={{ background: '#0f172a', color: '#10b981', padding: '1rem', borderRadius: '8px' }}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
