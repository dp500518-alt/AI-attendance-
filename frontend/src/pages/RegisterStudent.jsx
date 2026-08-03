import React, { useState } from 'react';
import { studentService } from '../services/api';
import { useNavigate } from 'react-router-dom';

export const RegisterStudent = () => {
  const [form, setForm] = useState({
    student_id: '',
    roll_number: '',
    name: '',
    department: 'Computer Science',
    semester: 'Semester 1',
    division: 'Division A',
    email: '',
    phone: '',
  });
  const [msg, setMsg] = useState({ text: '', type: '' });
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setMsg({ text: '', type: '' });

    try {
      const res = await studentService.registerStudent(form);
      if (res.data.success) {
        setMsg({ text: res.data.message || 'Student registered successfully!', type: 'success' });
        setTimeout(() => navigate('/students'), 1500);
      } else {
        setMsg({ text: res.data.message || 'Registration failed.', type: 'danger' });
      }
    } catch (err) {
      setMsg({ text: err.message || 'Network error occurred.', type: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="page-container" style={{ maxWidth: '700px' }}>
      <h2 style={{ marginBottom: '1.5rem', fontWeight: 700 }}>Register New Student</h2>

      {msg.text && (
        <div style={{
          padding: '0.8rem 1rem',
          borderRadius: '8px',
          marginBottom: '1.25rem',
          background: msg.type === 'success' ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
          color: msg.type === 'success' ? '#10b981' : '#ef4444',
          border: `1px solid ${msg.type === 'success' ? '#10b981' : '#ef4444'}`
        }}>
          {msg.text}
        </div>
      )}

      <div className="glass-card">
        <form onSubmit={handleSubmit}>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label>Student ID</label>
              <input type="text" name="student_id" className="form-control" placeholder="e.g. S101" value={form.student_id} onChange={handleChange} required />
            </div>

            <div className="form-group">
              <label>Roll Number</label>
              <input type="text" name="roll_number" className="form-control" placeholder="e.g. 2301" value={form.roll_number} onChange={handleChange} required />
            </div>
          </div>

          <div className="form-group">
            <label>Full Name</label>
            <input type="text" name="name" className="form-control" placeholder="Student Full Name" value={form.name} onChange={handleChange} required />
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label>Department</label>
              <input type="text" name="department" className="form-control" value={form.department} onChange={handleChange} required />
            </div>

            <div className="form-group">
              <label>Semester</label>
              <select name="semester" className="form-control" value={form.semester} onChange={handleChange}>
                <option>Semester 1</option>
                <option>Semester 2</option>
                <option>Semester 3</option>
                <option>Semester 4</option>
                <option>Semester 5</option>
                <option>Semester 6</option>
              </select>
            </div>

            <div className="form-group">
              <label>Division</label>
              <select name="division" className="form-control" value={form.division} onChange={handleChange}>
                <option>Division A</option>
                <option>Division B</option>
                <option>Division C</option>
              </select>
            </div>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <div className="form-group">
              <label>Email Address</label>
              <input type="email" name="email" className="form-control" placeholder="student@college.edu" value={form.email} onChange={handleChange} />
            </div>

            <div className="form-group">
              <label>Phone Number</label>
              <input type="text" name="phone" className="form-control" placeholder="+91 9876543210" value={form.phone} onChange={handleChange} />
            </div>
          </div>

          <button type="submit" className="btn-primary" disabled={loading} style={{ width: '100%', marginTop: '1rem', padding: '0.75rem' }}>
            {loading ? 'Saving Student...' : 'Register Student & Save to Dataset'}
          </button>
        </form>
      </div>
    </div>
  );
};
