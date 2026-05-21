import React, { useState, useEffect, useRef } from 'react';
import { chatAPI } from '../services/api';
 
function Chat({ conversationId, initialMessages = [], onMessagesUpdate, onCreateNewChat }) {
 
  const [messages, setMessages]   = useState(initialMessages);
  const [input, setInput]         = useState('');
  const [loading, setLoading]     = useState(false);
  const bottomRef                 = useRef(null);
  const textareaRef               = useRef(null);
 
  // ── Khi đổi conversation (key thay đổi) reset messages ──────
  useEffect(() => {
    setMessages(initialMessages);
    setInput('');
    setLoading(false);
  }, [conversationId]);
 
  // ── Auto scroll xuống cuối mỗi khi messages thay đổi ────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, loading]);
 
  // ── Auto resize textarea theo nội dung ──────────────────────
  useEffect(() => {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = Math.min(ta.scrollHeight, 160) + 'px';
  }, [input]);
 
  // ── Gửi tin nhắn ────────────────────────────────────────────
  const handleSend = async () => {
    if (!input.trim() || loading || !conversationId) return;
 
    const userMsg = {
      role:      'user',
      content:   input.trim(),
      timestamp: new Date().toISOString(),
    };
 
    const nextMessages = [...messages, userMsg];
    setMessages(nextMessages);
    setInput('');
    setLoading(true);
 
    // Lưu ngay sau khi user gửi (để title cũng cập nhật ngay)
    onMessagesUpdate?.(conversationId, nextMessages);
 
    try {
      const response = await chatAPI.sendMessage(userMsg.content);
      const answer   = response.data?.answer || 'Không có phản hồi từ server.';
      const sources  = response.data?.sources || [];
 
      const botMsg = {
        role:      'assistant',
        content:   answer,
        sources,
        timestamp: new Date().toISOString(),
      };
 
      const finalMessages = [...nextMessages, botMsg];
      setMessages(finalMessages);
      onMessagesUpdate?.(conversationId, finalMessages);
 
    } catch {
      const errMsg = {
        role:      'assistant',
        content:   'Lỗi kết nối backend. Vui lòng kiểm tra lại server.',
        sources:   [],
        timestamp: new Date().toISOString(),
      };
      const finalMessages = [...nextMessages, errMsg];
      setMessages(finalMessages);
      onMessagesUpdate?.(conversationId, finalMessages);
    } finally {
      setLoading(false);
    }
  };
 
  // ── Enter gửi, Shift+Enter xuống dòng ───────────────────────
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };
 
  // ── Click gợi ý ─────────────────────────────────────────────
  const handleSuggestion = (question) => {
    setInput(question);
    textareaRef.current?.focus();
  };
 
  // ── Chưa chọn conversation nào ──────────────────────────────
  if (!conversationId) {
    return (
      <div className="chat-container">
        <div className="chat-no-conv">
          <div className="no-conv-icon">💬</div>
          <h3>Chưa có cuộc hội thoại nào</h3>
          <p>Nhấn <strong>Đoạn chat mới</strong> để bắt đầu</p>
          <button className="no-conv-btn" onClick={onCreateNewChat}>
            ✏️ Bắt đầu chat
          </button>
        </div>
      </div>
    );
  }
 
  // ─── Render ─────────────────────────────────────────────────
  return (
    <div className="chat-container">
 
      {/* HEADER */}
      <div className="chat-header">
        <h2>Hỏi đáp về GitLab Handbook</h2>
        <p>Đặt câu hỏi về nội dung Handbook GitLab</p>
      </div>
 
      {/* KHU VỰC TIN NHẮN */}
      <div className="chat-messages">
 
        {/* Màn hình trống */}
        {messages.length === 0 && (
          <div className="chat-empty">
            <h1>SKIBIDI CHAT</h1>
            <p>Xin chào! Hãy đặt câu hỏi về GitLab Handbook</p>
            <div className="suggestions">
              {[
                'GitLab values là gì?',
                'Quy trình onboarding?',
                'Remote work policy?',
              ].map(q => (
                <button key={q} className="suggestion-btn" onClick={() => handleSuggestion(q)}>
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
 
        {/* Danh sách tin nhắn */}
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role === 'user' ? 'user' : 'bot'}`}>
 
            <div className="message-avatar">
              {msg.role === 'user' ? '👤' : '🦊'}
            </div>
 
            <div className="message-body">
              <div className="message-content">{msg.content}</div>
 
              {/* Timestamp */}
              {msg.timestamp && (
                <div className="message-timestamp">
                  {new Date(msg.timestamp).toLocaleTimeString('vi-VN', {
                    hour: '2-digit', minute: '2-digit'
                  })}
                </div>
              )}
 
              {/* Sources */}
              {msg.sources && msg.sources.length > 0 && (
                <div className="message-sources">
                  <span>Nguồn tham khảo:</span>
                  {msg.sources.map((source, j) => {
                    const url  = typeof source === 'object' ? source.source : source;
                    const text = typeof source === 'object'
                      ? (source.source ? source.source.split('/').pop() : `Nguồn ${j + 1}`)
                      : source;
                    return (
                      <a key={j} href={url} target="_blank" rel="noreferrer" className="source-link">
                        {text}
                      </a>
                    );
                  })}
                </div>
              )}
            </div>
 
          </div>
        ))}
 
        {/* Typing indicator */}
        {loading && (
          <div className="message bot">
            <div className="message-avatar">🦊</div>
            <div className="message-body">
              <div className="typing-indicator">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}
 
        <div ref={bottomRef} />
      </div>
 
      {/* KHU VỰC NHẬP */}
      <div className="chat-input-area">
        <textarea
          ref={textareaRef}
          className="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Nhập câu hỏi… (Enter gửi, Shift+Enter xuống dòng)"
          rows={1}
          disabled={loading}
        />
        <button
          className="send-btn"
          onClick={handleSend}
          disabled={loading || !input.trim()}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"/>
            <polygon points="22 2 15 22 11 13 2 9 22 2"/>
          </svg>
        </button>
      </div>
 
    </div>
  );
}
 
export default Chat;