from fastapi import APIRouter, HTTPException
from app.schemas.ingest import IngestRequest, IngestResponse
from app.tasks.ingest_task import ingest_document_task
from ai_engine.vector_db import VectorDBManager

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/", response_model=IngestResponse)
def ingest(request: IngestRequest):
    try:
        content = request.content

        if not content and request.file_path:
            with open(request.file_path, "r", encoding="utf-8") as f:
                content = f.read()

        if not content:
            return IngestResponse(success=False, message="Không có nội dung để index")

        # ✅ Đẩy vào queue, không block API
        task = ingest_document_task.delay(content, request.metadata or {})

        return IngestResponse(
            success=True,
            message=f"Đã đưa vào hàng đợi. Task ID: {task.id}",
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
def get_status():
    try:
        vdb = VectorDBManager()
        count = vdb.client.get_collection(vdb.collection_name).points_count
        return {"status": "ok", "total_chunks": count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.get("/task/{task_id}")
def get_task_status(task_id: str):
    """Kiểm tra tiến độ task đang chạy"""
    from app.core.celery_app import celery_app
    task = celery_app.AsyncResult(task_id)
    return {
        "task_id": task_id,
        "state": task.state,
        "detail": task.info,
    }