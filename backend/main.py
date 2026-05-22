from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text, inspect

from app.api.chat import router as chat_router
from app.api.history import router as history_router
from app.api.ingest import router as ingest_router
from app.api.upload import router as upload_router
from app.api.admin import router as admin_router
from app.core.database import engine, Base
from app.models.document import Document

# Import các models để Base metadata nhận diện và tự động khởi tạo cấu trúc bảng
from app.models.message import Message  # noqa: F401
from app.models.user import User        # noqa: F401
from ai_engine.embedding import get_embedding_model 


def _auto_migrate():
    """Tự động đồng bộ và thêm các cột mới vào bảng cơ sở dữ liệu hiện hữu.
    Lệnh create_all() chỉ tạo bảng mới chứ không tự động cập nhật các trường mới 
    vào bảng cũ, hàm này sẽ đảm bảo tính nhất quán của schema dữ liệu trên mọi môi trường.
    """
    inspector = inspect(engine)
    
    # Đồng bộ hóa cấu trúc cho bảng tin nhắn (messages)
    if "messages" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("messages")}
        with engine.connect() as conn:
            if "session_id" not in existing_cols:
                conn.execute(text("ALTER TABLE messages ADD COLUMN session_id VARCHAR(36)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)"))
            if "user_id" not in existing_cols:
                conn.execute(text("ALTER TABLE messages ADD COLUMN user_id INTEGER REFERENCES users(id)"))
            conn.commit()
            
    # Đồng bộ hóa cấu trúc cho bảng người dùng (users)
    if "users" in inspector.get_table_names():
        existing_user_cols = {col["name"] for col in inspector.get_columns("users")}
        with engine.connect() as conn:
            if "role" not in existing_user_cols:
                conn.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR DEFAULT 'user'"))
            conn.commit()

    # Đồng bộ hóa cấu trúc cho bảng tài liệu (documents)
    if "documents" in inspector.get_table_names():
        existing_doc_cols = {col["name"] for col in inspector.get_columns("documents")}
        with engine.connect() as conn:
            if "minio_object_name" not in existing_doc_cols:
                conn.execute(text("ALTER TABLE documents ADD COLUMN minio_object_name VARCHAR"))
            conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi tạo cấu trúc bảng PostgreSQL từ cấu hình models
    Base.metadata.create_all(bind=engine)
    
    # Thực hiện kiểm tra và cập nhật các cột dữ liệu bổ sung
    _auto_migrate()
    
    # Tải trước mô hình nhúng văn bản (Embedding Model) lên bộ nhớ
    get_embedding_model()
    yield


app = FastAPI(title="RAG Solution - Backend", lifespan=lifespan)

# Cấu hình Middleware xử lý chia sẻ tài nguyên giữa các nguồn khác nhau (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Tích hợp hệ thống phân tuyến (Routers) vào ứng dụng chính FastAPI
app.include_router(chat_router)
app.include_router(history_router)
app.include_router(ingest_router)
app.include_router(upload_router)
app.include_router(admin_router, tags=["Admin"])


@app.get("/health")
def health():
    """Endpoint kiểm tra trạng thái hoạt động nhanh của hệ thống."""
    return {"status": "ok"}


@app.get("/")
def root():
    """Trang chào mừng mặc định của phân hệ Backend."""
    return {"message": "Backend RAG đang chạy ngon lành rồi nhé!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)