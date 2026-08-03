import React, { useEffect, useState } from 'react';
import { systemService } from '../services/api';

export const Subjects = () => {
  const [subjects, setSubjects] = useState([]);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [dept, setDept] = useState('Computer Science');

  const fetchSubjects = () => {
    systemService.getSubjects().then((res) => setSubjects(res.data.subjects || [])).catch(console.error);
  };

  useEffect(() => {
    fetchSubjects();
  }, []);

  const handleAdd = async (e) => {
    e.preventDefault();
    await systemService.addSubject({ code, name, department: dept });
    setCode('');
    setName('');
    fetchSubjects();
  };

  const handleDelete = async (id) => {
    if (window.confirm('Delete subject?')) {
      await systemService.deleteSubject(id);
      fetchSubjects();
    }
  };

  return (
    <div className="page-container">
      <h2 style={{ marginBottom: '1.5rem', fontWeight: 700 }}>Subjects Management</h2>

      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <h3>Add New Subject</h3>
        <form onSubmit={handleAdd} style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 1fr auto', gap: '1rem' }}>
          <input type="text" className="form-control" placeholder="Subject Code" value={code} onChange={(e) => setCode(e.target.value)} required />
          <input type="text" className="form-control" placeholder="Subject Name" value={name} onChange={(e) => setName(e.target.value)} required />
          <input type="text" className="form-control" placeholder="Department" value={dept} onChange={(e) => setDept(e.target.value)} required />
          <button type="submit" className="btn-primary">Add Subject</button>
        </form>
      </div>

      <div className="glass-card">
        <table className="custom-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Code</th>
              <th>Name</th>
              <th>Department</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {subjects.map((s) => (
              <tr key={s.id}>
                <td><b>{s.id}</b></td>
                <td>{s.code}</td>
                <td>{s.name}</td>
                <td>{s.department}</td>
                <td>
                  <button onClick={() => handleDelete(s.id)} className="btn-primary" style={{ background: '#ef4444', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}>
                    Delete
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
};
