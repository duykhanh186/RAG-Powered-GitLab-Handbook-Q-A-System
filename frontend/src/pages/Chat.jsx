import React, { useState, useEffect, useRef } from 'react';
import { chatAPI } from '../services/api';

function Chat() {
  // Danh sách tin nhắn, mỗi tin có dạng: { role: 'user'|'bot', content: '...', sources: [] }
  const [messages, setMessages] = useState([]);

  // Nguồn tham khảo đang được chọn để xem chi tiết
  const [selectedSource, setSelectedSource] = useState(null);

  // Nội dung người dùng đang gõ
  const [input, setInput] = useState('');

  // Đang chờ phản hồi từ backend hay không
  const [loading, setLoading] = useState(false);

  // Dùng để tự động cuộn xuống tin nhắn mới nhất
  const bottomRef = useRef(null);

  // Mỗi khi messages thay đổi, cuộn xuống cuối
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Hàm gửi tin nhắn
  const handleSend = async () => {
    // Không gửi nếu input trống hoặc đang loading
    if (!input.trim() || loading) return;

    // Thêm tin nhắn của user vào danh sách
    const userMessage = { role: 'user', content: input };
    setMessages(prev => [...prev, userMessage]);

    // Xóa input và bắt đầu loading
    setInput('');
    setLoading(true);

    try {
      // Gọi API backend
      const response = await chatAPI.sendMessage(input);

      // Lấy answer và sources từ response
      // Thử cả .answer và .message phòng backend đặt tên khác
      const answer = response.data?.answer || 'Không có phản hồi từ server';
      const sources = response.data?.sources || [];
      const sessionId = response.data?.session_id;
      console.log('Session ID:', sessionId); // để debug

      // Thêm tin nhắn bot vào danh sách
      const botMessage = { role: 'bot', content: answer, sources };
      setMessages(prev => [...prev, botMessage]);

    } catch (error) {
      // Nếu lỗi thì hiện thông báo lỗi thay vì crash app
      const errorMessage = {
        role: 'bot',
        content: 'Lỗi kết nối backend. Vui lòng kiểm tra lại server.',
        sources: []
      };
      setMessages(prev => [...prev, errorMessage]);
    } finally {
      // Dù thành công hay lỗi đều tắt loading
      setLoading(false);
    }
  };

  // Bấm Enter để gửi, Shift+Enter để xuống dòng
  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // Khi bấm vào câu hỏi gợi ý thì điền vào input
  const handleSuggestion = (question) => {
    setInput(question);
  };

  return (
    <div className="chat-container">

      {/* ===== HEADER ===== */}
      <div className="chat-header">
        <h2>Hỏi đáp về GitLab Handbook</h2>
        <p>Đặt câu hỏi về nội dung Handbook GitLab</p>
      </div>

      {/* ===== KHU VỰC TIN NHẮN ===== */}
      <div className="chat-messages">

        {/* Hiện gợi ý khi chưa có tin nhắn nào */}
        {messages.length === 0 && (
          <div className="chat-empty">
            <h1>SKIBIDI CHAT</h1>
            <p>Xin chào! Hãy đặt câu hỏi về GitLab Handbook</p>

            {/* Các câu hỏi gợi ý */}
            <div className="suggestions">
              {[
                'GitLab values la gi?',
                'Quy trinh onboarding?',
                'Remote work policy?'
              ].map(question => (
                <button
                  key={question}
                  className="suggestion-btn"
                  onClick={() => handleSuggestion(question)}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Render từng tin nhắn */}
        {messages.map((message, index) => (
          <div key={index} className={`message ${message.role}`}>

            {/* Avatar user hoặc bot */}
            <div className="message-avatar">
              {message.role === 'user' ? '👤' : '🦊'}
            </div>

            <div className="message-body">
              {/* Nội dung tin nhắn */}
              <div className="message-content">
                {message.content}
              </div>

              {/* Hiện sources nếu có */}
              {message.sources && message.sources.length > 0 && (
                <div className="message-sources">
                  <span>Nguồn tham khảo:</span>
                  <div className="source-chips-container">
                    {message.sources.map((source, i) => {
                      const text = typeof source === 'object'
                        ? (source.source ? source.source.split('/').pop() : 'Nguồn ' + (i+1))
                        : source;
                      return (
                        <button
                          key={i}
                          onClick={() => setSelectedSource(source)}
                          className="source-link-btn"
                          title="Click để xem chi tiết nguồn tham khảo này"
                        >
                          📄 {text}
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

          </div>
        ))}

        {/* Hiện loading khi đang chờ bot trả lời */}
        {loading && (
          <div className="message bot">
            <div className="message-avatar">
              🦊
            </div>
            <div className="message-body">
              {/* 3 chấm nhảy */}
              <div className="typing-indicator">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}

        {/* Điểm neo để cuộn xuống cuối */}
        <div ref={bottomRef} />

      </div>

      {/* ===== KHU VỰC NHẬP TIN NHẮN ===== */}
      <div className="chat-input-area">

        <textarea
          className="chat-input"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Nhập câu hỏi... (Enter để gửi, Shift+Enter xuống dòng)"
          rows={1}
          disabled={loading}
        />

        <button
          className="send-btn"
          onClick={handleSend}
          // Disable khi đang loading hoặc input trống
          disabled={loading || !input.trim()}
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="22" y1="2" x2="11" y2="13"></line>
            <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
          </svg>
        </button>

      </div>

      {/* ===== MODAL CHI TIẾT NGUỒN ===== */}
      {selectedSource && (
        <div className="modal-overlay" onClick={() => setSelectedSource(null)}>
          <div className="modal-content" onClick={e => e.stopPropagation()}>
            <div className="modal-header">
              <h3>
                <span>📄</span> Chi tiết nguồn tham khảo
              </h3>
              <button className="close-modal-btn" onClick={() => setSelectedSource(null)}>
                ✕
              </button>
            </div>
            <div className="modal-body">
              <div className="source-path-box">
                <strong>Tệp tin:</strong> {typeof selectedSource === 'object' ? selectedSource.source : selectedSource}
              </div>
              <div className="source-text-container">
                {typeof selectedSource === 'object' ? selectedSource.content : "Không tìm thấy nội dung chi tiết cho nguồn này."}
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

export default Chat;