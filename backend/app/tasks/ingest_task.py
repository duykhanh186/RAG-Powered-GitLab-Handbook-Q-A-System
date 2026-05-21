from app.core.celery_app import celery_app
from ai_engine.processor import GitLabHandbookProcessor
from ai_engine.vector_db import VectorDBManager


@celery_app.task(bind=True, name="ingest_handbook")
def ingest_handbook_task(self, data_path: str):
    """
    Task chạy nền: chunking → embedding → lưu Qdrant
    Không block API, user không phải chờ
    """
    try:
        self.update_state(state="PROGRESS", meta={"status": "Đang xử lý file..."})

        processor = GitLabHandbookProcessor(data_path)
        chunks = processor.process_all()

        if not chunks:
            return {"status": "failed", "message": "Không tìm thấy file .md nào"}

        self.update_state(state="PROGRESS", meta={
            "status": f"Đang nạp {len(chunks)} chunks vào Qdrant..."
        })

        db_manager = VectorDBManager()
        db_manager.add_documents(chunks)

        return {
            "status": "success",
            "chunks_indexed": len(chunks),
            "message": f"Ingest xong {len(chunks)} chunks"
        }

    except Exception as e:
        self.update_state(state="FAILURE", meta={"status": f"Lỗi: {str(e)}"})
        raise


@celery_app.task(bind=True, name="ingest_document")
def ingest_document_task(self, content: str, metadata: dict = {}):
    """
    Task chạy nền: ingest 1 document đơn lẻ từ API
    """
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_core.documents import Document

        splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)
        chunks = splitter.split_text(content)
        documents = [Document(page_content=c, metadata=metadata) for c in chunks]

        db_manager = VectorDBManager()
        db_manager.add_documents(documents)

        return {
            "status": "success",
            "chunks_indexed": len(documents)
        }

    except Exception as e:
        raise