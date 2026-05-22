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
        self.text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150)

    async def ingest_document(self, file: UploadFile, db: Session):
        # 1. Tạo bản ghi trong Database
        db_doc = DBDocument(
            filename=file.filename,
            file_size=file.size,
            status="processing"
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)

        temp_path = ""
        try:
            # 2. Lưu file JSON tạm ra đĩa
            temp_dir = "temp_uploads"
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = os.path.join(temp_dir, file.filename)

            with open(temp_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)

            # 3. Phân tích file JSON
            with open(temp_path, "r", encoding="utf-8") as f:
                try:
                    json_data = json.load(f)
                except json.JSONDecodeError:
                    raise ValueError("Nội dung file không phải là cấu trúc JSON hợp lệ.")

            if not json_data:
                raise ValueError("File JSON trống.")

            documents = []

            # Xử lý thông minh: Nếu JSON là một danh sách (như file gitlab_tech_data.json)
            if isinstance(json_data, list):
                for item in json_data:
                    # Lấy phần "content" để băm nhỏ, nếu không có "content" thì biến cả cụm thành chữ
                    content_text = item.get("content", str(item))
                    chunks = self.text_splitter.split_text(content_text)
                    
                    # Lấy các trường còn lại (ví dụ: title, category) làm Metadata cho RAG
                    metadata = {k: v for k, v in item.items() if k != "content"}
                    metadata["source"] = file.filename
                    metadata["doc_id"] = db_doc.id

                    for chunk in chunks:
                        documents.append(Document(page_content=chunk, metadata=metadata))
            else:
                # Xử lý nếu JSON chỉ là một Object bình thường
                text_content = json.dumps(json_data, ensure_ascii=False)
                chunks = self.text_splitter.split_text(text_content)
                documents = [
                    Document(page_content=chunk, metadata={"source": file.filename, "doc_id": db_doc.id})
                    for chunk in chunks
                ]

            # 4. Đưa vào Vector DB (Qdrant)
            if not documents:
                raise ValueError("Không trích xuất được văn bản nào từ file JSON.")
                
            self.vector_db.add_documents(documents)
            chunks_count = len(documents)

            # 5. Cập nhật trạng thái thành công
            db_doc.status = "embedded"
            db_doc.chunk_count = chunks_count
            db.commit()

            return {
                "success": True, 
                "message": "Đã index thành công file JSON", 
                "chunks_indexed": chunks_count
            }

        except Exception as e:
            db_doc.status = "failed"
            db.commit()
            return {"success": False, "message": f"Lỗi khi index JSON: {str(e)}"}
            
        finally:
            # 6. Dọn dẹp file tạm
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)