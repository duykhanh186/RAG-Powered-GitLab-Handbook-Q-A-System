import os
from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.http.models import Distance, VectorParams
from langchain_qdrant import QdrantVectorStore
from ai_engine.embedding import get_embedding_model
import time

class VectorDBManager:
    def __init__(self):
        self.collection_name = "gitlab_handbook"

        # Khởi tạo embedding model từ file embeddings.py
        self.embeddings = get_embedding_model()

        # Kết nối tới Qdrant server qua URL (Docker container)
        qdrant_url = os.getenv("QDRANT_URL", "http://localhost:6333")
        qdrant_api_key = os.getenv("QDRANT_API_KEY", None)

        self.client = QdrantClient(
            url=qdrant_url,
            api_key=qdrant_api_key,
        )
        self._ensure_collection()

    def _ensure_collection(self):
        if not self.client.collection_exists(self.collection_name):
            print(f"[*] Đang tạo mới collection: {self.collection_name}")
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=384,  # SỬA THÀNH 384 cho model MiniLM
                    distance=Distance.COSINE
                ),
            )

    def get_vector_store(self):
        return QdrantVectorStore(
            client=self.client,
            collection_name=self.collection_name,
            embedding=self.embeddings,
            
        )

    

    def add_documents(self, chunks, batch_size=50):
        """Nạp tài liệu theo từng đợt để tránh lỗi API và lỗi đệ quy"""
        # Lấy instance vector store từ hàm đã viết ở trên
        vector_store = self.get_vector_store()
        
        total_batches = (len(chunks) + batch_size - 1) // batch_size
        print(f"[*] Tổng số chunks: {len(chunks)} - Chia thành {total_batches} đợt nạp.")

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            current_batch = i // batch_size + 1
            print(f"[*] Đang nạp batch {current_batch}/{total_batches}...")
            
            # SỬA TẠI ĐÂY: Gọi hàm của vector_store, KHÔNG gọi self.add_documents
            vector_store.add_documents(batch)
            
            # Nghỉ để né hạn mức Google Free Tier
            if current_batch < total_batches:
                time.sleep(1)
        
        print("✅ Nạp dữ liệu vào Qdrant thành công!")
