"""
Script nạp dữ liệu GitLab Handbook vào Qdrant (Dùng Local Embedding).
Chạy trong Docker container backend:
  docker compose exec -T backend python scripts/ingest_handbook.py
"""
import sys
import time

sys.path.insert(0, "/app")

from ai_engine.processor import GitLabHandbookProcessor
from ai_engine.vector_db import VectorDBManager

DATA_DIR = "/data/handbook"
BATCH_SIZE = 100  # Local embedding chạy offline nên có thể để batch to

def main():
    print("=" * 60)
    print("  INGEST DỮ LIỆU GITLAB HANDBOOK VÀO QDRANT")
    print("  (Sử dụng Local Embedding HuggingFace - SIÊU TỐC)")
    print("=" * 60)

    # 1. Xử lý & chunking dữ liệu
    processor = GitLabHandbookProcessor(DATA_DIR)
    chunks = processor.process_all()

    if not chunks:
        print("Không có chunks nào để ingest!")
        return

    # 2. Nạp vào Qdrant theo batch
    db_manager = VectorDBManager()
    total = len(chunks)
    successful = 0

    total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

    print(f"\n--- Bắt đầu nạp {total} chunks vào Qdrant ---")
    print(f"    Batch: {BATCH_SIZE}, Tổng số batch: {total_batches}\n")

    start_time = time.time()

    for i in range(0, total, BATCH_SIZE):
        batch = chunks[i:i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        end = min(i + BATCH_SIZE, total)

        try:
            db_manager.add_documents(batch)
            successful += len(batch)
            elapsed = time.time() - start_time
            rate = successful / elapsed if elapsed > 0 else 0
            remaining = (total - successful) / rate if rate > 0 else 0
            print(f"  [{end}/{total}] ✓ Batch {batch_num}/{total_batches} nạp thành công (~{remaining:.0f}s nữa xong)", flush=True)
        except Exception as e:
            print(f"  [{end}/{total}] ✗ LỖI ở batch {batch_num}: {str(e)[:80]}", flush=True)

    elapsed_total = time.time() - start_time
    print(f"\n{'=' * 60}")
    print(f"  HOÀN THÀNH: {successful}/{total} chunks (Mất {elapsed_total:.0f}s)")
    print(f"{'=' * 60}")

if __name__ == "__main__":
    main()
