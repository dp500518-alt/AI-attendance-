import React, { useState } from 'react';
import { classroomService } from '../services/api';

export const Classroom = () => {
  const [selectedFile, setSelectedFile] = useState(null);
  const [subject, setSubject] = useState('Data Structures');
  const [teacher, setTeacher] = useState('Prof. Sharma');
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile) return;

    setLoading(true);
    setResult(null);

    const formData = new FormData();
    formData.append('classroom_photo', selectedFile);
    formData.append('subject_name', subject);
    formData.append('teacher_name', teacher);

    try {
      const res = await classroomService.uploadPhoto(formData);
      setResult(res.data);
    } catch (err) {
      alert('Error analyzing classroom image: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: '1.5rem', fontWeight: 700 }}>Live Classroom AI Face Attendance</h2>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1.5rem' }}>
        <div className="glass-card">
          <h3>Upload Classroom Photo</h3>
          <form onSubmit={handleUpload}>
            <div className="form-group">
              <label>Select Lecture Subject</label>
              <input type="text" className="form-control" value={subject} onChange={(e) => setSubject(e.target.value)} required />
            </div>

            <div className="form-group">
              <label>Faculty Name</label>
              <input type="text" className="form-control" value={teacher} onChange={(e) => setTeacher(e.target.value)} required />
            </div>

            <div className="form-group">
              <label>Upload Classroom Image</label>
              <input type="file" accept="image/*" className="form-control" onChange={(e) => setSelectedFile(e.target.files[0])} required />
            </div>

            <button type="submit" className="btn-primary" disabled={loading} style={{ width: '100%', marginTop: '1rem' }}>
              {loading ? 'Processing YOLO & SFace AI Engine...' : 'Run Face Recognition & Mark Attendance'}
            </button>
          </form>
        </div>

        <div className="glass-card">
          <h3>AI Recognition Results</h3>
          {result ? (
            <div>
              <div style={{ padding: '0.8rem', background: 'rgba(16, 185, 129, 0.1)', borderRadius: '8px', marginBottom: '1rem', color: '#10b981', fontWeight: 600 }}>
                ✅ Detected {result.faces_detected || 0} faces in image!
              </div>

              <h4>Marked Attendance:</h4>
              <table className="custom-table">
                <thead>
                  <tr>
                    <th>Student ID</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {(result.marked_attendance || []).map((m, i) => (
                    <tr key={i}>
                      <td><b>{m.student_id}</b></td>
                      <td><span className="badge badge-success">Present</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p style={{ color: 'var(--text-muted)' }}>Upload a classroom snapshot to view instant AI face detection & attendance results.</p>
          )}
        </div>
      </div>
    </div>
  );
};
