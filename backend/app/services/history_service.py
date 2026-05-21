# History service
# HIEP viet lai History service logic (Đã chuyển đổi múi giờ sang GMT+7 và sắp xếp tin nhắn mới lên đầu)
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import timezone, timedelta  # 🔹 Thêm thư viện này để xử lý múi giờ
from app.models.message import Message
from app.schemas.message import MessageResponse

# Định nghĩa múi giờ Việt Nam (GMT+7)
VIETNAM_TZ = timezone(timedelta(hours=7))

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
        result = []
        for s in sessions:
            last_active_vn = None
            if s.last_active:
                # Ép kiểu datetime từ DB hiểu là UTC rồi chuyển thành giờ VN (GMT+7)
                last_active_vn = s.last_active.replace(tzinfo=timezone.utc).astimezone(VIETNAM_TZ)
            
            result.append({
                "session_id": s.session_id,
                "title": s.title if s.title else "Đoạn chat mới",
                "last_active": last_active_vn.isoformat() if last_active_vn else None
            })
            
        return result

    # 🔹 HÀM ĐÃ SỬA: Lấy chi tiết tin nhắn và đưa tin nhắn mới nhất lên đầu
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
            .order_by(Message.created_at.desc())  # desc() ở đây để đưa tin nhắn mới lên đầu
            .offset(offset)
            .limit(limit)
            .all()
        )
        
        # Chuyển đổi trường created_at của từng object sang giờ VN trước khi đưa qua Pydantic
        for m in messages:
            if m.created_at:
                m.created_at = m.created_at.replace(tzinfo=timezone.utc).astimezone(VIETNAM_TZ)

        return [MessageResponse.from_orm(m) for m in messages]

    # Xóa lịch sử
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