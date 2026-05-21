import React, { useState, useEffect } from 'react';
import { ingestAPI } from '../services/api';

function Dashboard() {
  // Trạng thái hệ thống lấy từ backend (số tài liệu, số vectors...)
  const [status, setStatus] = useState(null);

  // Đang tải trạng thái hệ thống hay không
  const [statusLoading, setStatusLoading] = useState(true);

  // Lỗi khi lấy trạng thái
  const [statusError, setStatusError] = useState('');

  // Khi component load lần đầu, lấy trạng thái hệ thống từ backend
  useEffect(() => {
    fetchStatus();
  }, []);

  // Hàm gọi API lấy trạng thái hệ thống
  const fetchStatus = async () => {
    setStatusLoading(true);
    setStatusError('');
    try {
      const response = await ingestAPI.getStatus();
      setStatus(response.data);
    } catch (error) {
      setStatusError('Khong the ket noi backend. Kiem tra lai server.');
    } finally {
      setStatusLoading(false);
    }
  };

  return (
    <div className="dashboard-container">

      {/* ===== HEADER ===== */}
      <div className="dashboard-header">
        <h2>Dashboard</h2>
        <p>Theo dõi trạng thái hệ thống</p>
      </div>

      <div className="dashboard-grid">

        {/* ===== CARD: TRẠNG THÁI HỆ THỐNG ===== */}
        <div className="card">
          <div className="card-title-row">
            <h3>Trạng Thái Hệ Thống</h3>

            {/* Nút refresh để lấy lại trạng thái mới nhất */}
            <button
              className="refresh-btn"
              onClick={fetchStatus}
              disabled={statusLoading}
            >
              {statusLoading ? 'Đang tải...' : 'Làm mới'}
            </button>
          </div>

          {/* Đang tải */}
          {statusLoading && (
            <p className="status-loading">Đang tải trạng thái...</p>
          )}

          {/* Lỗi khi tải */}
          {statusError && !statusLoading && (
            <p className="status-error">{statusError}</p>
          )}

          {/* Hiện thông tin trạng thái khi tải xong */}
          {status && !statusLoading && (
            <div className="status-info">

              {/* Số tài liệu đã ingest */}
              <div className="status-row">
                <span className="status-label">Tài liệu:</span>
                <span className="status-value">
                  {status.total_documents ?? status.document_count ?? 'N/A'}
                </span>
              </div>

              {/* Số vectors trong Qdrant */}
              <div className="status-row">
                <span className="status-label">Vectors:</span>
                <span className="status-value">
                  {status.total_vectors ?? status.vector_count ?? 'N/A'}
                </span>
              </div>

              {/* Trạng thái hoạt động */}
              <div className="status-row">
                <span className="status-label">Trạng thái:</span>
                <span className={`status-value ${status.status === 'active' ? 'active' : ''}`}>
                  {status.status ?? 'N/A'}
                </span>
              </div>

            </div>
          )}
        </div>

      </div>
    </div>
  );
}

export default Dashboard;