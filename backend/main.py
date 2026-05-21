from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text, inspect

from app.api.chat import router as chat_router
from app.api.history import router as history_router
from app.api.ingest import router as ingest_router
from app.core.database import engine, Base

# Import models để Base biết bảng Message, User mà tạo
from app.models.message import Message  # noqa: F401
from app.models.user import User        # noqa: F401


def _auto_migrate():
    """Tự động thêm cột mới vào bảng đã tồn tại.
    create_all() chỉ tạo bảng mới, không thêm cột mới vào bảng cũ.
    Hàm này đảm bảo schema luôn đồng bộ trên mọi máy."""
    inspector = inspect(engine)
    if "messages" in inspector.get_table_names():
        existing_cols = {col["name"] for col in inspector.get_columns("messages")}
        with engine.connect() as conn:
            if "session_id" not in existing_cols:
                conn.execute(text("ALTER TABLE messages ADD COLUMN session_id VARCHAR(36)"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_messages_session_id ON messages(session_id)"))
            if "user_id" not in existing_cols:
                conn.execute(text("ALTER TABLE messages ADD COLUMN user_id INTEGER REFERENCES users(id)"))
            conn.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Tự động tạo bảng trong Postgres nếu chưa có
    # Tránh lỗi "Relation does not exist"
    Base.metadata.create_all(bind=engine)
    # Thêm cột mới nếu bảng đã tồn tại từ trước
    _auto_migrate()
    yield


app = FastAPI(
    title="RAG Solution - Backend",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Đăng ký các router
app.include_router(chat_router)
app.include_router(history_router)
app.include_router(ingest_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Backend RAG đang chạy ngon lành rồi nhé!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)