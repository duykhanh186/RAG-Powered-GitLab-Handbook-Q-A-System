import React, { useState, useEffect, useCallback } from 'react';
import { adminAPI } from '../services/api';
import StatusBadge from '../components/admin/StatusBadge';

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

function SettingRow({ label, hint, children }) {
  return (
    <div className="setting-row">
      <div className="setting-row__left">
        <span className="setting-row__label">{label}</span>
        {hint && <span className="setting-row__hint">{hint}</span>}
      </div>
      <div className="setting-row__right">{children}</div>
    </div>
  );
}

function SettingCard({ title, icon, children, loading }) {
  return (
    <div className="admin-card">
      <div className="admin-card__header">
        <h3>{icon} {title}</h3>
      </div>
      <div className="admin-card__body">
        {loading ? (
          <div style={{ padding: 8 }}>
            {[...Array(3)].map((_, i) => (
              <div key={i} className="skeleton-row" style={{ padding: '14px 18px' }}>
                <div className="skeleton" style={{ width: '40%', height: 14 }} />
                <div className="skeleton" style={{ width: '25%', height: 14 }} />
              </div>
            ))}
          </div>
        ) : children}
      </div>
    </div>
  );
}

function AdminSettings() {
  const [status,         setStatus]         = useState(null);
  const [loading,        setLoading]        = useState(true);
  const [saving,         setSaving]         = useState(false);
  const [toasts,         setToasts]         = useState([]);
  const [embeddingModel, setEmbeddingModel] = useState('');
  const [chunkSize,      setChunkSize]      = useState('');
  const [chunkOverlap,   setChunkOverlap]   = useState('');

  const addToast = useCallback((message, type = 'success') => {
    const id = Date.now();
    setToasts(p => [...p, { id, message, type }]);
    setTimeout(() => setToasts(p => p.filter(t => t.id !== id)), 4000);
  }, []);

  const removeToast = useCallback((id) => setToasts(p => p.filter(t => t.id !== id)), []);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    try {
      const settingsRes = await adminAPI.getSettings();
      if (settingsRes.status === 200 || settingsRes.data) {
        const d = settingsRes.data;
        // Đổ dữ liệu status từ settings (đã có Qdrant, Redis, workers)
        setStatus(d);
        setEmbeddingModel(d?.embedding_model ?? d?.model ?? '');
        setChunkSize(String(d?.chunk_size ?? ''));
        setChunkOverlap(String(d?.chunk_overlap ?? ''));
      }
    } catch {
      addToast('Không thể tải cấu hình.', 'error');
    } finally {
      setLoading(false);
    }
  }, [addToast]);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await adminAPI.updateSettings({
        embedding_model: embeddingModel,
        chunk_size:      parseInt(chunkSize)    || undefined,
        chunk_overlap:   parseInt(chunkOverlap) || undefined,
      });
      addToast('✅ Đã lưu cấu hình');
    } catch {
      addToast('Lưu cấu hình thất bại.', 'error');
    } finally {
      setSaving(false);
    }
  }, [embeddingModel, chunkSize, chunkOverlap, addToast]);

  const s = status ?? {};

  return (
    <div className="admin-page">
      <Toast toasts={toasts} onRemove={removeToast} />

      <div className="admin-page__header">
        <div>
          <h2 className="admin-page__title">Settings</h2>
          <p className="admin-page__sub">Cấu hình hệ thống RAG</p>
        </div>
        <div className="admin-page__actions">
          <button className="btn btn--ghost" onClick={fetchAll} disabled={loading}>🔄 Làm mới</button>
          <button className="btn btn--primary" onClick={handleSave} disabled={saving || loading}>
            {saving ? '⏳ Đang lưu...' : '💾 Lưu cấu hình'}
          </button>
        </div>
      </div>

      <div className="settings-grid">

        <SettingCard title="API Keys" icon="🔑" loading={loading}>
          <SettingRow label="Groq API Key" hint="Dùng cho LLM inference">
            {s.groq_api_key_set
              ? <div className="api-key-row"><StatusBadge status="active" /><span className="api-key-mask">Đã cấu hình</span></div>
              : <StatusBadge status="error" />
            }
          </SettingRow>
          <SettingRow label="OpenAI API Key" hint="Dùng cho embedding (nếu có)">
            {s.openai_api_key_set
              ? <div className="api-key-row"><StatusBadge status="active" /><span className="api-key-mask">Đã cấu hình</span></div>
              : <span className="setting-row__muted">Không dùng</span>
            }
          </SettingRow>
        </SettingCard>

        <SettingCard title="Embedding Model" icon="🧠" loading={loading}>
          <SettingRow label="Model hiện tại" hint="Model dùng để tạo vector">
            <input className="form-input form-input--sm" value={embeddingModel}
              onChange={e => setEmbeddingModel(e.target.value)} placeholder="vd: text-embedding-ada-002" />
          </SettingRow>
          <SettingRow label="Chunk size" hint="Số token mỗi chunk">
            <input className="form-input form-input--sm" type="number" value={chunkSize}
              onChange={e => setChunkSize(e.target.value)} placeholder="vd: 512" />
          </SettingRow>
          <SettingRow label="Chunk overlap" hint="Số token overlap giữa các chunk">
            <input className="form-input form-input--sm" type="number" value={chunkOverlap}
              onChange={e => setChunkOverlap(e.target.value)} placeholder="vd: 50" />
          </SettingRow>
        </SettingCard>

        <SettingCard title="Vector Database" icon="🗄️" loading={loading}>
          <SettingRow label="Provider">
            <span className="setting-row__value">Qdrant</span>
          </SettingRow>
          <SettingRow label="Trạng thái">
            <StatusBadge status={s.qdrant_status ?? s.status ?? 'unknown'} />
          </SettingRow>
          <SettingRow label="Tổng vectors">
            <span className="setting-row__value">{s.total_vectors ?? s.total_chunks ?? '—'}</span>
          </SettingRow>
          <SettingRow label="Collection">
            <span className="setting-row__value">{s.collection_name ?? '—'}</span>
          </SettingRow>
        </SettingCard>

        <SettingCard title="Queue Workers" icon="⚡" loading={loading}>
          <SettingRow label="Celery Worker">
            <StatusBadge status={s.worker_status ?? s.celery_status ?? 'unknown'} />
          </SettingRow>
          <SettingRow label="Redis Broker">
            <StatusBadge status={s.redis_status ?? 'unknown'} />
          </SettingRow>
          <SettingRow label="Queue hiện tại">
            <span className="setting-row__value">{s.queue_length != null ? `${s.queue_length} tasks` : '—'}</span>
          </SettingRow>
        </SettingCard>

        <SettingCard title="Database" icon="🐘" loading={loading}>
          <SettingRow label="Provider">
            <span className="setting-row__value">PostgreSQL</span>
          </SettingRow>
          <SettingRow label="Trạng thái">
            <StatusBadge status={s.db_status ?? 'unknown'} />
          </SettingRow>
          <SettingRow label="Tổng users">
            <span className="setting-row__value">{s.total_users ?? '—'}</span>
          </SettingRow>
          <SettingRow label="Tổng conversations">
            <span className="setting-row__value">{s.total_conversations ?? '—'}</span>
          </SettingRow>
        </SettingCard>

      </div>
    </div>
  );
}

export default AdminSettings;