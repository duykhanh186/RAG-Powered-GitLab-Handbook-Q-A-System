# Configuration module
# HIEPviet lai Config
from pydantic_settings import BaseSettings
from functools import lru_cache
 
 
class Settings(BaseSettings):
    # App
    APP_NAME: str = "RAG Solution"
    DEBUG: bool = False
 
    # PostgreSQL
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@postgres:5432/rag_db"
 
    # Redis
    REDIS_URL: str = "redis://redis:6379"
 
    # Celery (dùng Redis làm broker)
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"
 
    # Qdrant
    QDRANT_URL: str = "http://qdrant:6333"
    QDRANT_COLLECTION: str = "documents"
 
    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-3.5-turbo"
    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # Google Gemini
    GOOGLE_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-latest"
    GOOGLE_EMBEDDING_MODEL: str = "models/gemini-embedding-001"

    # Groq
    GROQ_API_KEY: str = ""
 
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
 
 
@lru_cache()
def get_settings() -> Settings:
    return Settings()
 
 
settings = get_settings()


# Dynamic RAG Settings Helper Functions
import os
import json

SETTINGS_FILE = "/data/rag_settings.json"

def read_rag_settings():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
                return {
                    "chunk_size": data.get("chunk_size", 512),
                    "chunk_overlap": data.get("chunk_overlap", 50),
                    "embedding_model": data.get("embedding_model", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
                }
        except Exception:
            pass
    return {
        "chunk_size": 512,
        "chunk_overlap": 50,
        "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    }

def save_rag_settings(chunk_size: int, chunk_overlap: int, embedding_model: str = None):
    try:
        os.makedirs(os.path.dirname(SETTINGS_FILE), exist_ok=True)
        data = {
            "chunk_size": chunk_size,
            "chunk_overlap": chunk_overlap,
            "embedding_model": embedding_model or "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        }
        with open(SETTINGS_FILE, "w") as f:
            json.dump(data, f, indent=4)
        return True
    except Exception as e:
        print(f"Lỗi khi ghi tệp cấu hình RAG: {e}")
        return False