import os
from dotenv import load_dotenv
from backend.ai_engine.processor import GitLabHandbookProcessor
from backend.ai_engine.vector_db import VectorDBManager
from backend.ai_engine.rag_chain import RAGChain

# Load API Key
load_dotenv()

def run_standalone_test():
    print("🚀 --- ĐANG CHẠY THỬ NGHIỆM ĐỘC LẬP AI ENGINE ---")
    
    # BƯỚC 1: Xử lý dữ liệu (Processor)
    # Thử nghiệm với folder handbook hiện có
    data_path = "data/handbook"
    processor = GitLabHandbookProcessor(data_path)
    
    print("[1/3] Đang băm nhỏ tài liệu...")
    chunks = processor.process_all()
    
    if not chunks:
        print("❌ Lỗi: Không tìm thấy file markdown nào trong data/handbook!")
        return

    # BƯỚC 2: Nạp vào Database (Vector DB)
    print(f"[2/3] Đang nạp {len(chunks)} chunks vào Qdrant...")
    db_manager = VectorDBManager()
    
    # Kiểm tra xem có dữ liệu chưa để tránh nạp trùng tốn API quota
    client = db_manager.client
    info = client.get_collection(db_manager.collection_name)
    
    if info.points_count == 0:
        db_manager.add_documents(chunks)
        print("✅ Đã nạp dữ liệu thành công.")
    else:
        print(f"ℹ️ Database đã có sẵn {info.points_count} chunks. Bỏ qua bước nạp.")

    # BƯỚC 3: Hỏi đáp thử nghiệm (RAG Chain)
    print("[3/3] Đang khởi tạo RAG Chain để hỏi đáp...")
    rag = RAGChain(db_manager=db_manager)  # Truyền db_manager để tránh lỗi tranh chấp file
    
    # Danh sách câu hỏi test
    queries = [
        "Giá trị cốt lõi của GitLab là gì?",
        "Quy trình remote work tại công ty như thế nào?"
    ]
    
    for q in queries:
        print(f"\n❓ Câu hỏi: {q}")
        try:
            answer, docs = rag.ask(q)
            print(f"🤖 AI trả lời: {answer}")
        except Exception as e:
            print(f"❌ Lỗi khi hỏi: {e}")

    print("\n✨ --- KẾT THÚC KIỂM TRA ---")

if __name__ == "__main__":
    run_standalone_test()