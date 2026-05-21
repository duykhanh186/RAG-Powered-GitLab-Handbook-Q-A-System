# History service
# HIEP viet lai History service logic
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.models.message import Message
from app.schemas.message import MessageResponse


class HistoryService:
    # Lấy danh sách các đoạn chat (Session) để hiển thị lên thanh Sidebar bên trái
    def get_unique_sessions(
        self,
        db: Session,
        user_id: Optional[int] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[dict]:
        """
        Hàm này gom nhóm tin nhắn theo session_id, lấy câu chat đầu tiên làm tiêu đề 
         và sắp xếp cuộc trò chuyện mới nhất lên trên cùng.
        """
        # Tạo subquery để tìm thời gian chat mới nhất của mỗi session
        subquery = (
            db.query(
                Message.session_id,
                func.max(Message.created_at).label("last_active"),
                # Lấy tạm câu hỏi đầu tiên của session làm tiêu đề hiển thị ở Sidebar
                func.min(Message.question).label("title") 
            )
            .filter(Message.session_id.isnot(None))
        )
        
        if user_id:
            subquery = subquery.filter(Message.user_id == user_id)
            
        subquery = subquery.group_by(Message.session_id).subquery()

        # Truy vấn chính: Sắp xếp các session theo thứ tự mới nhất lên đầu (desc)
        sessions = (
            db.query(subquery)
            .order_by(subquery.c.last_active.desc()) 
            .offset(offset)
            .limit(limit)
            .all()
        )

        # Trả về danh sách dạng dict để frontend dễ map [{session_id, title, last_active}, ...]
        return [
            {
                "session_id": s.session_id,
                "title": s.title if s.title else "Đoạn chat mới",
                "last_active": s.last_active.isoformat() if s.last_active else None
            }
            for s in sessions
        ]

    # 🔹 HÀM CŨ: Giữ nguyên để lấy chi tiết tin nhắn khi bấm vào một đoạn chat cụ thể
    def get_history(
        self,
        db: Session,
        session_id: Optional[str] = None,   
        user_id: Optional[int] = None,      
        limit: int = 20,
        offset: int = 0,
    ) -> List[MessageResponse]:
        query = db.query(Message)

        if session_id:
            query = query.filter(Message.session_id == session_id)

        if user_id:
            query = query.filter(Message.user_id == user_id)

        messages = (
            query
            .order_by(Message.created_at.asc())  # Giữ asc để khi bấm vào chat, tin nhắn hiện từ cũ đến mới (chuẩn dòng thời gian)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [MessageResponse.from_orm(m) for m in messages]

    # 🔹 HÀM CŨ: Giữ nguyên để xóa lịch sử
    def delete_history(
        self,
        db: Session,
        session_id: Optional[str] = None,   
        user_id: Optional[int] = None,
    ) -> bool:
        try:
            query = db.query(Message)

            if session_id:
                query = query.filter(Message.session_id == session_id)
            if user_id:
                query = query.filter(Message.user_id == user_id)

            query.delete()
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False