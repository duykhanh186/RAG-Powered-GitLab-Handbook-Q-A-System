# History endpoint
# HIEP viet lai History API
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from app.core.database import get_db          # ← dùng Depends, KHÔNG dùng SessionLocal trực tiếp
from app.schemas.message import MessageResponse
from app.services.history_service import HistoryService

router = APIRouter(prefix="/api/history", tags=["history"])


#  Lấy danh sách các đoạn chat để hiển thị lên thanh Sidebar bên trái
# Endpoint thực tế sẽ là: GET /api/history/sessions
@router.get("/sessions")
def get_history_sessions(
    limit: int = 20,
    offset: int = 0,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    service = HistoryService()
    # Gọi hàm xử lý gom nhóm session và sắp xếp mới nhất lên đầu từ service
    return service.get_unique_sessions(db, user_id=user_id, limit=limit, offset=offset)


#  Được nâng cấp để lấy chi tiết tin nhắn theo từng session cụ thể
@router.get("/", response_model=List[MessageResponse])
def get_history(
    session_id: Optional[str] = Query(None, description="Id của đoạn chat cần lấy chi tiết tin nhắn"),
    user_id: Optional[int] = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),            # ← FastAPI tự inject db session
):
    service = HistoryService()
    # Truyền thêm session_id và user_id vào service để filter chuẩn xác
    return service.get_history(db, session_id=session_id, user_id=user_id, limit=limit, offset=offset)


#  Được nâng cấp để có thể xóa toàn bộ hoặc xóa riêng lẻ từng session chat
@router.delete("/")
def delete_history(
    session_id: Optional[str] = Query(None, description="Id của đoạn chat muốn xóa. Để trống nếu muốn xóa hết"),
    user_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    service = HistoryService()
    # Truyền tham số vào để delete_history ở service xử lý xóa thông minh
    success = service.delete_history(db, session_id=session_id, user_id=user_id)
    return {"success": success, "message": "Đã xóa lịch sử thành công" if success else "Xóa thất bại"}