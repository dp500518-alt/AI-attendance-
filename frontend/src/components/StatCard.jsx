import React from 'react';

export const StatCard = ({ icon, title, value, type = 'primary', subtitle }) => {
  return (
    <div className="glass-card stat-card">
      <div className={`stat-icon ${type}`}>{icon}</div>
      <div className="stat-info">
        <h3>{value}</h3>
        <p>{title}</p>
        {subtitle && <small style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{subtitle}</small>}
      </div>
    </div>
  );
};
