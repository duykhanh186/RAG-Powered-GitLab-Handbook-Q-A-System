import React, { useState, useEffect, useCallback } from 'react';
import { BrowserRouter as Router, Routes, Route, NavLink } from 'react-router-dom';
import Chat from './pages/Chat';
import Dashboard from './pages/Dashboard';
import './App.css';
 
// ─── Constants ────────────────────────────────────────────────
const LS_CONVERSATIONS = 'conversations';
const LS_CURRENT_ID    = 'currentConversationId';
 
// ─── Helpers ──────────────────────────────────────────────────
const genId = () => `conv_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`;
 
const formatTime = (isoString) => {
  const d = new Date(isoString);
  const now = new Date();
  const diffMs = now - d;
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);
 
  if (diffMins < 1)    return 'Vừa xong';
  if (diffMins < 60)   return `${diffMins} phút trước`;
  if (diffHours < 24)  return `${diffHours} giờ trước`;
  if (diffDays === 1)  return 'Hôm qua';
  if (diffDays < 7)    return `${diffDays} ngày trước`;
  return d.toLocaleDateString('vi-VN');
};
 
const truncate = (str, max = 36) =>
  str && str.length > max ? str.slice(0, max).trimEnd() + '…' : str;
 
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
    return { convs: Array.isArray(convs) ? convs : [], currentId };
  } catch (_) {
    return { convs: [], currentId: null };
  }
};
 
// ─── App ──────────────────────────────────────────────────────
function App() {
  const [darkMode, setDarkMode]                   = useState(true);
  const [conversations, setConversations]         = useState([]);
  const [currentConversationId, setCurrentId]     = useState(null);
  const [searchQuery, setSearchQuery]             = useState('');
  const [editingId, setEditingId]                 = useState(null);
  const [editingTitle, setEditingTitle]           = useState('');
  const [confirmDeleteId, setConfirmDeleteId]     = useState(null);
 
  // ── Boot: load từ localStorage ──────────────────────────────
  useEffect(() => {
    const { convs, currentId } = loadFromLS();
    if (convs.length > 0) {
      setConversations(convs);
      // Nếu currentId hợp lệ thì load lại, không thì lấy conv mới nhất
      const valid = convs.find(c => c.id === currentId);
      setCurrentId(valid ? currentId : convs[0].id);
    }
  }, []);
 
  // ── Lấy messages của conversation hiện tại ──────────────────
  const currentMessages = conversations.find(c => c.id === currentConversationId)?.messages ?? [];
 
  // ── createNewChat ────────────────────────────────────────────
  const createNewChat = useCallback(() => {
    const newConv = {
      id:        genId(),
      title:     'Đoạn chat mới',
      createdAt: new Date().toISOString(),
      messages:  [],
    };
    setConversations(prev => {
      const updated = [newConv, ...prev];
      saveToLS(updated, newConv.id);
      return updated;
    });
    setCurrentId(newConv.id);
  }, []);
 
  // ── loadConversation ─────────────────────────────────────────
  const loadConversation = useCallback((id) => {
    setCurrentId(id);
    setEditingId(null);
    setConfirmDeleteId(null);
    setConversations(prev => {
      saveToLS(prev, id);
      return prev;
    });
  }, []);
 
  // ── updateConversationMessages ───────────────────────────────
  // Được gọi từ Chat.jsx mỗi khi có tin nhắn mới
  const updateConversationMessages = useCallback((convId, newMessages) => {
    setConversations(prev => {
      const updated = prev.map(c => {
        if (c.id !== convId) return c;
        // Tự động đặt title từ tin nhắn đầu tiên của user
        const firstUserMsg = newMessages.find(m => m.role === 'user');
        const autoTitle =
          c.title === 'Đoạn chat mới' && firstUserMsg
            ? truncate(firstUserMsg.content, 40)
            : c.title;
        return { ...c, title: autoTitle, messages: newMessages };
      });
      saveToLS(updated, convId);
      return updated;
    });
  }, []);
 
  // ── deleteConversation ───────────────────────────────────────
  const deleteConversation = useCallback((id) => {
    setConversations(prev => {
      const updated = prev.filter(c => c.id !== id);
      const nextId  = updated.length > 0 ? updated[0].id : null;
      saveToLS(updated, nextId);
      setCurrentId(nextId);
      return updated;
    });
    setConfirmDeleteId(null);
  }, []);
 
  // ── renameConversation ───────────────────────────────────────
  const renameConversation = useCallback((id, newTitle) => {
    if (!newTitle.trim()) return;
    setConversations(prev => {
      const updated = prev.map(c =>
        c.id === id ? { ...c, title: newTitle.trim() } : c
      );
      saveToLS(updated, currentConversationId);
      return updated;
    });
    setEditingId(null);
  }, [currentConversationId]);
 
  // ── Filter sidebar theo search ───────────────────────────────
  const filteredConvs = conversations.filter(c =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  );
 
  // ─── Render ─────────────────────────────────────────────────
  return (
    <Router>
      <div className={darkMode ? 'app dark' : 'app light'}>
 
        {/* NAVBAR */}
        <nav className="navbar">
          <div className="navbar-brand">
            <span className="brand-icon">🦊</span>
            <span className="brand-name">GitLab Handbook QA</span>
          </div>
          <div className="navbar-links">
            <NavLink to="/" end className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Chat
            </NavLink>
            <NavLink to="/dashboard" className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>
              Dashboard
            </NavLink>
          </div>
        </nav>
 
        <div className="content-wrapper">
 
          {/* ===== SIDEBAR ===== */}
          <aside className="sidebar">
 
            {/* Nút tạo đoạn chat mới */}
            <button className="new-chat-btn" onClick={createNewChat}>
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>
              </svg>
              Đoạn chat mới
            </button>
 
            {/* Thanh tìm kiếm */}
            <div className="search-box">
              <span className="search-icon">🔍</span>
              <input
                type="text"
                placeholder="Tìm kiếm đoạn chat"
                className="search-input"
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
              />
              {searchQuery && (
                <button className="search-clear" onClick={() => setSearchQuery('')}>×</button>
              )}
            </div>
 
            {/* ── DANH SÁCH LỊCH SỬ ── */}
            <div className="history-list">
              {filteredConvs.length === 0 ? (
                <div className="history-empty">
                  {searchQuery
                    ? `Không tìm thấy "${searchQuery}"`
                    : 'Chưa có hội thoại nào'}
                </div>
              ) : (
                filteredConvs.map(conv => (
                  <div
                    key={conv.id}
                    className={`history-item ${conv.id === currentConversationId ? 'active' : ''}`}
                    onClick={() => loadConversation(conv.id)}
                  >
                    {/* Đang đổi tên */}
                    {editingId === conv.id ? (
                      <input
                        className="rename-input"
                        value={editingTitle}
                        autoFocus
                        onChange={e => setEditingTitle(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') renameConversation(conv.id, editingTitle);
                          if (e.key === 'Escape') setEditingId(null);
                        }}
                        onBlur={() => renameConversation(conv.id, editingTitle)}
                        onClick={e => e.stopPropagation()}
                      />
                    ) : (
                      <>
                        {/* Nội dung item */}
                        <div className="history-item-body">
                          <span className="history-title">{conv.title}</span>
                          <span className="history-time">{formatTime(conv.createdAt)}</span>
                        </div>
 
                        {/* Action buttons — hiện khi hover */}
                        <div
                          className="history-actions"
                          onClick={e => e.stopPropagation()}
                        >
                          {/* Đổi tên */}
                          <button
                            className="action-btn"
                            title="Đổi tên"
                            onClick={() => {
                              setEditingId(conv.id);
                              setEditingTitle(conv.title);
                            }}
                          >
                            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
                              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
                            </svg>
                          </button>
 
                          {/* Xóa / confirm xóa */}
                          {confirmDeleteId === conv.id ? (
                            <div className="delete-confirm">
                              <button
                                className="action-btn danger"
                                title="Xác nhận xóa"
                                onClick={() => deleteConversation(conv.id)}
                              >✓</button>
                              <button
                                className="action-btn"
                                title="Hủy"
                                onClick={() => setConfirmDeleteId(null)}
                              >✕</button>
                            </div>
                          ) : (
                            <button
                              className="action-btn"
                              title="Xóa"
                              onClick={() => setConfirmDeleteId(conv.id)}
                            >
                              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <polyline points="3 6 5 6 21 6"/>
                                <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
                                <path d="M10 11v6M14 11v6"/>
                                <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
                              </svg>
                            </button>
                          )}
                        </div>
                      </>
                    )}
                  </div>
                ))
              )}
            </div>
 
            {/* Theme toggle — đẩy xuống cuối */}
            <div className="theme-toggle" onClick={() => setDarkMode(!darkMode)}>
              <span>{darkMode ? '☀️' : '🌙'}</span>
              <span>{darkMode ? 'Chế độ sáng' : 'Chế độ tối'}</span>
            </div>
 
          </aside>
 
          {/* ===== NỘI DUNG CHÍNH ===== */}
          <main className="main-content">
            <Routes>
              <Route
                path="/"
                element={
                  <Chat
                    key={currentConversationId}          // re-mount khi đổi conv
                    conversationId={currentConversationId}
                    initialMessages={currentMessages}
                    onMessagesUpdate={updateConversationMessages}
                    onCreateNewChat={createNewChat}
                  />
                }
              />
              <Route path="/dashboard" element={<Dashboard />} />
            </Routes>
          </main>
 
        </div>
      </div>
    </Router>
  );
}
 
export default App;