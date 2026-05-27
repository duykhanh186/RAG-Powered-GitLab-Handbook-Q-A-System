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
    // Validate chunk_size
    const cs = parseInt(chunkSize);
    const co = parseInt(chunkOverlap);
    if (chunkSize && (isNaN(cs) || cs < 100 || cs > 5000)) {
      addToast('Chunk size phải nằm trong khoảng 100 - 5000.', 'error');
      return;
    }
    if (chunkOverlap && (isNaN(co) || co < 0)) {
      addToast('Chunk overlap không được nhỏ hơn 0.', 'error');
      return;
    }
    if (cs && co >= cs) {
      addToast(`Chunk overlap (${co}) phải nhỏ hơn chunk size (${cs}).`, 'error');
      return;
    }

    setSaving(true);
    try {
      const res = await adminAPI.updateSettings({
        embedding_model: embeddingModel,
        chunk_size:      cs || undefined,
        chunk_overlap:   co != null && !isNaN(co) ? co : undefined,
      });
      addToast(res.data?.message || `✅ Đã lưu (chunk_size=${cs}, overlap=${co})`);
    } catch (err) {
      const detail = err.response?.data?.detail;
      addToast(detail || 'Lưu cấu hình thất bại.', 'error');
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

        <SettingCard title="Embedding & Chunking" icon="🧠" loading={loading}>
          <SettingRow label="Model hiện tại" hint="Model dùng để tạo vector nhúng">
            <input className="form-input form-input--sm" value={embeddingModel}
              onChange={e => setEmbeddingModel(e.target.value)} placeholder="vd: sentence-transformers/..." />
          </SettingRow>
          <SettingRow label="Chunk size" hint="Độ dài mỗi đoạn văn bản (100 – 5000 ký tự)">
            <input className="form-input form-input--sm" type="number" value={chunkSize}
              min="100" max="5000" step="50"
              onChange={e => setChunkSize(e.target.value)} placeholder="vd: 512" />
          </SettingRow>
          <SettingRow label="Chunk overlap" hint={`Số ký tự chồng lấp giữa các chunk (0 – ${(parseInt(chunkSize) || 512) - 1})`}>
            <input className="form-input form-input--sm" type="number" value={chunkOverlap}
              min="0" max={Math.max(0, (parseInt(chunkSize) || 512) - 1)} step="10"
              onChange={e => setChunkOverlap(e.target.value)} placeholder="vd: 50" />
          </SettingRow>
          <div style={{ padding: '10px 18px', fontSize: 11, color: '#888', borderTop: '1px solid rgba(255,255,255,0.05)' }}>
            ⚠️ Thay đổi chunk size / overlap chỉ áp dụng cho tài liệu được nạp <b>sau khi lưu</b>. Tài liệu cũ cần Re-index.
          </div>
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