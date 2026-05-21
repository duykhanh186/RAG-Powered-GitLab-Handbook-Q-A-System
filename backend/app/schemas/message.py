# Message schema
# HIEP viet lai Message schema (Đã cấu hình tự động format giờ VN)
from pydantic import BaseModel, field_serializer
from datetime import datetime, timezone, timedelta
from typing import Optional

# Cấu hình cứng múi giờ Việt Nam
VIETNAM_TZ = timezone(timedelta(hours=7))

class MessageBase(BaseModel):
    question: str
    answer: str
    sources: Optional[str] = None


class MessageCreate(MessageBase):
    session_id: Optional[str] = None
    user_id: Optional[int] = None


class MessageResponse(MessageBase):
    id: int
    session_id: Optional[str] = None
    user_id: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True  # Cho phép đọc từ SQLAlchemy model

    # 🔹 Thêm serializer này để ép Pydantic luôn trả ra chuỗi ISO có chứa múi giờ +07:00 ở API response
    @field_serializer('created_at')
    def serialize_datetime(self, dt: datetime) -> str:
        if dt is None:
            return None
        # Nếu datetime chưa có thông tin múi giờ (naive), ép nó hiểu là UTC rồi convert sang VN
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(VIETNAM_TZ).isoformat()