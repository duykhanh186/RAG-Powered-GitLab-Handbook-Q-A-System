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


# Khởi động Uvicorn
echo "[*] Khởi động Backend Server..."
exec uvicorn main:app --host 0.0.0.0 --port 8000 --reload

