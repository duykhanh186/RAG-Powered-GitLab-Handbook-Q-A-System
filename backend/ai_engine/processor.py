import os
from pathlib import Path
from tqdm import tqdm
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import MarkdownHeaderTextSplitter, RecursiveCharacterTextSplitter

# ... (giữ nguyên phần import)

class GitLabHandbookProcessor:
    def __init__(self, data_path: str):
        self.data_path = Path(data_path).resolve()
        
        self.headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
            ("###", "Header 3"),
        ]
        
        self.md_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=self.headers_to_split_on, 
            strip_headers=False
        )
        
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=150,
            separators=["\n\n", "\n", ".", " ", ""] # Ưu tiên ngắt ở đoạn văn
        )

    def process_all(self):
        print(f"--- BẮT ĐẦU XỬ LÝ DỮ LIỆU TẠI: {self.data_path} ---")
        if not self.data_path.exists():
            print(f"LỖI: Thư mục không tồn tại: {self.data_path}")
            return []

        loader = DirectoryLoader(
            str(self.data_path), 
            glob="**/*.md", 
            loader_cls=TextLoader,
            show_progress=True,
            use_multithreading=True,
            loader_kwargs={'encoding': 'utf-8'}
        )
        
        try:
            raw_docs = loader.load()
            print(f"-> Thành công: Đã nạp {len(raw_docs)} file.")
        except Exception as e:
            print(f"LỖI hệ thống khi nạp file: {e}")
            return []

        all_final_chunks = []
        
        for doc in tqdm(raw_docs, desc="Tiến độ Chunking", unit="file"):
            # Lấy source tương đối để lưu metadata cho gọn
            source_path = doc.metadata.get("source", "unknown")
            try:
                source_label = str(Path(source_path).relative_to(self.data_path.parent.parent))
            except:
                source_label = Path(source_path).name

            # Bước 1: Tách theo Header
            header_splits = self.md_splitter.split_text(doc.page_content)
            
            # Bước 2: Tách nhỏ các đoạn dài nhưng vẫn giữ Metadata của Header
            for h_split in header_splits:
                # Quan trọng: split_text của MarkdownHeaderTextSplitter trả về list Document
                # Ta cần băm nhỏ nội dung của Document đó
                sub_chunks = self.text_splitter.split_text(h_split.page_content)
                
                for content in sub_chunks:
                    # Gộp metadata từ header và source
                    new_metadata = h_split.metadata.copy()
                    new_metadata["source"] = source_label
                    
                    # Tạo đối tượng Document mới hoàn chỉnh
                    from langchain_core.documents import Document
                    all_final_chunks.append(Document(page_content=content, metadata=new_metadata))
            
        print(f"\n=== HOÀN THÀNH: {len(all_final_chunks)} chunks ===")
        return all_final_chunks

if __name__ == "__main__":
    BASE_DIR = Path(__file__).resolve().parent
    DATA_DIR = BASE_DIR.parent.parent / "data" / "handbook"
    
    processor = GitLabHandbookProcessor(str(DATA_DIR))
    final_data = processor.process_all()
    
    # GIẢ SỬ BẠN DÙNG db_manager ĐỂ LƯU
    from ai_engine.vector_db import VectorDBManager
    db_manager = VectorDBManager()
    
    # CHIA NHỎ ĐỂ NẠP (BATCHING)
    batch_size = 100  # Nạp mỗi lần 100 chunks để máy không đơ
    print(f"--- BẮT ĐẦU NẠP VÀO QDRANT ({len(final_data)} chunks) ---")
    
    for i in range(0, len(final_data), batch_size):
        batch = final_data[i : i + batch_size]
        try:
            # Đây là nơi máy sẽ chạy nặng nhất vì phải chạy Embedding Model
            db_manager.vector_store.add_documents(batch)
            print(f"✅ Đã nạp thành công: {i + len(batch)}/{len(final_data)}")
        except Exception as e:
            print(f"❌ Lỗi tại chunk {i}: {e}")
            
    print("✨ TẤT CẢ DỮ LIỆU ĐÃ ĐƯỢC NẠP THÀNH CÔNG!")
