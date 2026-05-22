import React, { useState, useEffect, useCallback, useRef } from 'react';
import { adminAPI } from '../services/api';
import StatusBadge from '../components/admin/StatusBadge';
import ConfirmModal from '../components/admin/ConfirmModal';

const ACCEPTED = ['.pdf', '.docx', '.txt', '.md', '.json'];

const formatDate = (iso) => {
  if (!iso) return 'N/A';
  return new Date(iso).toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
};

const formatBytes = (bytes) => {
  if (!bytes) return '—';
  const k = 1024, sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
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

function UploadZone({ onFiles }) {
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef(null);

  const handleDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files).filter(f =>
      ACCEPTED.some(ext => f.name.toLowerCase().endsWith(ext))
    );
    if (files.length) onFiles(files);
  };

  return (
    <div
      className={`upload-zone ${dragging ? 'upload-zone--dragging' : ''}`}
      onDragOver={e => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept={ACCEPTED.join(',')}
        multiple
        style={{ display: 'none' }}
        onChange={e => onFiles(Array.from(e.target.files))}
      />
      <div className="upload-zone__icon">📤</div>
      <p className="upload-zone__text">
        Kéo thả file vào đây hoặc <span className="upload-zone__link">chọn file</span>
      </p>
      <p className="upload-zone__hint">Hỗ trợ: PDF, DOCX, TXT, MD, JSON</p>
    </div>
  );
}

function AdminDocuments() {
  const [docs,         setDocs]         = useState([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState('');
  const [uploads,      setUploads]      = useState([]);
  const [showUpload,   setShowUpload]   = useState(false);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [reindexing,   setReindexing]   = useState({});
  const [toasts,       setToasts]       = useState([]);
  const [search,       setSearch]       = useState('');

  const addToast = useCallback((message, type = 'success') => {
    const id = Date.now();
    setToasts(p => [...p, { id, message, type }]);
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 4000);
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(p => p.filter(t => t.id !== id));
  }, []);

  const fetchDocs = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const res = await adminAPI.getDocuments();
      const raw = res.data?.documents ?? res.data ?? [];
      setDocs(Array.isArray(raw) ? raw : []);
    } catch {
      setError('Không thể tải danh sách tài liệu.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  const handleFiles = useCallback(async (files) => {
    const newUploads = files.map(f => ({
      id: `${Date.now()}_${f.name}`,
      file: f,
      status: 'uploading',
      progress: 0,
      error: null,
    }));
    setUploads(p => [...p, ...newUploads]);

    for (const item of newUploads) {
      try {
        await adminAPI.uploadDocument(item.file, (pct) => {
          setUploads(p => p.map(u =>
            u.id === item.id ? { ...u, progress: pct } : u
          ));
        });
        setUploads(p => p.map(u =>
          u.id === item.id ? { ...u, status: 'embedded', progress: 100 } : u
        ));
        addToast(`✅ Upload thành công: ${item.file.name}`);
      } catch (e) {
        const msg = e.response?.data?.detail ?? 'Upload thất bại';
        setUploads(p => p.map(u =>
          u.id === item.id ? { ...u, status: 'failed', error: msg } : u
        ));
        addToast(`❌ ${item.file.name}: ${msg}`, 'error');
      }
    }
    fetchDocs();
  }, [fetchDocs, addToast]);

  const handleDelete = useCallback(async () => {
    if (!deleteTarget) return;
    try {
      await adminAPI.deleteDocument(deleteTarget.id);
      addToast(`🗑️ Đã xóa: ${deleteTarget.filename ?? deleteTarget.name}`);
      fetchDocs();
    } catch {
      addToast('Xóa thất bại.', 'error');
    } finally {
      setDeleteTarget(null);
    }
  }, [deleteTarget, fetchDocs, addToast]);

  const handleReindex = useCallback(async (doc) => {
    setReindexing(p => ({ ...p, [doc.id]: true }));
    try {
      await adminAPI.reindexDocument(doc.id);
      addToast(`🔄 Đang re-index: ${doc.filename ?? doc.name}`);
      setTimeout(fetchDocs, 2000);
    } catch {
      addToast('Re-index thất bại.', 'error');
    } finally {
      setReindexing(p => ({ ...p, [doc.id]: false }));
    }
  }, [fetchDocs, addToast]);

  const filtered = docs.filter(d =>
    (d.filename ?? d.name ?? '').toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="admin-page">
      <Toast toasts={toasts} onRemove={removeToast} />

      <div className="admin-page__header">
        <div>
          <h2 className="admin-page__title">Documents</h2>
          <p className="admin-page__sub">{docs.length} tài liệu trong hệ thống</p>
        </div>
        <div className="admin-page__actions">
          <button className="btn btn--primary" onClick={() => setShowUpload(p => !p)}>
            {showUpload ? '✕ Đóng' : '📤 Upload'}
          </button>
          <button className="btn btn--ghost" onClick={fetchDocs} disabled={loading}>🔄</button>
        </div>
      </div>

      {showUpload && (
        <div className="admin-card" style={{ marginBottom: 20 }}>
          <div className="admin-card__header"><h3>Upload tài liệu mới</h3></div>
          <div className="admin-card__body" style={{ padding: 16 }}>
            <UploadZone onFiles={handleFiles} />
            {uploads.length > 0 && (
              <div className="upload-list">
                {uploads.map(u => (
                  <div key={u.id} className="upload-item">
                    <div className="upload-item__info">
                      <span className="upload-item__name">📄 {u.file.name}</span>
                      <StatusBadge status={u.status} />
                    </div>
                    {u.status === 'uploading' && (
                      <div className="progress-bar">
                        <div className="progress-bar__fill" style={{ width: `${u.progress}%` }} />
                      </div>
                    )}
                    {u.error && <p className="upload-item__error">{u.error}</p>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="admin-search-bar">
        <span>🔍</span>
        <input
          type="text"
          placeholder="Tìm kiếm tài liệu..."
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="admin-search-input"
        />
        {search && (
          <button className="admin-search-clear" onClick={() => setSearch('')}>✕</button>
        )}
      </div>

      <div className="admin-card">
        <div className="admin-table-wrap">
          {loading ? (
            <div style={{ padding: 8 }}>
              {[...Array(5)].map((_, i) => (
                <div key={i} className="skeleton-row" style={{ padding: '12px 16px' }}>
                  <div className="skeleton" style={{ width: '30%', height: 14 }} />
                  <div className="skeleton" style={{ width: '15%', height: 14 }} />
                  <div className="skeleton" style={{ width: 80, height: 22, borderRadius: 99 }} />
                  <div className="skeleton" style={{ width: '10%', height: 14 }} />
                </div>
              ))}
            </div>
          ) : error ? (
            <div className="admin-empty">
              <span>⚠️</span><p>{error}</p>
              <button className="btn btn--ghost" onClick={fetchDocs}>Thử lại</button>
            </div>
          ) : filtered.length === 0 ? (
            <div className="admin-empty">
              <span>📭</span>
              <p>{search ? `Không tìm thấy "${search}"` : 'Chưa có tài liệu nào'}</p>
            </div>
          ) : (
            <table className="admin-table">
              <thead>
                <tr>
                  <th>Tên file</th>
                  <th>Ngày upload</th>
                  <th>Trạng thái</th>
                  <th>Chunks</th>
                  <th>Kích thước</th>
                  <th>Hành động</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((doc, i) => (
                  <tr key={doc.id ?? i}>
                    <td><span className="admin-table__filename">📄 {doc.filename ?? doc.name ?? `Document ${i + 1}`}</span></td>
                    <td className="admin-table__meta">{formatDate(doc.upload_date ?? doc.created_at)}</td>
                    <td><StatusBadge status={doc.status ?? doc.embedding_status} /></td>
                    <td className="admin-table__meta">{doc.chunk_count ?? '—'}</td>
                    <td className="admin-table__meta">{formatBytes(doc.file_size)}</td>
                    <td>
                      <div className="admin-table__actions">
                        <button
                          className="btn btn--ghost btn--sm"
                          onClick={() => handleReindex(doc)}
                          disabled={reindexing[doc.id]}
                          title="Re-index"
                        >
                          {reindexing[doc.id] ? '⏳' : '🔄'}
                        </button>
                        <button
                          className="btn btn--danger btn--sm"
                          onClick={() => setDeleteTarget(doc)}
                          title="Xóa"
                        >
                          🗑️
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      <ConfirmModal
        isOpen={!!deleteTarget}
        title="Xóa tài liệu"
        message={`Bạn có chắc muốn xóa "${deleteTarget?.filename ?? deleteTarget?.name}"? Hành động này không thể hoàn tác.`}
        confirmLabel="Xóa"
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}

export default AdminDocuments;