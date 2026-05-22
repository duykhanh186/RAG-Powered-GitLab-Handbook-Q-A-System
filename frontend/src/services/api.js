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
  sendMessage: (message, sessionId) => apiClient.post('/chat/', { question: message, session_id: sessionId }),
  getHistory: () => apiClient.get('/chat/history'),
};

// ===== HISTORY API =====
export const historyAPI = {
  getHistory: () => apiClient.get('/history/'),
  deleteHistory: () => apiClient.delete('/history/'),
};

// ===== INGEST API =====
export const ingestAPI = {
  // Giữ lại đường dẫn /ingest/ gốc cho các file dự phòng nếu có
  uploadDocument: (file) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/ingest/', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  getStatus: () => apiClient.get('/ingest/status'),
};

// ===== ADMIN API =====
export const adminAPI = {
  // 1. Dashboard
  getDashboard:   () => apiClient.get('/admin/dashboard'),

  // 2. Documents
  getDocuments:   () => apiClient.get('/admin/documents'),
  
  
  uploadDocument: (file, onProgress) => {
    const formData = new FormData();
    formData.append('file', file);
    return apiClient.post('/admin/documents', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (e) => {
        if (onProgress) {
          const pct = Math.round((e.loaded * 100) / e.total);
          onProgress(pct);
        }
      },
    });
  },

  deleteDocument:  (id) => apiClient.delete(`/admin/documents/${id}`),
  reindexDocument: (id) => apiClient.post(`/admin/reindex/${id}`),

  // 3. Users
  getUsers:       ()         => apiClient.get('/admin/users'),
  createUser:     (data)     => apiClient.post('/admin/users', data),
  deleteUser:     (id)       => apiClient.delete(`/admin/users/${id}`),
  updateUserRole: (id, role) => apiClient.patch(`/admin/users/${id}`, { role }),

  // 4. Settings
  getSettings:    ()     => apiClient.get('/admin/settings'),
  updateSettings: (data) => apiClient.put('/admin/settings', data),
};