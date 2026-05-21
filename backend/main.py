from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text, inspect

from app.api.chat import router as chat_router
from app.api.history import router as history_router
from app.api.ingest import router as ingest_router
from app.api.upload import router as upload_router
from app.core.database import engine, Base
from app.models.message import Message  # noqa: F401
from app.models.user import User        # noqa: F401
from app.core.minio_client import ensure_bucket
from ai_engine.vector_db import VectorDBManager
from app.tasks.ingest_task import ingest_handbook_task


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
    # Tạo bảng Postgres
    Base.metadata.create_all(bind=engine)
    # Khởi tạo MinIO bucket
    try:
        ensure_bucket()
        print("✅ MinIO bucket sẵn sàng")
    except Exception as e:
        print(f"⚠️ MinIO chưa sẵn sàng: {e}")

    # Tự động ingest nếu Qdrant rỗng
    try:
        db_manager = VectorDBManager()
        count = db_manager.client.count("gitlab_handbook").count
        if count == 0:
            print("⚡ Qdrant rỗng → Đẩy ingest vào background queue...")
            ingest_handbook_task.delay("/data/handbook")
            print("✅ Task đã được đẩy vào Celery queue")
        else:
            print(f"✅ Qdrant đã có {count} vectors → Bỏ qua ingest")
    except Exception as e:
        print(f"⚠️ Lỗi kiểm tra Qdrant: {e}")

    yield


app = FastAPI(title="RAG Solution - Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)
app.include_router(history_router)
app.include_router(ingest_router)
app.include_router(upload_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/")
def root():
    return {"message": "Backend RAG đang chạy ngon lành rồi nhé!"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)