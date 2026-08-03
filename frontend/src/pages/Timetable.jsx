import React, { useEffect, useState } from 'react';
import { timetableService } from '../services/api';

export const Timetable = () => {
  const [timetable, setTimetable] = useState([]);
  const [sem, setSem] = useState('Semester 1');
  const [div, setDiv] = useState('Division A');
  const [loading, setLoading] = useState(true);

  const fetchTimetable = () => {
    setLoading(true);
    timetableService.getTimetable(sem, div)
      .then((res) => setTimetable(res.data.timetable || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchTimetable();
  }, [sem, div]);

  return (
    <div className="page-container">
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <h2 style={{ margin: 0, fontWeight: 700 }}>Academic Timetable Schedule</h2>

        <div style={{ display: 'flex', gap: '1rem' }}>
          <select className="form-control" value={sem} onChange={(e) => setSem(e.target.value)}>
            <option>Semester 1</option>
            <option>Semester 2</option>
            <option>Semester 3</option>
            <option>Semester 4</option>
          </select>
          <select className="form-control" value={div} onChange={(e) => setDiv(e.target.value)}>
            <option>Division A</option>
            <option>Division B</option>
          </select>
        </div>
      </div>

      <div className="glass-card">
        <table className="custom-table">
          <thead>
            <tr>
              <th>Day</th>
              <th>Time Slot</th>
              <th>Subject</th>
              <th>Faculty</th>
              <th>Room</th>
            </tr>
          </thead>
          <tbody>
            {loading ? (
              <tr><td colSpan="5" style={{ textAlign: 'center' }}>Loading schedule...</td></tr>
            ) : timetable.length === 0 ? (
              <tr><td colSpan="5" style={{ textAlign: 'center', color: 'var(--text-muted)' }}>No timetable entries set for this semester/division.</td></tr>
            ) : (
              timetable.map((item, idx) => (
                <tr key={idx}>
                  <td><b>{item.day_of_week}</b></td>
                  <td>{item.time_slot}</td>
                  <td>{item.subject_name}</td>
                  <td>{item.teacher_name}</td>
                  <td>{item.classroom_room}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
