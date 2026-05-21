# Chat endpoint
# HIEP viet lai Chat API
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import ChatService

router = APIRouter(prefix="/api/chat", tags=["chat"])

# Khởi tạo instance duy nhất để tránh load lại embedding model trên mỗi request
chat_service = ChatService()


@router.post("/", response_model=ChatResponse)
def chat(request: ChatRequest, db: Session = Depends(get_db)):
    """Gửi câu hỏi và nhận câu trả lời từ AI, có context lịch sử."""
    try:
        return chat_service.process_message(request, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))