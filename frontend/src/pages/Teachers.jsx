import React, { useEffect, useState } from 'react';
import { teacherService } from '../services/api';

export const Teachers = () => {
  const [teachers, setTeachers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ username: '', password: '', full_name: '', department: '', email: '' });

  const fetchTeachers = () => {
    setLoading(true);
    teacherService.getTeachers()
      .then((res) => setTeachers(res.data.teachers || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchTeachers();
  }, []);

  const handleCreate = async (e) => {
    e.preventDefault();
    await teacherService.createTeacher(form);
    setShowModal(false);
    setForm({ username: '', password: '', full_name: '', department: '', email: '' });
    fetchTeachers();
  };

  const handleDelete = async (id) => {
    if (window.confirm('Delete teacher account?')) {
      await teacherService.deleteTeacher(id);
      fetchTeachers();
    }
  };

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0, fontWeight: 700 }}>Faculty Directory</h2>
        <button onClick={() => setShowModal(!showModal)} className="btn-primary">
          ➕ Add Faculty Member
        </button>
      </div>

      {showModal && (
        <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
          <h3>Add Faculty User</h3>
          <form onSubmit={handleCreate} style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
            <input type="text" className="form-control" placeholder="Username" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
            <input type="password" className="form-control" placeholder="Password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
            <input type="text" className="form-control" placeholder="Full Name" value={form.full_name} onChange={(e) => setForm({ ...form, full_name: e.target.value })} required />
            <input type="text" className="form-control" placeholder="Department" value={form.department} onChange={(e) => setForm({ ...form, department: e.target.value })} />
            <input type="email" className="form-control" placeholder="Email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} style={{ gridColumn: 'span 2' }} />
            <button type="submit" className="btn-primary" style={{ gridColumn: 'span 2' }}>Save Faculty</button>
          </form>
        </div>
      )}

      <div className="glass-card">
        <table className="custom-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Username</th>
              <th>Full Name</th>
              <th>Department</th>
              <th>Email</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="6" style={{ textAlign: 'center' }}>Loading teachers...</td></tr>
            ) : (
              teachers.map((t) => (
                <tr key={t.id}>
                  <td><b>{t.id}</b></td>
                  <td>{t.username}</td>
                  <td>{t.full_name}</td>
                  <td>{t.department || 'N/A'}</td>
                  <td>{t.email || 'N/A'}</td>
                  <td>
                    <button onClick={() => handleDelete(t.id)} className="btn-primary" style={{ background: '#ef4444', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
