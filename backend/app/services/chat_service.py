# Chat service
# HIEP viet lai Chat service logic
import uuid
import json
import time  # Thêm time để tự tính TTL cho cache
from sqlalchemy.orm import Session
from ai_engine.rag_chain import RAGChain
from app.models.message import Message
from app.schemas.chat import ChatRequest, ChatResponse
import redis

# ---- KHỞI TẠO CACHE ĐA LỚP  ----
# Lớp 1: Local RAM bằng dict thuần Python
# Cấu trúc lưu: { "cache_key": {"data": chat_history, "expire_at": timestamp} }
local_history_cache = {}
LOCAL_CACHE_TTL = 60  # Hết hạn sau 60 giây

# Lớp 2: Redis Cache
redis_client = redis.Redis(host='redis', port=6379, db=0, decode_responses=True)


class ChatService:
    def __init__(self):
        self.processor = RAGChain()

    def process_message(self, request: ChatRequest, db: Session) -> ChatResponse:
        # ✅ Tạo session_id mới nếu chưa có
        session_id = request.session_id or str(uuid.uuid4())
        cache_key = f"chat_history:{session_id}"
        
        chat_history = None
        current_time = time.time()

        # 🔍 LỚP 1: KIỂM TRA LOCAL CACHE (RAM BACKEND)
        if cache_key in local_history_cache:
            cache_item = local_history_cache[cache_key]
            # Check xem cache đã hết hạn chưa
            if current_time < cache_item["expire_at"]:
                chat_history = cache_item["data"]
            else:
                # Hết hạn thì xóa luôn
                local_history_cache.pop(cache_key, None)

        # 🔍 LỚP 2: KIỂM TRA REDIS CACHE (Nếu Lớp 1 trượt)
        if chat_history is None:
            redis_data = redis_client.get(cache_key)
            if redis_data:
                chat_history = json.loads(redis_data)
                # Đập ngược lại Lớp 1 kèm thời gian hết hạn mới
                local_history_cache[cache_key] = {
                    "data": chat_history,
                    "expire_at": time.time() + LOCAL_CACHE_TTL
                }

        # 🔍 LỚP 3: TRUY VẤN DATABASE GỐC (Nếu cả 2 lớp cache đều trượt)
        if chat_history is None:
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
            
            # Set vào Redis (TTL 10 phút = 600s)
            redis_client.setex(cache_key, 600, json.dumps(chat_history))
            # Set vào Local RAM tự chế
            local_history_cache[cache_key] = {
                "data": chat_history,
                "expire_at": time.time() + LOCAL_CACHE_TTL
            }

        # ✅ Gọi AI engine với context lịch sử
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

        # ✅ Lưu message mới vào PostgreSQL kèm session_id
        message = Message(
            question=request.question,
            answer=answer,
            sources=json.dumps(sources),
            session_id=session_id,
            user_id=getattr(request, "user_id", None),
        )
        db.add(message)
        db.commit()
        db.refresh(message)

        # 💾 CẬP NHẬT LẠI CACHE ĐỂ LƯỢT CHAT SAU CÓ LUÔN CÂU VỪA CHAT
        new_turn = {"question": request.question, "answer": answer}
        chat_history.append(new_turn)
        
        if len(chat_history) > 10:
            chat_history = chat_history[-10:]

        # Ghi đè lịch sử mới vào cả Redis và Local Cache tự chế
        redis_client.setex(cache_key, 600, json.dumps(chat_history))
        local_history_cache[cache_key] = {
            "data": chat_history,
            "expire_at": time.time() + LOCAL_CACHE_TTL
        }

        return ChatResponse(
            answer=answer,
            sources=sources,
            session_id=session_id,
            created_at=message.created_at,
        )