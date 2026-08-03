import React, { useEffect, useState } from 'react';
import { studentService } from '../services/api';
import { Link } from 'react-router-dom';

export const Students = () => {
  const [students, setStudents] = useState([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);

  const fetchStudents = () => {
    setLoading(true);
    studentService.getStudents('', '', query)
      .then((res) => setStudents(res.data.students || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchStudents();
  }, [query]);

  const handleDelete = async (studentId) => {
    if (window.confirm(`Are you sure you want to delete student ID ${studentId}?`)) {
      await studentService.deleteStudent(studentId);
      fetchStudents();
    }
  };

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0, fontWeight: 700 }}>Student Directory</h2>
        <Link to="/register-student" className="btn-primary">
          ➕ Register New Student
        </Link>
      </div>

      <div className="glass-card" style={{ marginBottom: '1.5rem' }}>
        <input
          type="text"
          className="form-control"
          placeholder="Search student by Name, Roll No, or Student ID..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </div>

      <div className="glass-card">
        <div className="table-responsive">
          <table className="custom-table">
            <thead>
              <tr>
                <th>Photo</th>
                <th>Student ID</th>
                <th>Roll No</th>
                <th>Full Name</th>
                <th>Department</th>
                <th>Semester / Div</th>
                <th>AI Training Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="8" style={{ textAlign: 'center' }}>Loading directory...</td></tr>
              ) : students.length === 0 ? (
                <tr><td colSpan="8" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No student records found.</td></tr>
              ) : (
                students.map((s) => (
                  <tr key={s.id}>
                    <td>
                      <img
                        src={`http://localhost:5000/api/students/photo/${s.id}`}
                        alt={s.name}
                        style={{ width: '40px', height: '40px', borderRadius: '50%', objectFit: 'cover' }}
                      />
                    </td>
                    <td><b>{s.id}</b></td>
                    <td>{s.roll_number}</td>
                    <td>{s.name}</td>
                    <td>{s.department}</td>
                    <td>{s.semester} ({s.division})</td>
                    <td>
                      {s.has_embedding ? (
                        <span className="badge badge-success">Embedding Ready</span>
                      ) : (
                        <span className="badge badge-warning">Needs Training</span>
                      )}
                    </td>
                    <td>
                      <button
                        onClick={() => handleDelete(s.id)}
                        className="btn-primary"
                        style={{ background: '#ef4444', padding: '0.3rem 0.6rem', fontSize: '0.8rem' }}
                      >
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
    </div>
  );
};
