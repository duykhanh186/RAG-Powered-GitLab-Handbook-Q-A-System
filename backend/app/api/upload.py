import io
import uuid
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.core.minio_client import ensure_bucket, BUCKET_NAME
from app.tasks.ingest_task import ingest_document_task

router = APIRouter(prefix="/api/upload", tags=["upload"])

ALLOWED_TYPES = ["text/plain", "text/markdown", "application/pdf"]


@router.post("/")
async def upload_file(file: UploadFile = File(...)):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Chỉ hỗ trợ: {ALLOWED_TYPES}")

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
            content_type=file.content_type,
        )

        # ✅ Đẩy ingest vào Celery queue (không block)
        text_content = content.decode("utf-8", errors="ignore")
        task = ingest_document_task.delay(
            text_content,
            {"source": file.filename, "object_name": object_name}
        )

        return {
            "success": True,
            "filename": file.filename,
            "object_name": object_name,
            "size": file_size,
            "task_id": task.id,
            "message": "File đã lưu vào MinIO và đang ingest vào Qdrant"
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
    """Xóa file khỏi MinIO"""
    try:
        client = ensure_bucket()
        client.remove_object(BUCKET_NAME, object_name)
        return {"success": True, "message": f"Đã xóa {object_name}"}
    except Exception as e:
        raise HTTPException(500, str(e))