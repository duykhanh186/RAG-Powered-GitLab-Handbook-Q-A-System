import React, { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../services/api';
import StatusBadge from '../components/admin/StatusBadge';
import ConfirmModal from '../components/admin/ConfirmModal';

const formatDate = (iso) => {
  if (!iso) return 'N/A';
  return new Date(iso).toLocaleDateString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
  });
};

function Toast({ toasts, onRemove }) {
  return (
    <div className="toast-container">
      {toasts.map(t => (
        <div key={t.id} className={`toast toast--${t.type}`}>
          <span>{t.message}</span>
          <button onClick={() => onRemove(t.id)}>✕</button>
        </div>
      ))}
    </div>
  );
}

function CreateUserModal({ isOpen, onClose, onCreate }) {
  const [form, setForm] = useState({ username: '', email: '', password: '', role: 'user' });
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState('');

  useEffect(() => {
    if (!isOpen) { setForm({ username: '', email: '', password: '', role: 'user' }); setErr(''); }
  }, [isOpen]);

  const handleSubmit = async () => {
    if (!form.username.trim() || !form.email.trim() || !form.password.trim()) {
      setErr('Vui lòng điền đầy đủ thông tin.'); return;
    }
    setSubmitting(true); setErr('');
    try {
      await onCreate(form);
      onClose();
    } catch (e) {
      setErr(e.response?.data?.detail ?? 'Tạo user thất bại.');
    } finally {
      setSubmitting(false);
    }
  };

  if (!isOpen) return null;
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal__header">
          <h3 className="modal__title">Tạo người dùng mới</h3>
          <button className="modal__close" onClick={onClose}>✕</button>
        </div>
        <div className="modal__body">
          {[
            { label: 'Username *', key: 'username', type: 'text',     placeholder: 'Nhập username' },
            { label: 'Email *',    key: 'email',    type: 'email',    placeholder: 'Nhập email' },
            { label: 'Mật khẩu *', key: 'password', type: 'password', placeholder: 'Nhập mật khẩu' },
          ].map(f => (
            <div key={f.key} className="form-group">
              <label className="form-label">{f.label}</label>
              <input
                className="form-input"
                type={f.type}
                placeholder={f.placeholder}
                value={form[f.key]}
                onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
              />
            </div>
          ))}
          <div className="form-group">
            <label className="form-label">Role</label>
            <select className="form-select" value={form.role} onChange={e => setForm(p => ({ ...p, role: e.target.value }))}>
              <option value="user">User</option>
              <option value="admin">Admin</option>
            </select>
          </div>
          {err && <p className="form-error">{err}</p>}
        </div>
        <div className="modal__footer">
          <button className="btn btn--ghost" onClick={onClose}>Hủy</button>
          <button className="btn btn--primary" onClick={handleSubmit} disabled={submitting}>
            {submitting ? 'Đang tạo...' : 'Tạo user'}
          </button>
        </div>
      </div>
    </div>
  );
}

function AdminUsers() {
  const [users,        setUsers]        = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState('');
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [showCreate,   setShowCreate]   = useState(false);
  const [updatingRole, setUpdatingRole] = useState({});
  const [toasts,       setToasts]       = useState([]);
  const [search,       setSearch]       = useState('');

  const addToast = useCallback((message, type = 'success') => {
    const id = Date.now();
    setToasts(p => [...p, { id, message, type }]);
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 4000);
  }, []);

  const removeToast = useCallback((id) => setToasts(p => p.filter(t => t.id !== id)), []);

  const fetchUsers = useCallback(async () => {
    setLoading(true); setError('');
    try {
      const res = await adminAPI.getUsers();
      const raw = res.data?.users ?? res.data ?? [];
      setUsers(Array.isArray(raw) ? raw : []);
    } catch {
      setError('Không thể tải danh sách người dùng.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchUsers(); }, [fetchUsers]);

  const handleCreate = useCallback(async (form) => {
    await adminAPI.createUser(form);
    addToast(`✅ Đã tạo user: ${form.username}`);
    fetchUsers();
  }, [fetchUsers, addToast]);

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      await adminAPI.deleteUser(deleteTarget.id);
      addToast(`🗑️ Đã xóa: ${deleteTarget.username ?? deleteTarget.email}`);
      fetchUsers();
    } catch {
      addToast('Xóa user thất bại.', 'error');
    } finally {
      setDeleteTarget(null);
    }
  }, [deleteTarget, fetchUsers, addToast]);

  const handleRoleChange = useCallback(async (user, newRole) => {
    setUpdatingRole(p => ({ ...p, [user.id]: true }));
    try {
      await adminAPI.updateUserRole(user.id, newRole);
      addToast(`✅ Đổi role ${user.username} → ${newRole}`);
      fetchUsers();
    } catch {
      addToast('Đổi role thất bại.', 'error');
    } finally {
      setUpdatingRole(p => ({ ...p, [user.id]: false }));
    }
  }, [fetchUsers, addToast]);

  const filtered = users.filter(u =>
    (u.username ?? '').toLowerCase().includes(search.toLowerCase()) ||
    (u.email ?? '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="admin-page">
      <Toast toasts={toasts} onRemove={removeToast} />

      <div className="admin-page__header">
        <div>
          <h2 className="admin-page__title">Users</h2>
          <p className="admin-page__sub">{users.length} người dùng</p>
        </div>
        <div className="admin-page__actions">
          <button className="btn btn--primary" onClick={() => setShowCreate(true)}>➕ Tạo user</button>
          <button className="btn btn--ghost" onClick={fetchUsers} disabled={loading}>🔄</button>
        </div>
      </div>

      <div className="admin-search-bar">
        <span>🔍</span>
        <input type="text" placeholder="Tìm kiếm user..." value={search}
          onChange={e => setSearch(e.target.value)} className="admin-search-input" />
        {search && <button className="admin-search-clear" onClick={() => setSearch('')}>✕</button>}
      </div>

      <div className="admin-card">
        <div className="admin-table-wrap">
          {loading ? (
            <div style={{ padding: 8 }}>
              {[...Array(5)].map((_, i) => (
                <div key={i} className="skeleton-row" style={{ padding: '12px 16px' }}>
                  <div className="skeleton" style={{ width: '20%', height: 14 }} />
                  <div className="skeleton" style={{ width: '25%', height: 14 }} />
                  <div className="skeleton" style={{ width: 70, height: 22, borderRadius: 99 }} />
                  <div className="skeleton" style={{ width: '15%', height: 14 }} />
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="admin-empty">
              <span>⚠️</span><p>{error}</p>
              <button className="btn btn--ghost" onClick={fetchUsers}>Thử lại</button>
            </div>
          ) : filtered.length === 0 ? (
            <div className="admin-empty">
              <span>👥</span>
              <p>{search ? `Không tìm thấy "${search}"` : 'Chưa có người dùng nào'}</p>
            </div>
          ) : (
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Username</th><th>Email</th><th>Role</th><th>Ngày tạo</th><th>Hành động</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((user, i) => (
                  <tr key={user.id ?? i}>
                    <td><span className="admin-table__username">👤 {user.username ?? '—'}</span></td>
                    <td className="admin-table__meta">{user.email ?? '—'}</td>
                    <td>
                      <select
                        className="role-select"
                        value={user.role ?? 'user'}
                        disabled={updatingRole[user.id]}
                        onChange={e => handleRoleChange(user, e.target.value)}
                      >
                        <option value="user">User</option>
                        <option value="admin">Admin</option>
                      </select>
                    </td>
                    <td className="admin-table__meta">{formatDate(user.created_at)}</td>
                    <td>
                      <button className="btn btn--danger btn--sm" onClick={() => setDeleteTarget(user)} title="Xóa">🗑️</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <CreateUserModal isOpen={showCreate} onClose={() => setShowCreate(false)} onCreate={handleCreate} />
      <ConfirmModal
        isOpen={!!deleteTarget}
        title="Xóa người dùng"
        message={`Bạn có chắc muốn xóa user "${deleteTarget?.username ?? deleteTarget?.email}"?`}
        confirmLabel="Xóa"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

export default AdminUsers;