# Admin API routes
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from pydantic import BaseModel
import time
from app.core.database import get_db
from app.models.user import User
from app.models.message import Message
from app.models.document import Document as DBDocument
from app.services.ingest_service import IngestService

# VectorDBManager được import ở đây (lazy-safe): nếu ai_engine chưa cài
# hoặc Qdrant chưa start, lỗi sẽ được bắt trong từng hàm, server vẫn chạy bình thường
try:
    from ai_engine.vector_db import VectorDBManager as _VectorDBManager
except ImportError:
    _VectorDBManager = None

router = APIRouter(prefix="/api/admin", tags=["admin"])


# ─── Schemas ──────────────────────────────────────────────────
class UserCreate(BaseModel):
    username: str
    email: str
    role: Optional[str] = "user"

class UserRoleUpdate(BaseModel):
    role: str

class SettingsUpdate(BaseModel):
    embedding_model: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None


# ─── Singleton cache cho VectorDBManager (tránh khởi tạo lại mỗi request) ────
_vdb_instance = None

def _get_vdb():
    global _vdb_instance
    if _VectorDBManager is None:
        raise RuntimeError("ai_engine.vector_db không thể import được")
    if _vdb_instance is None:
        _vdb_instance = _VectorDBManager()
    return _vdb_instance


# ─── Cache cho Qdrant info (TTL 30 giây, tránh gọi lại mỗi request) ──────────
_qdrant_cache: dict = {"data": None, "ts": 0.0}
_QDRANT_CACHE_TTL = 30  # giây

def _get_qdrant_info():
    global _vdb_instance, _qdrant_cache
    now = time.monotonic()
    # Trả về cache nếu còn hiệu lực
    if _qdrant_cache["data"] is not None and (now - _qdrant_cache["ts"]) < _QDRANT_CACHE_TTL:
        return _qdrant_cache["data"]
    try:
        vdb = _get_vdb()
        info = vdb.client.get_collection(vdb.collection_name)
        result = {
            "status": "active",
            "total_vectors": info.points_count,
            "collection_name": vdb.collection_name,
        }
    except Exception as e:
        _vdb_instance = None  # reset nếu lỗi để thử lại lần sau
        result = {
            "status": "error",
            "total_vectors": 0,
            "collection_name": "unknown",
            "detail": str(e),
        }
    _qdrant_cache["data"] = result
    _qdrant_cache["ts"] = now
    return result


# ─── Helper: kiểm tra Redis nhanh ─────────────────────────────
_redis_cache: dict = {"data": "unknown", "ts": 0.0}
_REDIS_CACHE_TTL = 30

def _get_redis_status() -> str:
    global _redis_cache
    now = time.monotonic()
    if (now - _redis_cache["ts"]) < _REDIS_CACHE_TTL:
        return _redis_cache["data"]
    try:
        import os, redis as _redis
        r = _redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"), socket_connect_timeout=2)
        r.ping()
        status = "active"
    except Exception:
        status = "error"
    _redis_cache["data"] = status
    _redis_cache["ts"] = now
    return status


# ─── DASHBOARD ────────────────────────────────────────────────
@router.get("/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Thống kê tổng hợp số liệu hiển thị trên Admin Dashboard."""
    try:
        total_users = db.query(func.count(User.id)).scalar() or 0
        total_conversations = db.query(
            func.count(func.distinct(Message.session_id))
        ).scalar() or 0
        total_messages = db.query(func.count(Message.id)).scalar() or 0

        qdrant = _get_qdrant_info()  # dùng cache 30s
        redis_status = _get_redis_status()  # dùng cache 30s

        # Thống kê từ bảng Documents chuẩn
        total_docs = db.query(func.count(DBDocument.id)).scalar() or 0
        indexed_docs = db.query(func.count(DBDocument.id)).filter(DBDocument.status == "embedded").scalar() or 0
        processing_docs = db.query(func.count(DBDocument.id)).filter(DBDocument.status.in_(["processing", "uploading"])).scalar() or 0
        failed_docs = db.query(func.count(DBDocument.id)).filter(DBDocument.status == "failed").scalar() or 0

        return {
            "total_users":         total_users,
            "total_conversations": total_conversations,
            "total_messages":      total_messages,
            "total_vectors":       qdrant["total_vectors"],
            "total_documents":     total_docs,
            "indexed_documents":   indexed_docs,
            "processing_count":    processing_docs,
            "failed_count":        failed_docs,
            "qdrant_status":       qdrant["status"],
            "collection_name":     qdrant["collection_name"],
            "status":              qdrant["status"],
            "worker_status":       "active" if redis_status == "active" else "unknown",
            "redis_status":        redis_status,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



# ─── DOCUMENTS ────────────────────────────────────────────────
@router.get("/documents")
def get_documents(db: Session = Depends(get_db)):
    """Lấy danh sách toàn bộ tài liệu có trong DB."""
    try:
        docs = db.query(DBDocument).order_by(DBDocument.id.desc()).all()

        recent_docs = [
            {
                "id":               doc.id,
                "filename":         doc.filename,
                "upload_date":      doc.created_at.isoformat() if hasattr(doc, 'created_at') and doc.created_at else None,
                "status":           doc.status,
                "chunk_count":      doc.chunk_count,
                "embedding_status": doc.status,
                "file_size":        doc.file_size,
            }
            for doc in docs
        ]

        return {"documents": recent_docs, "total": len(recent_docs)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/documents")
async def upload_document(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """Cổng kết nối tiếp nhận file JSON từ Admin."""
    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Hệ thống chỉ chấp nhận định dạng file .json")
    try:
        service = IngestService()
        return await service.ingest_document(file, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """Xóa bỏ tài liệu ra khỏi hệ thống."""
    try:
        doc = db.query(DBDocument).filter(DBDocument.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Tài liệu không tồn tại")
        
        filename = doc.filename
        db.delete(doc)
        db.commit()
        return {"success": True, "message": f"Đã xóa thành công tài liệu {filename}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reindex/{doc_id}")
def reindex_document(doc_id: int):
    return {"success": True, "message": f"Đã gửi yêu cầu re-index tài liệu có ID {doc_id}"}


# ─── USERS ────────────────────────────────────────────────────
@router.get("/users")
def get_users(db: Session = Depends(get_db)):
    try:
        users = db.query(User).order_by(User.created_at.desc()).all()
        return {
            "users": [
                {
                    "id":         u.id,
                    "username":   u.username,
                    "email":      u.email,
                    "role":       getattr(u, "role", "user"),
                    "created_at": u.created_at.isoformat() if u.created_at else None,
                }
                for u in users
            ],
            "total": len(users),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users")
def create_user(body: UserCreate, db: Session = Depends(get_db)):
    try:
        existing = db.query(User).filter(
            (User.username == body.username) | (User.email == body.email)
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Username hoặc email đã tồn tại")

        user = User(username=body.username, email=body.email)
        if hasattr(user, "role"):
            user.role = body.role

        db.add(user)
        db.commit()
        db.refresh(user)

        return {
            "id":       user.id,
            "username": user.username,
            "email":    user.email,
            "role":     getattr(user, "role", "user"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User không tồn tại")
        db.delete(user)
        db.commit()
        return {"success": True, "message": f"Đã xóa user {user_id}"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/users/{user_id}")
def update_user_role(user_id: int, body: UserRoleUpdate, db: Session = Depends(get_db)):
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="User không tồn tại")
        user.role = body.role
        db.commit()
        db.refresh(user)
        return {"id": user.id, "username": user.username, "role": user.role}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ─── SETTINGS ─────────────────────────────────────────────────
@router.get("/settings")
def get_settings(db: Session = Depends(get_db)):
    try:
        from app.core.config import settings
        qdrant = _get_qdrant_info()          # dùng cache 30s
        redis_status = _get_redis_status()   # dùng cache 30s
        total_users = db.query(func.count(User.id)).scalar() or 0
        total_conversations = db.query(func.count(func.distinct(Message.session_id))).scalar() or 0

        return {
            "groq_api_key_set":   bool(getattr(settings, "GROQ_API_KEY", "")),
            "openai_api_key_set": bool(getattr(settings, "OPENAI_API_KEY", "")),
            "embedding_model":    getattr(settings, "EMBEDDING_MODEL", ""),
            "chunk_size":         512,
            "chunk_overlap":      50,
            "qdrant_status":      qdrant["status"],
            "total_vectors":      qdrant["total_vectors"],
            "collection_name":    qdrant["collection_name"],
            "worker_status":      "active" if redis_status == "active" else "unknown",
            "redis_status":       redis_status,
            "celery_status":      "active" if redis_status == "active" else "unknown",
            "queue_length":       0,
            "active_workers":     0,
            "db_status":          "active",
            "total_users":        total_users,
            "total_conversations": total_conversations,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/settings")
def update_settings(body: SettingsUpdate):
    return {"success": True}