from fastapi import APIRouter, HTTPException, UploadFile, File, Depends
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.services.ingest_service import IngestService

router = APIRouter(prefix="/api/ingest", tags=["ingest"])

@router.post("/")
async def ingest(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """API chỉ nhận file JSON từ giao diện và nhúng vào Qdrant"""
    # CHẶN TẤT CẢ CÁC FILE KHÔNG PHẢI JSON
    if not file.filename.lower().endswith(".json"):
        raise HTTPException(status_code=400, detail="Hệ thống chỉ chấp nhận định dạng file .json")

    try:
        service = IngestService()
        return await service.ingest_document(file, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
def get_status():
    try:
        from ai_engine.vector_db import VectorDBManager
        vdb = VectorDBManager()
        collection_info = vdb.client.get_collection(vdb.collection_name)
        count = collection_info.points_count
        return {"status": "ok", "total_chunks": count}
    except Exception as e:
        return {"status": "error", "detail": str(e)}