import React, { useState } from 'react';
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom';

const NAV_ITEMS = [
  { to: '/admin/dashboard', icon: '📊', label: 'Dashboard' },
  { to: '/admin/documents', icon: '📁', label: 'Documents' },
  { to: '/admin/users',     icon: '👥', label: 'Users'     },
  { to: '/admin/settings',  icon: '⚙️',  label: 'Settings'  },
];

const LABELS = {
  admin:     'Admin',
  dashboard: 'Dashboard',
  documents: 'Documents',
  users:     'Users',
  settings:  'Settings',
};

function BreadCrumb() {
  const { pathname } = useLocation();
  const parts = pathname.split('/').filter(Boolean);
  return (
    <div className="breadcrumb">
      {parts.map((p, i) => (
        <span key={i}>
          {i > 0 && <span className="breadcrumb__sep"> / </span>}
          <span className={i === parts.length - 1 ? 'breadcrumb__current' : 'breadcrumb__item'}>
            {LABELS[p] ?? p}
          </span>
        </span>
      ))}
    </div>
  );
}

function AdminLayout() {
  const [collapsed, setCollapsed] = useState(false);
  const navigate = useNavigate();

  return (
    <div className="admin-layout">

      {/* ── SIDEBAR ── */}
      <aside className={`admin-sidebar ${collapsed ? 'admin-sidebar--collapsed' : ''}`}>

        <div className="admin-sidebar__top">
          {!collapsed && (
            <div className="admin-sidebar__brand">
              <span className="brand-icon">🦊</span>
              <span className="brand-name">Admin Panel</span>
            </div>
          )}
          <button
            className="admin-sidebar__toggle"
            onClick={() => setCollapsed(p => !p)}
            title={collapsed ? 'Mở rộng' : 'Thu gọn'}
          >
            {collapsed ? '→' : '←'}
          </button>
        </div>

        <nav className="admin-sidebar__nav">
          {NAV_ITEMS.map(item => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `admin-nav-link ${isActive ? 'admin-nav-link--active' : ''}`
              }
              title={collapsed ? item.label : undefined}
            >
              <span className="admin-nav-link__icon">{item.icon}</span>
              {!collapsed && (
                <span className="admin-nav-link__label">{item.label}</span>
              )}
            </NavLink>
          ))}
        </nav>

        <div className="admin-sidebar__footer">
          <button
            className="admin-back-btn"
            onClick={() => navigate('/')}
            title="Quay lại Chat"
          >
            <span>💬</span>
            {!collapsed && <span>Quay lại Chat</span>}
          </button>
        </div>

      </aside>

      {/* ── MAIN ── */}
      <div className="admin-main">
        <header className="admin-header">
          <div className="admin-header__left">
            <BreadCrumb />
          </div>
          <div className="admin-header__right">
            <span className="admin-header__badge">🔧 Admin</span>
          </div>
        </header>
        <div className="admin-content">
          <Outlet />
        </div>
      </div>

    </div>
  );
}

export default AdminLayout;