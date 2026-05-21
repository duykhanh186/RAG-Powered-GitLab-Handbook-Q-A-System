#!/bin/sh
set -e

echo "=== Backend Entrypoint ==="

# Chờ Qdrant sẵn sàng
echo "[*] Đang chờ Qdrant..."
until python -c "from qdrant_client import QdrantClient; QdrantClient('${QDRANT_URL:-http://qdrant:6333}').get_collections()" 2>/dev/null; do
  echo "    Qdrant chưa sẵn sàng, thử lại sau 2s..."
  sleep 2
done
echo "[✓] Qdrant đã sẵn sàng!"

# Hàm chạy ingest ngầm
run_ingest_background() {
  # Chờ 3 giây để uvicorn khởi động xong
  sleep 3

  POINTS=$(python -c "
from qdrant_client import QdrantClient
import os
c = QdrantClient(os.getenv('QDRANT_URL', 'http://qdrant:6333'))
try:
    info = c.get_collection('gitlab_handbook')
    print(info.points_count)
except:
    print(0)
" 2>/dev/null || echo "0")

  echo "[*] Qdrant hiện có ${POINTS} points trong collection gitlab_handbook"

  if [ "$POINTS" -eq 0 ] 2>/dev/null && [ -d "/data/handbook" ]; then
    echo "[*] Chưa có data -> Bắt đầu tự động INGEST handbook ngầm..."
    python scripts/ingest_handbook.py
    echo "[✓] Ingest hoàn tất!"
  else
    echo "[✓] Đã có data hoặc không có thư mục handbook -> Bỏ qua ingest."
  fi
}

# Chạy ngầm ingest
run_ingest_background &

# Khởi động Uvicorn
echo "[*] Khởi động Backend Server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload

