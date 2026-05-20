# Ingest endpoint
# HIEP viet lai Ingest API
from fastapi import APIRouter, HTTPException

from app.schemas.ingest import IngestRequest, IngestResponse
from app.services.ingest_service import IngestService

router = APIRouter(prefix="/api/ingest", tags=["ingest"])


@router.post("/", response_model=IngestResponse)
def ingest(request: IngestRequest):
    try:
        service = IngestService()
        return service.ingest_document(request)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
def get_status():
    # Kiểm tra Qdrant có sẵn sàng không
    try:
        from ai_engine.vector_db import VectorDBManager
        vdb = VectorDBManager()
        collection_info = vdb.client.get_collection(vdb.collection_name)
        count = collection_info.points_count
        return {"status": "ok", "total_chunks": count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}