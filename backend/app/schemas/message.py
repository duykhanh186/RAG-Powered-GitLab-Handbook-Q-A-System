# Message schema
# HIEP viet lai Message schema
from pydantic import BaseModel
from datetime import datetime
from typing import Optional


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
        from_attributes = True  # cho phép đọc từ SQLAlchemy model