import io
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.minio_client import ensure_bucket, BUCKET_NAME
from app.tasks.ingest_task import ingest_document_task

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_EXTS = [".json", ".txt", ".md", ".pdf", ".docx"]


@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    filename_lower = file.filename.lower()
    if not any(filename_lower.endswith(ext) for ext in ALLOWED_EXTS):
        raise HTTPException(
            status_code=400,
            detail=f"Hệ thống chỉ chấp nhận định dạng file: {', '.join(ALLOWED_EXTS)}"
        )

    try:
        client = ensure_bucket()
        content = await file.read()
        file_size = len(content)
        object_name = f"{uuid.uuid4()}_{file.filename}"

        # ✅ Lưu file gốc vào MinIO
        client.put_object(
            BUCKET_NAME,
            object_name,
            io.BytesIO(content),
            length=file_size,
            content_type=file.content_type or "application/octet-stream",
        )

        # ✅ Đẩy ingest vào Celery queue (chỉ truyền tham chiếu tệp tin siêu nhẹ)
        task = ingest_document_task.delay(
            object_name=object_name,
            filename=file.filename,
            content_type=file.content_type or "application/octet-stream",
            metadata={"source": file.filename, "object_name": object_name}
        )

        return {
            "success": True,
            "filename": file.filename,
            "object_name": object_name,
            "size": file_size,
            "task_id": task.id,
            "message": "File đã lưu vào MinIO và đang gửi yêu cầu ingest bất đồng bộ"
        }

    except Exception as e:
        raise HTTPException(500, str(e))


@router.get("/files")
def list_files():
    """Liệt kê tất cả file trong MinIO"""
    try:
        client = ensure_bucket()
        objects = list(client.list_objects(BUCKET_NAME))
        files = []
        for obj in objects:
            files.append({
                "name": obj.object_name,
                "size": obj.size,
                "last_modified": str(obj.last_modified),
            })
        return {"files": files, "total": len(files)}
    except Exception as e:
        raise HTTPException(500, str(e))


@router.delete("/files/{object_name}")
def delete_file(object_name: str):
    """Xóa file khỏi MinIO và Qdrant Vector DB"""
    try:
        # 1. Xóa file gốc khỏi MinIO
        client = ensure_bucket()
        client.remove_object(BUCKET_NAME, object_name)

        # 2. Xóa các vectors liên quan đến object_name này trong Qdrant Vector DB
        try:
            from ai_engine.vector_db import VectorDBManager
            from qdrant_client.http.models import Filter, FieldCondition, MatchValue
            
            vdb = VectorDBManager()
            vdb.client.delete(
                collection_name=vdb.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="metadata.object_name",
                            match=MatchValue(value=object_name)
                        )
                    ]
                )
            )
            print(f"[*] Đã xóa thành công vectors khỏi Qdrant cho file: {object_name}")
            
            # 3. Làm mới cache Dashboard Admin
            from app.api.admin import invalidate_qdrant_cache
            invalidate_qdrant_cache()
            
        except Exception as qe:
            print(f"[!] Cảnh báo: Lỗi khi xóa vectors trong Qdrant cho file {object_name}: {str(qe)}")

        return {"success": True, "message": f"Đã xóa thành công tệp tin {object_name} khỏi hệ thống."}
    except Exception as e:
        raise HTTPException(500, str(e))