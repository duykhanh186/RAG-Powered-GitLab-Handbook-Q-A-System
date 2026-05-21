import os
from minio import Minio

MINIO_URL = os.getenv("MINIO_URL", "http://minio:9000").replace("http://", "")
MINIO_USER = os.getenv("MINIO_ROOT_USER", "minioadmin")
MINIO_PASSWORD = os.getenv("MINIO_ROOT_PASSWORD", "minioadmin")
BUCKET_NAME = "documents"


def get_minio_client() -> Minio:
    return Minio(
        MINIO_URL,
        access_key=MINIO_USER,
        secret_key=MINIO_PASSWORD,
        secure=False
    )


def ensure_bucket():
    client = get_minio_client()
    if not client.bucket_exists(BUCKET_NAME):
        client.make_bucket(BUCKET_NAME)
        print(f"✅ Tạo bucket: {BUCKET_NAME}")
    return client