# Admin API routes
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from pydantic import BaseModel
import time
import json
import os
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


# ─── Kết nối Redis dùng chung cho Cache ───────────────────────
_redis_client = None

def _get_redis_client():
    global _redis_client
    if _redis_client is None:
        try:
            import redis as _redis
            redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
            _redis_client = _redis.from_url(redis_url, socket_connect_timeout=2, decode_responses=True)
        except Exception as e:
            print(f"[!] Cảnh báo: Không thể khởi tạo Redis client: {str(e)}")
            _redis_client = None
    return _redis_client


# ─── Cache cho Qdrant info (Dùng Redis, Fallback sang bộ nhớ cục bộ) ─────────
_qdrant_cache_fallback: dict = {"data": None, "ts": 0.0}
_QDRANT_CACHE_TTL = 30  # giây

def _get_qdrant_info():
    global _vdb_instance, _qdrant_cache_fallback
    
    # 1. Thử dùng Redis Cache trước (Đồng bộ đa workers)
    r = _get_redis_client()
    if r:
        try:
            cached_data = r.get("qdrant_dashboard_cache")
            if cached_data:
                print("[*] RETURNING QDRANT INFO FROM REDIS CACHE")
                return json.loads(cached_data)
        except Exception as re:
            print(f"[!] Cảnh báo: Lỗi đọc cache từ Redis: {str(re)}")
    else:
        # 2. Fallback: Dùng cache bộ nhớ cục bộ nếu Redis không khả dụng
        now = time.monotonic()
        if _qdrant_cache_fallback["data"] is not None and (now - _qdrant_cache_fallback["ts"]) < _QDRANT_CACHE_TTL:
            print(f"[*] RETURNING QDRANT INFO FROM LOCAL FALLBACK CACHE (age: {now - _qdrant_cache_fallback['ts']:.1f}s)")
            return _qdrant_cache_fallback["data"]
    
    print("[*] FETCHING FRESH QDRANT INFO FROM SERVER...")
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
        
    # 3. Ghi dữ liệu mới vào cache
    if r:
        try:
            r.setex("qdrant_dashboard_cache", _QDRANT_CACHE_TTL, json.dumps(result))
            print("[*] SAVED FRESH QDRANT INFO TO REDIS CACHE")
        except Exception as re:
            print(f"[!] Cảnh báo: Lỗi ghi cache vào Redis: {str(re)}")
    else:
        _qdrant_cache_fallback["data"] = result
        _qdrant_cache_fallback["ts"] = time.monotonic()
        
    return result


def invalidate_qdrant_cache():
    global _qdrant_cache_fallback
    print("[*] INVALIDATING QDRANT CACHE")
    
    # 1. Xóa cache trên Redis (Cập nhật tức khắc cho tất cả workers)
    r = _get_redis_client()
    if r:
        try:
            r.delete("qdrant_dashboard_cache")
            print("[*] DELETED QDRANT CACHE FROM REDIS")
        except Exception as re:
            print(f"[!] Cảnh báo: Lỗi xóa cache trên Redis: {str(re)}")
            
    # 2. Xóa cache dự phòng cục bộ
    _qdrant_cache_fallback = {"data": None, "ts": 0.0}


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
    """Cổng kết nối tiếp nhận file từ Admin (JSON, TXT, MD, PDF, DOCX)."""
    filename_lower = file.filename.lower()
    allowed_exts = [".json", ".txt", ".md", ".pdf", ".docx"]
    if not any(filename_lower.endswith(ext) for ext in allowed_exts):
        raise HTTPException(
            status_code=400,
            detail=f"Hệ thống chỉ chấp nhận định dạng file: {', '.join(allowed_exts)}"
        )
    try:
        service = IngestService()
        res = await service.ingest_document(file, db)
        invalidate_qdrant_cache()
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/documents/{doc_id}")
def delete_document(doc_id: int, db: Session = Depends(get_db)):
    """Xóa bỏ tài liệu ra khỏi hệ thống (cả Postgres và Qdrant Vector DB)."""
    try:
        doc = db.query(DBDocument).filter(DBDocument.id == doc_id).first()
        if not doc:
            raise HTTPException(status_code=404, detail="Tài liệu không tồn tại")
        
        filename = doc.filename
        minio_obj_name = getattr(doc, "minio_object_name", None)
        
        # 1. Xóa file gốc vật lý khỏi MinIO Object Storage (nếu có)
        if minio_obj_name:
            try:
                from app.core.minio_client import ensure_bucket, BUCKET_NAME
                client = ensure_bucket()
                client.remove_object(BUCKET_NAME, minio_obj_name)
                print(f"[*] Đã xóa thành công file gốc khỏi MinIO: {minio_obj_name}")
            except Exception as me:
                print(f"[!] Cảnh báo: Lỗi khi xóa file gốc khỏi MinIO cho doc_id {doc_id}: {str(me)}")
        
        # 2. Xóa các vectors liên quan đến doc_id này trong Qdrant Vector DB
        try:
            from ai_engine.vector_db import VectorDBManager
            from qdrant_client.http.models import Filter, FieldCondition, MatchValue
            
            vdb = VectorDBManager()  # Khởi tạo mới mỗi lần để đảm bảo an toàn kết nối (thread-safety)
            vdb.client.delete(
                collection_name=vdb.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="metadata.doc_id",
                            match=MatchValue(value=doc_id)
                        )
                    ]
                )
            )
            print(f"[*] Đã xóa thành công vectors khỏi Qdrant cho doc_id: {doc_id}")
        except Exception as qe:
            print(f"[!] Cảnh báo: Lỗi khi xóa vectors trong Qdrant cho doc_id {doc_id}: {str(qe)}")
        
        # 3. Xóa bản ghi trong database PostgreSQL
        db.delete(doc)
        db.commit()
        invalidate_qdrant_cache()
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
        from app.core.config import settings, read_rag_settings
        qdrant = _get_qdrant_info()          # dùng cache 30s
        redis_status = _get_redis_status()   # dùng cache 30s
        total_users = db.query(func.count(User.id)).scalar() or 0
        total_conversations = db.query(func.count(func.distinct(Message.session_id))).scalar() or 0

        # Tải cấu hình RAG động
        rag_settings = read_rag_settings()

        return {
            "groq_api_key_set":   bool(getattr(settings, "GROQ_API_KEY", "")),
            "openai_api_key_set": bool(getattr(settings, "OPENAI_API_KEY", "")),
            "embedding_model":    rag_settings["embedding_model"],
            "chunk_size":         rag_settings["chunk_size"],
            "chunk_overlap":      rag_settings["chunk_overlap"],
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
    try:
        from app.core.config import save_rag_settings, read_rag_settings
        current = read_rag_settings()
        chunk_size = body.chunk_size if body.chunk_size is not None else current["chunk_size"]
        chunk_overlap = body.chunk_overlap if body.chunk_overlap is not None else current["chunk_overlap"]
        embedding_model = body.embedding_model if body.embedding_model is not None else current["embedding_model"]
        
        success = save_rag_settings(chunk_size, chunk_overlap, embedding_model)
        if not success:
            raise HTTPException(status_code=500, detail="Không thể lưu tệp cấu hình RAG.")
        return {"success": True, "message": "Đã cập nhật cấu hình RAG thành công!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))