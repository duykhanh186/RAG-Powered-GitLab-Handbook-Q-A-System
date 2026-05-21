import axios from 'axios';

// Lấy URL backend từ .env, mặc định dùng cùng origin (qua nginx proxy)
const API_URL = process.env.REACT_APP_API_URL || '';

export const apiClient = axios.create({
  baseURL: `${API_URL}/api`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// ===== CHAT API =====
export const chatAPI = {
  // Gửi tin nhắn → POST /api/chat/
  // Body: { message: "..." }
 sendMessage: (message) => apiClient.post('/chat/', { question: message }),

  // Lấy lịch sử chat → GET /api/chat/history
  getHistory: () => apiClient.get('/chat/history'),
};

// ===== HISTORY API =====
export const historyAPI = {
  // Lấy toàn bộ lịch sử → GET /api/history/
  getHistory: () => apiClient.get('/history/'),

  // Xóa toàn bộ lịch sử → DELETE /api/history/
  deleteHistory: () => apiClient.delete('/history/'),
};

// ===== INGEST API =====
export const ingestAPI = {
  // Upload tài liệu → POST /api/ingest/
  uploadDocument: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/ingest/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },

  // Lấy trạng thái hệ thống → GET /api/ingest/status
  getStatus: () => apiClient.get('/ingest/status'),
};