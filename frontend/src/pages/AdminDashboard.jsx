import React, { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../services/api';
import StatusBadge from '../components/admin/StatusBadge';

const formatDate = (iso) => {
  if (!iso) return 'N/A';
  return new Date(iso).toLocaleString('vi-VN', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  });
};

const formatBytes = (bytes) => {
  if (!bytes) return '';
  const k = 1024, sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
};

function Skeleton({ width = '100%', height = '16px' }) {
  return <div className="skeleton" style={{ width, height, borderRadius: 6 }} />;
}

function StatCard({ icon, label, value, sub, color, loading }) {
  return (
    <div className={`admin-stat-card admin-stat-card--${color}`}>
      <div className="admin-stat-card__icon">{icon}</div>
      <div className="admin-stat-card__body">
        {loading
          ? <Skeleton width="60px" height="28px" />
          : <div className="admin-stat-card__value">{value ?? '—'}</div>
        }
        <div className="admin-stat-card__label">{label}</div>
        {sub && !loading && <div className="admin-stat-card__sub">{sub}</div>}
      </div>
    </div>
  );
}

function AdminDashboard() {
  const [status, setStatus] = useState(null);
  const [docs, setDocs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [lastSync, setLastSync] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      // Dùng 1 request duy nhất thay vì 2 request song song
      // (mỗi request cũ đều tạo connection Qdrant riêng → chậm)
      const [dashRes, docsRes] = await Promise.allSettled([
        adminAPI.getDashboard(),
        adminAPI.getDocuments(),
      ]);

      if (dashRes.status === 'fulfilled') {
        setStatus(dashRes.value.data);
      }
      if (docsRes.status === 'fulfilled') {
        const raw = docsRes.value.data?.documents ?? docsRes.value.data ?? [];
        setDocs(Array.isArray(raw) ? raw.slice(0, 8) : []);
      }
      setLastSync(new Date());
    } catch {
      setError('Không thể kết nối backend.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const s = status ?? {};
  const stats = [
    { icon: '📄', label: 'Tổng tài liệu', value: s.total_documents ?? s.document_count ?? '—', sub: `${s.total_vectors ?? s.total_chunks ?? 0} vectors`, color: 'blue' },
    { icon: '✅', label: 'Đã index', value: s.indexed_documents ?? s.embedded_count ?? '—', sub: 'Embedded xong', color: 'green' },
    { icon: '⚙️', label: 'Đang xử lý', value: s.processing_count ?? '—', sub: 'Processing / Uploading', color: 'yellow' },
    { icon: '❌', label: 'Thất bại', value: s.failed_count ?? '—', sub: 'Cần re-index', color: 'red' },
    { icon: '👥', label: 'Người dùng', value: s.total_users ?? '—', sub: null, color: 'purple' },
    { icon: '💬', label: 'Hội thoại', value: s.total_conversations ?? s.total_chunks ?? '—', sub: null, color: 'teal' },
  ];

  return (
    <div className="admin-page">
      <div className="admin-page__header">
        <div>
          <h2 className="admin-page__title">Dashboard</h2>
          <p className="admin-page__sub">Theo dõi trạng thái hệ thống RAG</p>
        </div>
        <div className="admin-page__actions">
          {lastSync && (
            <span className="admin-last-sync">
              Cập nhật lúc {lastSync.toLocaleTimeString('vi-VN')}
            </span>
          )}
          <button className="btn btn--primary" onClick={fetchAll} disabled={loading}>
            {loading ? '⏳ Đang tải...' : '🔄 Làm mới'}
          </button>
        </div>
      </div>

      {error && <div className="admin-error-bar">⚠️ {error}</div>}

      {/* Stat cards */}
      <div className="admin-stats-grid">
        {stats.map((st, i) => (
          <StatCard key={i} {...st} loading={loading} />
        ))}
      </div>

      {/* Bottom grid */}
      <div className="admin-grid-2">

        {/* Recent docs */}
        <div className="admin-card">
          <div className="admin-card__header">
            <h3>📁 Tài liệu gần đây</h3>
          </div>
          <div className="admin-card__body">
            {loading ? (
              <div className="skeleton-list">
                {[...Array(5)].map((_, i) => (
                  <div key={i} className="skeleton-row" style={{ padding: '10px 18px' }}>
                    <Skeleton width="55%" />
                    <Skeleton width="80px" height="22px" />
                  </div>
                ))}
              </div>
            ) : docs.length === 0 ? (
              <div className="admin-empty">
                <span>📭</span>
                <p>Chưa có tài liệu nào</p>
              </div>
            ) : (
              <div className="admin-doc-list">
                {docs.map((doc, i) => (
                  <div key={doc.id ?? i} className="admin-doc-row">
                    <div className="admin-doc-row__info">
                      <span className="admin-doc-row__name" title={doc.filename ?? doc.name}>
                        📄 {doc.filename ?? doc.name ?? `Document ${i + 1}`}
                      </span>
                      <span className="admin-doc-row__meta">
                        {formatDate(doc.upload_date ?? doc.created_at)}
                        {doc.file_size ? ` · ${formatBytes(doc.file_size)}` : ''}
                        {doc.chunk_count ? ` · ${doc.chunk_count} chunks` : ''}
                      </span>
                    </div>
                    <StatusBadge status={doc.status ?? doc.embedding_status} />
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Worker status */}
        <div className="admin-card">
          <div className="admin-card__header">
            <h3>⚡ Queue Workers</h3>
            <button className="btn btn--ghost btn--sm" onClick={fetchAll} disabled={loading}>🔄</button>
          </div>
          <div className="admin-card__body">
            {loading ? (
              <div className="skeleton-list">
                {[...Array(3)].map((_, i) => (
                  <div key={i} className="skeleton-row" style={{ padding: '12px 18px' }}>
                    <Skeleton width="50%" />
                    <Skeleton width="70px" height="22px" />
                  </div>
                ))}
              </div>
            ) : (
              <div className="admin-worker-list">
                <div className="admin-worker-row">
                  <div className="admin-worker-row__info">
                    <span className="admin-worker-row__name">🔧 Celery Worker</span>
                    <span className="admin-worker-row__meta">Embedding & Indexing</span>
                  </div>
                  <StatusBadge status={s.worker_status ?? s.celery_status ?? 'unknown'} />
                </div>
                <div className="admin-worker-row">
                  <div className="admin-worker-row__info">
                    <span className="admin-worker-row__name">📮 Redis Queue</span>
                    <span className="admin-worker-row__meta">Message broker</span>
                  </div>
                  <StatusBadge status={s.redis_status ?? 'unknown'} />
                </div>
                <div className="admin-worker-row">
                  <div className="admin-worker-row__info">
                    <span className="admin-worker-row__name">🗄️ Vector DB (Qdrant)</span>
                    <span className="admin-worker-row__meta">
                      {s.total_vectors ?? s.total_chunks ?? 0} vectors
                    </span>
                  </div>
                  <StatusBadge status={s.qdrant_status ?? s.status ?? 'unknown'} />
                </div>
              </div>
            )}
          </div>
        </div>

      </div>
    </div>
  );
}

export default AdminDashboard;