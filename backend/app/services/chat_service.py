# Chat service
# HIEP viet lai Chat service logic
import uuid
from sqlalchemy.orm import Session
from ai_engine.rag_chain import RAGChain
from app.models.message import Message
from app.schemas.chat import ChatRequest, ChatResponse


class ChatService:
    def __init__(self):
        self.processor = RAGChain()

    def process_message(self, request: ChatRequest, db: Session) -> ChatResponse:
        # ✅ Tạo session_id mới nếu chưa có
        session_id = request.session_id or str(uuid.uuid4())

        # ✅ Lấy lịch sử hội thoại của session này (tối đa 10 cặp gần nhất)
        history_messages = (
            db.query(Message)
            .filter(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
            .limit(10)
            .all()
        )

        # ✅ Chuyển lịch sử sang dạng list để truyền vào AI
        chat_history = [
            {"question": m.question, "answer": m.answer}
            for m in history_messages
        ]

        # ✅ Gọi AI engine với context lịch sử
        # RAGChain.ask() trả về tuple (answer, docs)
        answer, docs = self.processor.ask(
            request.question,
            chat_history=chat_history,
        )

        # ✅ Trích xuất nguồn tài liệu độc bản (deduplicated)
        seen_sources = set()
        sources = []
        for doc in docs:
            src_path = doc.metadata.get("source", "Handbook")
            if src_path not in seen_sources:
                seen_sources.add(src_path)
                sources.append({
                    "content": doc.page_content,
                    "source": src_path
                })

        import json

        # ✅ Lưu message mới vào PostgreSQL kèm session_id
        message = Message(
            question=request.question,
            answer=answer,
            sources=json.dumps(sources),
            session_id=session_id,
            user_id=getattr(request, "user_id", None),  # nếu có auth sau này
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        return ChatResponse(
            answer=answer,
            sources=sources,
            session_id=session_id,  # ✅ trả về session_id để frontend lưu lại
            created_at=message.created_at,
        )