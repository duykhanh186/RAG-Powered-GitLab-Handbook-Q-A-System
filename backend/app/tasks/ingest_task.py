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
def ingest_document_task(self, object_name: str, filename: str, content_type: str, metadata: dict = {}):
    """
    Task chạy nền bất đồng bộ:
    Tải file từ MinIO -> Trích xuất text (TXT, MD, JSON, PDF, DOCX) -> Cắt đoạn -> Embedding Qdrant
    """
    import os
    import json
    from app.core.minio_client import ensure_bucket, BUCKET_NAME
    from langchain_text_splitters import RecursiveCharacterTextSplitter
    from langchain_core.documents import Document
    from app.core.config import read_rag_settings

    temp_path = ""
    try:
        # 1. Kết nối MinIO và tải tệp tin về thư mục tạm cục bộ
        temp_dir = "temp_celery_uploads"
        os.makedirs(temp_dir, exist_ok=True)
        temp_path = os.path.join(temp_dir, f"celery_{object_name}")

        client = ensure_bucket()
        client.fget_object(BUCKET_NAME, object_name, temp_path)

        # 2. Đọc cấu hình RAG động
        rag_settings = read_rag_settings()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=rag_settings["chunk_size"],
            chunk_overlap=rag_settings["chunk_overlap"]
        )

        documents = []
        filename_lower = filename.lower()

        # 3. Phân tích nội dung theo loại tệp tin
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
                    chunks = splitter.split_text(content_text)
                    
                    item_metadata = {k: v for k, v in item.items() if k != "content"}
                    item_metadata.update(metadata)
                    item_metadata["source"] = filename

                    for chunk in chunks:
                        documents.append(Document(page_content=chunk, metadata=item_metadata))
            else:
                text_content = json.dumps(json_data, ensure_ascii=False)
                chunks = splitter.split_text(text_content)
                documents = [
                    Document(page_content=chunk, metadata=metadata)
                    for chunk in chunks
                ]

        elif filename_lower.endswith(".txt") or filename_lower.endswith(".md"):
            with open(temp_path, "r", encoding="utf-8", errors="ignore") as f:
                text_content = f.read()

            if not text_content.strip():
                raise ValueError("Nội dung file trống.")

            chunks = splitter.split_text(text_content)
            documents = [
                Document(page_content=chunk, metadata=metadata)
                for chunk in chunks
            ]

        elif filename_lower.endswith(".pdf"):
            import pypdf
            reader = pypdf.PdfReader(temp_path)
            text_content = ""
            for page in reader.pages:
                text_content += page.extract_text() or ""

            if not text_content.strip():
                raise ValueError("Không trích xuất được nội dung chữ từ file PDF.")

            chunks = splitter.split_text(text_content)
            documents = [
                Document(page_content=chunk, metadata=metadata)
                for chunk in chunks
            ]

        elif filename_lower.endswith(".docx"):
            import docx
            doc = docx.Document(temp_path)
            text_content = "\n".join([p.text for p in doc.paragraphs])

            if not text_content.strip():
                raise ValueError("Không trích xuất được nội dung chữ từ file DOCX.")

            chunks = splitter.split_text(text_content)
            documents = [
                Document(page_content=chunk, metadata=metadata)
                for chunk in chunks
            ]

        else:
            raise ValueError(f"Định dạng tệp {filename} không được hệ thống hỗ trợ.")

        if not documents:
            raise ValueError("Không trích xuất được văn bản nào từ tài liệu.")

        # 4. Nạp các đoạn văn bản (chunks) vào Qdrant Vector DB
        db_manager = VectorDBManager()
        db_manager.add_documents(documents)

        return {
            "status": "success",
            "chunks_indexed": len(documents),
            "filename": filename,
            "object_name": object_name
        }

    except Exception as e:
        print(f"[!] Lỗi khi xử lý chạy nền tài liệu {filename}: {str(e)}")
        raise
    finally:
        # 5. Dọn dẹp sạch sẽ tệp tạm cục bộ
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass