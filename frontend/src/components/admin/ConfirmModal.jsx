import React, { useEffect } from 'react';

function ConfirmModal({ isOpen, title, message, confirmLabel = 'Xóa', onConfirm, onCancel, danger = true }) {
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e) => { if (e.key === 'Escape') onCancel(); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, onCancel]);

  if (!isOpen) return null;

  return (
    <div className="modal-overlay" onClick={onCancel}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <div className="modal__header">
          <h3 className="modal__title">{title ?? 'Xác nhận'}</h3>
          <button className="modal__close" onClick={onCancel}>✕</button>
        </div>
        <div className="modal__body">
          <p>{message ?? 'Bạn có chắc chắn muốn thực hiện hành động này?'}</p>
        </div>
        <div className="modal__footer">
          <button className="btn btn--ghost" onClick={onCancel}>Hủy</button>
          <button
            className={`btn ${danger ? 'btn--danger' : 'btn--primary'}`}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ConfirmModal;