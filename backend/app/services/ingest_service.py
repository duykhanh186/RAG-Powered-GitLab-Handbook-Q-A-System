import os
import json
import shutil
from fastapi import UploadFile
from sqlalchemy.orm import Session
from app.models.document import Document as DBDocument
from ai_engine.vector_db import VectorDBManager
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

class IngestService:
    def __init__(self):
        self.vector_db = VectorDBManager()
        # Đọc cấu hình RAG động từ Admin Settings
        from app.core.config import read_rag_settings
        rag_settings = read_rag_settings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=rag_settings["chunk_size"],
            chunk_overlap=rag_settings["chunk_overlap"]
        )

    async def ingest_document(self, file: UploadFile, db: Session):
        # Tải cấu hình RAG động từ Settings để áp dụng tức thì
        from app.core.config import read_rag_settings
        rag_settings = read_rag_settings()
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=rag_settings["chunk_size"],
            chunk_overlap=rag_settings["chunk_overlap"]
        )

        # 1. Tạo bản ghi trong Database ban đầu với file_size tạm thời là 0
        db_doc = DBDocument(
            filename=file.filename,
            file_size=0,
            status="processing"
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)

        temp_path = ""
        try:
            # 2. Lưu file tạm ra đĩa
            temp_dir = "temp_uploads"
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, file.filename)

            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # Cập nhật kích thước file thực tế từ đĩa
            file_size = os.path.getsize(temp_path)
            
            # ✅ Upload file gốc lên MinIO Object Storage
            import uuid
            from app.core.minio_client import ensure_bucket, BUCKET_NAME
            
            minio_object_name = f"{uuid.uuid4()}_{file.filename}"
            client = ensure_bucket()
            with open(temp_path, "rb") as f:
                client.put_object(
                    BUCKET_NAME,
                    minio_object_name,
                    f,
                    length=file_size,
                    content_type=file.content_type or "application/octet-stream",
                )

            # Cập nhật thông tin kích thước và tên đối tượng trên MinIO
            db_doc.file_size = file_size
            db_doc.minio_object_name = minio_object_name
            db.commit()

            documents = []
            filename_lower = file.filename.lower()

            # 3. Phân tích nội dung theo loại file
            if filename_lower.endswith(".json"):
                with open(temp_path, "r", encoding="utf-8") as f:
                    try:
                        json_data = json.load(f)
                    except json.JSONDecodeError:
                        raise ValueError("Nội dung file không phải là cấu trúc JSON hợp lệ.")

                if not json_data:
                    raise ValueError("File JSON trống.")

                if isinstance(json_data, list):
                    for item in json_data:
                        content_text = item.get("content", str(item))
                        chunks = self.text_splitter.split_text(content_text)
                        
                        metadata = {k: v for k, v in item.items() if k != "content"}
                        metadata["source"] = file.filename
                        metadata["doc_id"] = db_doc.id

                        for chunk in chunks:
                            documents.append(Document(page_content=chunk, metadata=metadata))
                else:
                    text_content = json.dumps(json_data, ensure_ascii=False)
                    chunks = self.text_splitter.split_text(text_content)
                    documents = [
                        Document(page_content=chunk, metadata={"source": file.filename, "doc_id": db_doc.id})
                        for chunk in chunks
                    ]

            elif filename_lower.endswith(".txt") or filename_lower.endswith(".md"):
                with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
                    text_content = f.read()

                if not text_content.strip():
                    raise ValueError("Nội dung file trống.")

                chunks = self.text_splitter.split_text(text_content)
                documents = [
                    Document(page_content=chunk, metadata={"source": file.filename, "doc_id": db_doc.id})
                    for chunk in chunks
                ]

            elif filename_lower.endswith(".pdf"):
                try:
                    import pypdf
                except ImportError:
                    raise ImportError("Thư viện 'pypdf' chưa được cài đặt trên server.")
                
                reader = pypdf.PdfReader(temp_path)
                text_content = ""
                for page in reader.pages:
                    text_content += page.extract_text() or ""

                if not text_content.strip():
                    raise ValueError("Không trích xuất được nội dung chữ từ file PDF.")

                chunks = self.text_splitter.split_text(text_content)
                documents = [
                    Document(page_content=chunk, metadata={"source": file.filename, "doc_id": db_doc.id})
                    for chunk in chunks
                ]

            elif filename_lower.endswith(".docx"):
                try:
                    import docx
                except ImportError:
                    raise ImportError("Thư viện 'python-docx' chưa được cài đặt trên server.")

                doc = docx.Document(temp_path)
                text_content = "\n".join([p.text for p in doc.paragraphs])

                if not text_content.strip():
                    raise ValueError("Không trích xuất được nội dung chữ từ file DOCX.")

                chunks = self.text_splitter.split_text(text_content)
                documents = [
                    Document(page_content=chunk, metadata={"source": file.filename, "doc_id": db_doc.id})
                    for chunk in chunks
                ]

            else:
                raise ValueError("Định dạng file không được hệ thống hỗ trợ.")

            # 4. Đưa các chunks vào Qdrant Vector DB
            if not documents:
                raise ValueError("Không trích xuất được văn bản nào từ tài liệu.")
                
            self.vector_db.add_documents(documents)
            chunks_count = len(documents)

            # 5. Cập nhật trạng thái thành công
            db_doc.status = "embedded"
            db_doc.chunk_count = chunks_count
            db.commit()

            return {
                "success": True, 
                "message": f"Đã lập chỉ mục thành công tài liệu: {file.filename}", 
                "chunks_indexed": chunks_count
            }

        except Exception as e:
            db_doc.status = "failed"
            db.commit()
            return {"success": False, "message": f"Lỗi khi xử lý tài liệu: {str(e)}"}
            
        finally:
            # 6. Dọn dẹp file tạm
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)