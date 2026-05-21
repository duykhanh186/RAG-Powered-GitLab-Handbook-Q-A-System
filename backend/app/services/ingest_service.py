# Ingest service
# HIEP viet lai Ingest service logic
from app.schemas.ingest import IngestRequest, IngestResponse
from ai_engine.vector_db import VectorDBManager
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


class IngestService:
    def __init__(self):
        self.vector_db = VectorDBManager()
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)

    def ingest_document(self, request: IngestRequest) -> IngestResponse:
        try:
            # Lấy nội dung cần index
            content = request.content

            if not content and request.file_path:
                with open(request.file_path, "r", encoding="utf-8") as f:
                    content = f.read()

            if not content:
                return IngestResponse(
                    success=False,
                    message="Không có nội dung để index",
                )

            # Phân tách văn bản
            chunks = self.text_splitter.split_text(content)
            documents = [Document(page_content=chunk, metadata=request.metadata or {}) for chunk in chunks]

            # Đưa vào vector DB (Qdrant)
            self.vector_db.add_documents(documents)
            chunks_count = len(documents)

            return IngestResponse(
                success=True,
                message=f"Đã index thành công",
                chunks_indexed=chunks_count,
            )

        except Exception as e:
            return IngestResponse(
                success=False,
                message=f"Lỗi khi index: {str(e)}",
            )