import React from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';

export const Navbar = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <header className="top-navbar">
      <div style={{ fontWeight: 600, fontSize: '1.1rem' }}>
        AI Smart Attendance Control Panel
      </div>

      <div style={{ display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{user?.full_name || 'User'}</div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'capitalize' }}>
            {user?.role || 'Guest'} {user?.department ? `• ${user.department}` : ''}
          </div>
        </div>

        <button onClick={handleLogout} className="btn-primary" style={{ background: '#ef4444', padding: '0.4rem 0.9rem', fontSize: '0.85rem' }}>
          Logout
        </button>
      </div>
    </header>
  );
};
