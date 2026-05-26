import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';

import Chat from './pages/Chat';
import AdminLayout from './components/admin/AdminLayout';
import AdminDashboard from './pages/AdminDashboard';
import AdminDocuments from './pages/AdminDocuments';
import AdminUsers from './pages/AdminUsers';
import AdminSettings from './pages/AdminSettings';

import './App.css';

// ─── Constants ────────────────────────────────────────────────
const LS_CONVERSATIONS = 'conversations';
const LS_CURRENT_ID = 'currentConversationId';

// ─── Helpers ──────────────────────────────────────────────────
const genId = () =>
  `conv_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;

const formatTime = (isoString) => {
  const d = new Date(isoString);
  const now = new Date();

  const diffMs = now - d;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Vừa xong';
  if (diffMins < 60) return `${diffMins} phút trước`;
  if (diffHours < 24) return `${diffHours} giờ trước`;
  if (diffDays === 1) return 'Hôm qua';
  if (diffDays < 7) return `${diffDays} ngày trước`;

  return d.toLocaleDateString('vi-VN');
};

const truncate = (str, max = 36) =>
  str && str.length > max
    ? str.slice(0, max).trimEnd() + '…'
    : str;

// ─── localStorage helpers ─────────────────────────────────────
const saveToLS = (conversations, currentId) => {
  try {
    localStorage.setItem(LS_CONVERSATIONS, JSON.stringify(conversations));
    localStorage.setItem(LS_CURRENT_ID, currentId ?? '');
  } catch (_) {}
};

const loadFromLS = () => {
  try {
    const convs = JSON.parse(localStorage.getItem(LS_CONVERSATIONS) || '[]');
    const currentId = localStorage.getItem(LS_CURRENT_ID) || null;
    return {
      convs: Array.isArray(convs) ? convs : [],
      currentId,
    };
  } catch (_) {
    return { convs: [], currentId: null };
  }
};

// ─── App ──────────────────────────────────────────────────────
function App() {
  const [darkMode, setDarkMode] = useState(true);
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [editingId, setEditingId] = useState(null);
  const [editingTitle, setEditingTitle] = useState('');
  const [confirmDeleteId, setConfirmDeleteId] = useState(null);

  // ── Boot: load localStorage ────────────────────────────────
  useEffect(() => {
    const { convs, currentId } = loadFromLS();
    if (convs.length > 0) {
      setConversations(convs);
      const valid = convs.find((c) => c.id === currentId);
      setCurrentId(valid ? currentId : convs[0].id);
    }
  }, []);

  // ── Messages hiện tại ──────────────────────────────────────
  const currentMessages = conversations.find((c) => c.id === currentConversationId)?.messages ?? [];

  // ── Tạo chat mới ───────────────────────────────────────────
  const createNewChat = useCallback(() => {
    const newConv = {
      id: genId(),
      title: 'Đoạn chat mới',
      createdAt: new Date().toISOString(),
      messages: [],
    };
    setConversations((prev) => {
      const updated = [newConv, ...prev];
      saveToLS(updated, newConv.id);
      return updated;
    });
    setCurrentId(newConv.id);
  }, []);

  // ── Load conversation ──────────────────────────────────────
  const loadConversation = useCallback((id) => {
    setCurrentId(id);
    setEditingId(null);
    setConfirmDeleteId(null);
    setConversations((prev) => {
      saveToLS(prev, id);
      return prev;
    });
  }, []);

  // ── Update messages ────────────────────────────────────────
  const updateConversationMessages = useCallback((convId, newMessages) => {
    setConversations((prev) => {
      const updated = prev.map((c) => {
        if (c.id !== convId) return c;
        const firstUserMsg = newMessages.find((m) => m.role === 'user');
        const autoTitle = c.title === 'Đoạn chat mới' && firstUserMsg
            ? truncate(firstUserMsg.content, 40)
            : c.title;
        return { ...c, title: autoTitle, messages: newMessages };
      });
      saveToLS(updated, convId);
      return updated;
    });
  }, []);

  // ── Xóa conversation ───────────────────────────────────────
  const deleteConversation = useCallback((id) => {
    setConversations((prev) => {
      const updated = prev.filter((c) => c.id !== id);
      const nextId = updated.length > 0 ? updated[0].id : null;
      saveToLS(updated, nextId);
      setCurrentId(nextId);
      return updated;
    });
    setConfirmDeleteId(null);
  }, []);

  // ── Đổi tên conversation ───────────────────────────────────
  const renameConversation = useCallback((id, newTitle) => {
    if (!newTitle.trim()) return;
    setConversations((prev) => {
      const updated = prev.map((c) => c.id === id ? { ...c, title: newTitle.trim() } : c);
      saveToLS(updated, currentConversationId);
      return updated;
    });
    setEditingId(null);
  }, [currentConversationId]);

  // ── Filter sidebar ─────────────────────────────────────────
  const filteredConvs = conversations.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  // ─── Render ────────────────────────────────────────────────
  return (
    <Router>
      <div className={darkMode ? 'app dark' : 'app light'}>
        <Routes>
          
          {/* =========================================
              CỔNG 1: DÀNH RIÊNG CHO ADMIN (TÁCH BIỆT)
          ========================================== */}
          <Route path="/admin" element={<AdminLayout />}>
            <Route index element={<Navigate to="dashboard" replace />} />
            <Route path="dashboard" element={<AdminDashboard />} />
            <Route path="documents" element={<AdminDocuments />} />
            <Route path="users" element={<AdminUsers />} />
            <Route path="settings" element={<AdminSettings />} />
          </Route>

          {/* =========================================
              CỔNG 2: CHAT DÀNH CHO USER THƯỜNG
          ========================================== */}
          <Route path="/" element={
            <div className="content-wrapper">
              
              {/* === CHAT SIDEBAR === */}
              <aside className="sidebar">
                <button className="new-chat-btn" onClick={createNewChat}>
                  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="5" x2="12" y2="19" />
                    <line x1="5" y1="12" x2="19" y2="12" />
                  </svg>
                  Đoạn chat mới
                </button>

                <div className="search-box">
                  <span className="search-icon">🔍</span>
                  <input type="text" placeholder="Tìm kiếm đoạn chat" className="search-input" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} />
                  {searchQuery && (
                    <button className="search-clear" onClick={() => setSearchQuery('')}>×</button>
                  )}
                </div>

                <div className="history-list">
                  {filteredConvs.length === 0 ? (
                    <div className="history-empty">
                      {searchQuery ? `Không tìm thấy "${searchQuery}"` : 'Chưa có hội thoại nào'}
                    </div>
                  ) : (
                    filteredConvs.map((conv) => (
                      <div key={conv.id} className={`history-item ${conv.id === currentConversationId ? 'active' : ''}`} onClick={() => loadConversation(conv.id)}>
                        {editingId === conv.id ? (
                          <input
                            className="rename-input"
                            value={editingTitle}
                            autoFocus
                            onChange={(e) => setEditingTitle(e.target.value)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') renameConversation(conv.id, editingTitle);
                              if (e.key === 'Escape') setEditingId(null);
                            }}
                            onBlur={() => renameConversation(conv.id, editingTitle)}
                            onClick={(e) => e.stopPropagation()}
                          />
                        ) : (
                          <>
                            <div className="history-item-body">
                              <span className="history-title">{conv.title}</span>
                              <span className="history-time">{formatTime(conv.createdAt)}</span>
                            </div>
                            <div className="history-actions" onClick={(e) => e.stopPropagation()}>
                              <button className="action-btn" title="Đổi tên" onClick={() => { setEditingId(conv.id); setEditingTitle(conv.title); }}>✎</button>
                              {confirmDeleteId === conv.id ? (
                                <div className="delete-confirm">
                                  <button className="action-btn danger" title="Xác nhận xóa" onClick={() => deleteConversation(conv.id)}>✓</button>
                                  <button className="action-btn" title="Hủy" onClick={() => setConfirmDeleteId(null)}>✕</button>
                                </div>
                              ) : (
                                <button className="action-btn" title="Xóa" onClick={() => setConfirmDeleteId(conv.id)}>🗑</button>
                              )}
                            </div>
                          </>
                        )}
                      </div>
                    ))
                  )}
                </div>

                <div className="theme-toggle" onClick={() => setDarkMode(!darkMode)}>
                  <span>{darkMode ? '☀️' : '🌙'}</span>
                  <span>{darkMode ? 'Chế độ sáng' : 'Chế độ tối'}</span>
                </div>
              </aside>

              {/* === MAIN CHAT AREA === */}
              <main className="main-content">
                <Chat
                  key={currentConversationId}
                  conversationId={currentConversationId}
                  initialMessages={currentMessages}
                  onMessagesUpdate={updateConversationMessages}
                  onCreateNewChat={createNewChat}
                />
              </main>
            </div>
          } />

          {/* Xử lý các link không tồn tại */}
          <Route path="*" element={<Navigate to="/" replace />} />

        </Routes>
      </div>
    </Router>
  );
}

export default App;