# RAG-Powered GitLab Handbook Q&A System

> An intelligent question-answering system for the GitLab Handbook, built with **Retrieval-Augmented Generation (RAG)**, powered by LLMs and vector databases, fully containerized as microservices.

Hệ thống Hỏi & Đáp (Q&A) thông minh dựa trên nội dung **GitLab Handbook**, sử dụng kiến trúc **RAG (Retrieval-Augmented Generation)** kết hợp mô hình ngôn ngữ lớn (LLM) và cơ sở dữ liệu vector. Dự án được triển khai hoàn toàn bằng **Docker Compose** theo mô hình Microservices, tích hợp giao diện Chatbot và hệ thống Admin Dashboard toàn diện.

---

## Mục Lục

- [Tính Năng Chính](#tính-năng-chính)
- [Kiến Trúc Hệ Thống](#kiến-trúc-hệ-thống)
- [Công Nghệ Sử Dụng](#công-nghệ-sử-dụng)
- [Yêu Cầu Hệ Thống](#yêu-cầu-hệ-thống)
- [Cài Đặt & Chạy Nhanh](#cài-đặt--chạy-nhanh)
- [Cấu Hình Biến Môi Trường](#cấu-hình-biến-môi-trường)
- [Hướng Dẫn Sử Dụng](#hướng-dẫn-sử-dụng)
- [API Documentation](#api-documentation)
- [Cấu Trúc Thư Mục](#cấu-trúc-thư-mục)
- [Troubleshooting](#troubleshooting)
- [Security Considerations](#security-considerations)
- [Thành Viên Nhóm](#thành-viên-nhóm)
- [License](#license)

---

## Tính Năng Chính

- **💬 Chatbot Thông Minh**
  - Giao diện chat trực quan với phiên trò chuyện duy trì ngữ cảnh (session-based)
  - Tự động trích xuất và hiển thị nguồn tài liệu tham khảo (source attribution)
  - Hỗ trợ đa ngôn ngữ (Tiếng Anh và Tiếng Việt)

- **🛡️ Admin Dashboard Toàn Diện**
  - Dashboard thống kê: tổng người dùng, phiên chat, số vectors trong Qdrant, trạng thái tài liệu
  - Health check real-time: PostgreSQL, Redis, Qdrant, Celery Worker
  - Quản lý tài liệu: upload, re-index, xóa (dọn dẹp đồng bộ cả MinIO + Qdrant + PostgreSQL)
  - Quản lý người dùng: tạo tài khoản, phân quyền (admin/user), vô hiệu hóa tài khoản
  - Cấu hình RAG runtime: chunk size, chunk overlap, embedding model

- **⚡ Xử Lý Tài Liệu Bất Đồng Bộ**
  - Celery Worker + Redis Broker: xử lý tài liệu dung lượng lớn không chặn API
  - Chunking tự động với độ chồng lấp tối ưu (size: 1000 tokens, overlap: 150 tokens)
  - Sinh embeddings on-premises với `sentence-transformers` (không phụ thuộc API ngoài)
  - Index vector an toàn vào Qdrant Vector DB với metadata đầy đủ

---

## Kiến Trúc Hệ Thống

### Microservices Architecture

```mermaid
graph TD
    User([Người dùng / Quản trị viên]) <-->|HTTP :80| Nginx[Nginx Reverse Proxy]

    Nginx <-->|/| Frontend[ReactJS SPA<br/>Frontend :3000]
    Nginx <-->|/api/| Backend[FastAPI<br/>Backend :8000]

    Backend <-->|SQLAlchemy ORM| Postgres[(PostgreSQL 15<br/>Users · Chats · Docs)]
    Backend <-->|S3-compatible API| MinIO[(MinIO<br/>Object Storage)]
    Backend -->|Push Task| Redis[Redis 7<br/>Message Broker]
    Backend <-->|Vector Search| Qdrant[(Qdrant<br/>Vector DB)]
    Backend <-->|REST API| Groq["Groq Cloud API<br/>(Llama-3.3-70b-versatile)"]

    Redis <--> Celery[Celery Worker<br/>Ingestion Pipeline]
    Celery <-->|Download File| MinIO
    Celery -->|Parse & Clean| Processor["Text Processor<br/>(Chunking)"]
    Celery -->|Generate Embeddings| EmbedModel["sentence-transformers<br/>(paraphrase-multilingual-MiniLM-L12-v2)"]
    Celery -->|Insert Vectors| Qdrant
```

---

### Document Ingestion Pipeline

```mermaid
sequenceDiagram
    participant UI as Admin Upload UI
    participant API as FastAPI Backend
    participant S3 as MinIO Object Storage
    participant Queue as Redis Queue
    participant Worker as Celery Worker
    participant VDB as Qdrant Vector DB

    UI->>API: 1. Upload file (PDF / DOCX / TXT / MD / JSON)
    API->>S3: 2. Store raw file (UUID-prefixed object name)
    API->>Queue: 3. Enqueue ingest_document_task
    API-->>UI: 4. Return { task_id, object_name } — Processing...

    rect rgb(200, 220, 255)
        Note over Worker,VDB: Background Processing (Async)
        Worker->>S3: 5. Download file by object_name
        Worker->>Worker: 6. Parse & clean text (pypdf / python-docx)
        Worker->>Worker: 7. Chunk text (size: 1000 tokens, overlap: 150)
        Worker->>Worker: 8. Generate embeddings — 384-dim vectors
        Worker->>VDB: 9. Upsert vectors + metadata (doc_id, source, chunk_index)
        Worker-->>Queue: 10. Mark task complete, update document status → "embedded"
    end
```

**Chi tiết từng bước:**

| Bước | Module | Mô tả |
| :--: | :--- | :--- |
| Parse | `ai_engine/processor.py` | Trích xuất text từ PDF/DOCX/TXT/MD/JSON |
| Chunk | `langchain_text_splitters` | Cắt thành chunk ~1000 tokens, overlap 150 tokens để bảo toàn ngữ cảnh |
| Embed | `paraphrase-multilingual-MiniLM-L12-v2` | Sinh vector 384 chiều, hỗ trợ Anh-Việt |
| Index | `ai_engine/vector_db.py` (Qdrant) | Lưu vector + metadata vào collection để tìm kiếm cosine similarity |

---

### RAG Query Pipeline

```mermaid
sequenceDiagram
    participant User as Client UI
    participant API as FastAPI Backend
    participant VDB as Qdrant Vector DB
    participant DB as PostgreSQL
    participant LLM as Groq API

    User->>API: 1. POST /api/chat/ { message, session_id }
    API->>API: 2. Embed question → 384-dim vector
    API->>VDB: 3. Semantic search (top-k chunks, cosine similarity)
    VDB-->>API: 4. Return relevant chunks + source metadata
    API->>DB: 5. Fetch chat history (session context)
    API->>API: 6. Build prompt: [system] + [context] + [history] + [question]
    API->>LLM: 7. Call Llama-3.3-70b-versatile via Groq API
    LLM-->>API: 8. Return generated answer
    API->>DB: 9. Persist message pair to PostgreSQL
    API-->>User: 10. Response { answer, sources, session_id }
```

**Chi tiết từng bước:**

1. **Query Embedding**: Chuyển câu hỏi thành vector 384 chiều dùng cùng model lúc indexing
2. **Semantic Retrieval**: Tìm top-k chunks có cosine similarity cao nhất trong Qdrant
3. **Context Assembly**: Ghép retrieved chunks + lịch sử chat trong session + câu hỏi thành prompt
4. **LLM Inference**: Llama-3.3-70b-versatile (Groq) sinh câu trả lời dựa trên context
5. **Source Attribution**: Trả về danh sách document sources làm căn cứ cho câu trả lời

---

### Service Ports & Access Points

| Service | Host Port | Container Port | URL | Mô tả |
| :--- | :---: | :---: | :--- | :--- |
| **Nginx** | `80` | `80` | `http://localhost` | Entry point chính — route tới Frontend / Backend |
| **Frontend** | `3000` | `80` | `http://localhost:3000` | React SPA — Chatbot UI & Admin Dashboard |
| **Backend API** | `8000` | `8000` | `http://localhost:8000` | FastAPI — toàn bộ business logic |
| **API Docs (Swagger)** | `8000` | `8000` | `http://localhost:8000/docs` | Interactive API explorer |
| **Qdrant Dashboard** | `6333` | `6333` | `http://localhost:6333/dashboard` | Vector DB UI — quản lý collections |
| **MinIO Console** | `9001` | `9001` | `http://localhost:9001` | Object Storage UI — quản lý files |
| **MinIO API** | `9000` | `9000` | `http://localhost:9000` | S3-compatible API |
| **PostgreSQL** | `5432` | `5432` | `localhost:5432` | Relational DB — users, chats, documents |
| **Redis** | `6379` | `6379` | `localhost:6379` | Message broker & cache — Celery queue |

---

## Công Nghệ Sử Dụng

### Frontend
| Package | Version | Vai trò |
| :--- | :---: | :--- |
| ReactJS | 18 | UI framework |
| React Router | v7 | Client-side routing |
| Axios | Latest | HTTP client |
| CSS3 (Vanilla) | — | Responsive & Dark Mode styling |

### Backend & AI Engine
| Package | Version | Vai trò |
| :--- | :---: | :--- |
| FastAPI | 0.104.1 | Async web framework |
| Uvicorn | 0.24.0 | ASGI server |
| SQLAlchemy | 2.0.23 | ORM for PostgreSQL |
| Pydantic | ≥ 2.7.4 | Data validation & schema |
| Celery | 5.3.4 | Distributed task queue |
| python-multipart | 0.0.9 | File upload support |

### RAG Pipeline
| Package | Version | Vai trò |
| :--- | :---: | :--- |
| LangChain | 0.2.16 | RAG orchestration |
| langchain-huggingface | 0.0.3 | HuggingFace embedding integration |
| sentence-transformers | — | Local 384-dim multilingual embeddings |
| qdrant-client | 1.10.1 | Qdrant Vector DB SDK |
| groq | Latest | Groq Cloud LLM inference SDK |
| pypdf | 4.2.0 | PDF parsing |
| python-docx | 1.1.2 | DOCX parsing |

### Databases & Storage
| Service | Image | Vai trò |
| :--- | :---: | :--- |
| PostgreSQL | 15-alpine | Dữ liệu quan hệ: users, chat history, documents |
| Qdrant | latest | Vector search: 384-dim, cosine similarity |
| MinIO | latest | S3-compatible object storage cho raw files |
| Redis | 7-alpine | Message broker (Celery) & dashboard cache |

### Infrastructure
| Công nghệ | Vai trò |
| :--- | :--- |
| Docker & Docker Compose | Containerization & service orchestration |
| Nginx (alpine) | Reverse proxy & static file serving |

---

## Yêu Cầu Hệ Thống

### Phần Mềm Bắt Buộc

| Yêu cầu | Phiên bản | Ghi chú |
| :--- | :---: | :--- |
| **Docker Desktop** | 20.10+ | Bao gồm Docker Compose v2 |
| **Git** | Latest | Để clone repository |
| **Trình duyệt hiện đại** | Latest | Chrome, Edge, Firefox, Safari |
| **Groq API Key** | Required | Đăng ký miễn phí tại [console.groq.com](https://console.groq.com) |

### Phần Cứng Khuyến Nghị

| Thông số | Tối thiểu | Khuyến nghị |
| :--- | :---: | :---: |
| **RAM** | 8 GB | 16 GB |
| **Disk** | 5 GB free | 10 GB free |
| **OS** | Windows 10/11 (WSL2), macOS, Linux | — |
| **Network** | Ổn định | Cần khi lần đầu tải images (~3–5 GB) |

> **Lưu ý**: Lần chạy đầu tiên mất **5–10 phút** để tải Docker images và HuggingFace embedding model (`paraphrase-multilingual-MiniLM-L12-v2` ~470 MB). Model được cache tại `./backend_cache` để các lần chạy sau nhanh hơn.

---

## Cài Đặt & Chạy Nhanh

### Bước 1 — Clone Repository

```bash
git clone https://github.com/HoangQuocHung0605/THAI-Group-Skibidi.git
cd THAI-Group-Skibidi
```

### Bước 2 — Cấu Hình Environment Variables

```bash
# Copy file template
cp .env.example .env
```

Mở file `.env` vừa tạo và điền **Groq API Key** (bắt buộc):

```env
GROQ_API_KEY=gsk_xxxxxxxxxxxxxxxxxxxx
```

> Lấy API key miễn phí tại: [https://console.groq.com](https://console.groq.com)

### Bước 3 — Khởi Động Toàn Bộ Services

```bash
# Build images và khởi động tất cả containers ở background
docker compose up -d --build

# Theo dõi quá trình khởi động (tùy chọn)
docker compose logs -f
```

> **Lần đầu** mất khoảng 5–10 phút (tải images + embedding model). Các lần sau dưới 1 phút.

### Bước 4 — Kiểm Tra Trạng Thái Services

```bash
# Xem trạng thái tất cả containers
docker compose ps

# Kiểm tra backend health (đợi 30–60 giây sau khi start)
curl http://localhost:8000/health
# Expected: {"status": "ok"}
```

Tất cả services trạng thái `healthy` là hệ thống đã sẵn sàng.

### Bước 5 — Truy Cập Ứng Dụng

| Service | URL | Credentials mặc định |
| :--- | :--- | :--- |
| **Chatbot & Admin UI** | http://localhost | — |
| **API Docs (Swagger)** | http://localhost:8000/docs | — |
| **Qdrant Dashboard** | http://localhost:6333/dashboard | — |
| **MinIO Console** | http://localhost:9001 | `minioadmin` / `minioadmin` |

### Dừng Hệ Thống

```bash
# Dừng tất cả containers (giữ nguyên dữ liệu)
docker compose down

# Dừng và xóa toàn bộ volumes (reset dữ liệu)
docker compose down -v
```

---

## Cấu Hình Biến Môi Trường

Tạo file `.env` ở thư mục gốc (copy từ `.env.example`) với nội dung sau:

### Bảng Tham Chiếu Đầy Đủ

| Biến | Giá trị mặc định | Bắt buộc | Mô tả |
| :--- | :--- | :---: | :--- |
| `GROQ_API_KEY` | — | ✅ | API key cho Groq LLM inference ([lấy miễn phí](https://console.groq.com)) |
| `POSTGRES_DB` | `rag_db` | — | Tên database PostgreSQL |
| `POSTGRES_USER` | `postgres` | — | PostgreSQL username |
| `POSTGRES_PASSWORD` | `postgres` | — | PostgreSQL password (**thay đổi khi deploy production**) |
| `QDRANT_API_KEY` | `qdrant_key` | — | API key xác thực Qdrant |
| `MINIO_ROOT_USER` | `minioadmin` | — | MinIO admin username |
| `MINIO_ROOT_PASSWORD` | `minioadmin` | — | MinIO admin password (**thay đổi khi deploy production**) |
| `REDIS_PASSWORD` | *(trống)* | — | Redis password (không cần trong Docker internal network) |
| `DATABASE_URL` | `postgresql://postgres:postgres@postgres:5432/rag_db` | Auto | SQLAlchemy connection string (tự động từ docker-compose) |
| `REDIS_URL` | `redis://redis:6379` | Auto | Celery broker URL (tự động từ docker-compose) |
| `REACT_APP_API_URL` | `http://localhost:8000` | — | Backend API endpoint cho Frontend |

### File `.env` Đầy Đủ

```env
# ─── LLM API (BẮT BUỘC) ──────────────────────────────────────
GROQ_API_KEY=gsk_your_key_here

# ─── Database ────────────────────────────────────────────────
POSTGRES_DB=rag_db
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres

# ─── Vector DB ───────────────────────────────────────────────
QDRANT_API_KEY=qdrant_key

# ─── Object Storage ──────────────────────────────────────────
MINIO_ROOT_USER=minioadmin
MINIO_ROOT_PASSWORD=minioadmin

# ─── Auto-generated (không cần sửa khi dùng Docker Compose) ─
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/rag_db
REDIS_URL=redis://redis:6379
REACT_APP_API_URL=http://localhost:8000
```

---

## Hướng Dẫn Sử Dụng

### 1. Chatbot Interface

**Truy cập**: http://localhost hoặc http://localhost:3000

**Cách sử dụng**:
1. Nhấn **"New Chat"** trên sidebar để tạo phiên hội thoại mới
2. Gõ câu hỏi liên quan đến GitLab Handbook (ví dụ: *"What is GitLab's remote work policy?"*, *"GitLab có quy trình code review như thế nào?"*)
3. Câu trả lời hiển thị kèm danh sách **nguồn tài liệu tham chiếu** (Sources)
4. Lịch sử hội thoại được lưu tự động theo từng session

### 2. Admin Dashboard

**Truy cập**: http://localhost/admin hoặc http://localhost:3000/admin

#### Tab Dashboard
- Thống kê: tổng users, phiên chat, messages, vectors
- Service health: trạng thái PostgreSQL, Redis, Qdrant, Celery Worker
- Tình trạng pipeline: số tài liệu đã indexed / đang xử lý / thất bại

#### Tab Documents
- Upload tài liệu (kéo thả hoặc chọn file): PDF, DOCX, TXT, MD, JSON
- Xem metadata và trạng thái embedding của từng tài liệu
- Re-index tài liệu khi cần cập nhật
- Xóa tài liệu (tự động dọn dẹp đồng bộ: MinIO + Qdrant + PostgreSQL)

#### Tab Users
- Xem danh sách toàn bộ người dùng đã đăng ký
- Tạo tài khoản người dùng mới
- Phân quyền: `admin` / `user`
- Xóa tài khoản người dùng

#### Tab Settings
- Xem và chỉnh sửa cấu hình RAG: embedding model, chunk size, chunk overlap
- Kiểm tra trạng thái API keys (Groq)
- Xem thông tin Qdrant collection

### 3. Theo Dõi Background Tasks

```bash
# Xem log của Celery worker
docker compose logs celery_worker -f

# Kiểm tra các task đang chạy
docker compose exec celery_worker celery -A app.tasks.ingest_task inspect active

# Xem danh sách workers đang hoạt động
docker compose exec celery_worker celery -A app.tasks.ingest_task inspect ping
```

---

## API Documentation

Tài liệu API tương tác đầy đủ có tại: **http://localhost:8000/docs** (Swagger UI)

### Các Endpoint Chính

#### System

```http
GET /health
Response: { "status": "ok" }
```

#### Chat API

```http
POST /api/chat/
Body:    { "message": string, "session_id": string (optional) }
Response: { "answer": string, "sources": [...], "session_id": string }
```

#### History API

```http
GET /api/history/sessions?user_id={id}&limit={n}&offset={n}
Response: [ { "session_id": string, "last_message": string, "created_at": datetime } ]

GET /api/history/?session_id={id}&limit={n}&offset={n}
Response: [ { "id": int, "role": string, "content": string, "created_at": datetime } ]

DELETE /api/history/?session_id={id}
Response: { "success": bool, "message": string }
```

#### Upload API

```http
POST /api/upload/
Body:    multipart/form-data { "file": <file> }
Response: { "success": bool, "filename": string, "object_name": string, "task_id": string }

GET /api/upload/files
Response: { "files": [...], "total": int }

DELETE /api/upload/files/{object_name}
Response: { "success": bool, "message": string }
```

#### Admin API

```http
GET /api/admin/dashboard
Response: { total_users, total_conversations, total_vectors, qdrant_status, redis_status, ... }

GET /api/admin/documents
Response: { "documents": [...], "total": int }

POST /api/admin/documents
Body:    multipart/form-data { "file": <file> }
Response: { "success": bool, "filename": string, "task_id": string }

DELETE /api/admin/documents/{doc_id}
Response: { "success": bool, "message": string }

POST /api/admin/reindex/{doc_id}
Response: { "success": bool, "message": string }

GET /api/admin/users
Response: { "users": [...], "total": int }

POST /api/admin/users
Body:    { "username": string, "email": string, "role": "user"|"admin" }
Response: { "id": int, "username": string, "email": string, "role": string }

PATCH /api/admin/users/{user_id}
Body:    { "role": "user"|"admin" }
Response: { "id": int, "username": string, "role": string }

DELETE /api/admin/users/{user_id}
Response: { "success": bool, "message": string }

GET /api/admin/settings
Response: { embedding_model, chunk_size, chunk_overlap, qdrant_status, ... }

PUT /api/admin/settings
Body:    { "embedding_model": string, "chunk_size": int, "chunk_overlap": int }
Response: { "success": bool, "message": string }
```

---

## Cấu Trúc Thư Mục

```text
THAI-Group-Skibidi/
├── backend/
│   ├── ai_engine/                    # RAG pipeline core
│   │   ├── embedding.py              # HuggingFace embedding model loader (singleton)
│   │   ├── processor.py              # Text parsing & chunking logic
│   │   ├── vector_db.py              # Qdrant client wrapper
│   │   └── rag_chain.py              # LangChain RAG chain (retrieval + generation)
│   ├── app/
│   │   ├── api/                      # FastAPI route handlers
│   │   │   ├── chat.py               # POST /api/chat/
│   │   │   ├── history.py            # GET|DELETE /api/history/
│   │   │   ├── upload.py             # POST /api/upload/
│   │   │   ├── ingest.py             # POST /api/ingest/ (handbook ingestion)
│   │   │   └── admin.py              # /api/admin/* (dashboard, docs, users, settings)
│   │   ├── core/                     # App configuration & connections
│   │   │   ├── config.py             # Pydantic settings & RAG config I/O
│   │   │   ├── database.py           # SQLAlchemy engine & session factory
│   │   │   └── minio_client.py       # MinIO client & bucket initialization
│   │   ├── models/                   # SQLAlchemy ORM models
│   │   │   ├── user.py               # User model (id, username, email, role)
│   │   │   ├── message.py            # Message model (session_id, role, content)
│   │   │   └── document.py           # Document model (filename, status, chunk_count)
│   │   ├── schemas/                  # Pydantic request/response schemas
│   │   ├── services/                 # Business logic layer
│   │   │   ├── chat_service.py       # RAG query orchestration
│   │   │   ├── history_service.py    # Chat history CRUD
│   │   │   └── ingest_service.py     # Document ingestion coordination
│   │   └── tasks/                    # Celery task definitions
│   │       └── ingest_task.py        # Async document ingestion task
│   ├── main.py                       # FastAPI application entry point
│   ├── entrypoint.sh                 # Container startup script
│   ├── requirements.txt              # Python dependencies
│   └── dockerfile                    # Backend Docker image (python:3.11-slim)
├── frontend/
│   ├── src/
│   │   ├── components/               # Reusable React components
│   │   │   └── admin/                # Admin layout & shared components
│   │   ├── pages/                    # Page-level components
│   │   │   ├── AdminDashboard.jsx    # Dashboard tab
│   │   │   ├── AdminUsers.jsx        # Users management tab
│   │   │   └── ...                   # Other admin & chatbot pages
│   │   ├── services/                 # Axios API client functions
│   │   ├── App.jsx                   # Root component & routing
│   │   └── App.css                   # Global styles & dark mode
│   ├── public/
│   ├── package.json
│   └── dockerfile                    # Frontend Docker image (nginx:alpine)
├── nginx/
│   └── default.conf                  # Reverse proxy config (/ → frontend, /api/ → backend)
├── data/                             # Persistent Docker volumes (git-ignored)
│   ├── postgres/                     # PostgreSQL data files
│   ├── qdrant/                       # Qdrant vector storage
│   └── minio/                        # MinIO object files
├── backend_cache/                    # HuggingFace model cache (git-ignored)
├── docker-compose.yml                # Full service orchestration
├── .env.example                      # Environment variables template
└── README.md
```

---

## Troubleshooting

### Docker Issues

**Port đã được sử dụng**
```bash
# Windows: tìm process đang dùng port (ví dụ 8000)
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/macOS:
lsof -i :8000 && kill -9 <PID>
```

**Container không start được**
```bash
# Xem log chi tiết của service bị lỗi
docker compose logs <service_name>

# Rebuild từ đầu
docker compose down
docker compose up -d --build
```

**Hết dung lượng ổ đĩa**
```bash
# Dọn dẹp Docker (images, containers, volumes không dùng)
docker system prune -a --volumes
```

---

### Connection Issues

**Không kết nối được Backend API**
```bash
# Kiểm tra tất cả services đang chạy
docker compose ps

# Kiểm tra health endpoint
curl http://localhost:8000/health

# Đợi 30–60 giây sau khi start để backend khởi tạo hoàn toàn
```

**GROQ_API_KEY không hợp lệ**
```bash
# Kiểm tra API key còn hiệu lực
curl -H "Authorization: Bearer $GROQ_API_KEY" https://api.groq.com/openai/v1/models

# Lấy key mới tại: https://console.groq.com
```

**MinIO không kết nối được**
```bash
# Kiểm tra MinIO health
curl http://localhost:9000/minio/health/live

# Xem log MinIO
docker compose logs minio
```

---

### Performance Issues

**Embedding chậm**
- Model `paraphrase-multilingual-MiniLM-L12-v2` chạy trên CPU, tốc độ bình thường < 1 giây/chunk
- Kiểm tra cache model đã được tải: `ls ./backend_cache/`
- Nếu cache trống, lần đầu cần tải ~470 MB từ HuggingFace

**Vector search chậm**
- Kiểm tra số lượng vectors trong Qdrant: http://localhost:6333/dashboard
- Nếu collection rất lớn, cân nhắc giảm `top_k` trong cấu hình RAG

**Celery worker không nhận task**
```bash
# Restart celery worker
docker compose restart celery_worker

# Xem log worker
docker compose logs celery_worker -f
```

---

## Security Considerations

> ⚠️ **Cấu hình mặc định chỉ phù hợp cho môi trường phát triển (development). KHÔNG triển khai lên production với credentials mặc định.**

### Production Checklist

1. **Thay đổi tất cả credentials mặc định**
   ```env
   POSTGRES_PASSWORD=<strong_random_password_25+_chars>
   MINIO_ROOT_USER=<custom_username>
   MINIO_ROOT_PASSWORD=<strong_random_password>
   QDRANT_API_KEY=<strong_random_key>
   ```

2. **Bảo vệ Groq API Key**
   - Không commit file `.env` lên Git (đã có trong `.gitignore`)
   - Sử dụng secret manager trong production (AWS Secrets Manager, Vault, etc.)
   - Rotate API key định kỳ

3. **Bật HTTPS**
   - Dùng Let's Encrypt với Nginx hoặc Traefik làm reverse proxy
   - Cập nhật `REACT_APP_API_URL` sang `https://`

4. **Giới hạn quyền truy cập mạng**
   - Chỉ expose port 80/443 ra ngoài
   - Tắt các port nội bộ (5432, 6379, 6333, 9000, 9001) trong firewall
   - Sử dụng Docker internal network (đã có sẵn)

5. **Bổ sung Authentication**
   - Hiện tại API không có JWT authentication — cần thêm trước khi deploy public
   - Thêm rate limiting cho `/api/chat/` để tránh abuse
   - Bật CORS restriction (thay `allow_origins=["*"]` bằng domain cụ thể)

6. **Backup dữ liệu**
   - PostgreSQL: cấu hình `pg_dump` định kỳ
   - Qdrant vectors: backup thư mục `./data/qdrant/`
   - MinIO files: backup thư mục `./data/minio/`

### Privacy & Compliance

- Lịch sử chat được lưu trong PostgreSQL theo session
- Vector embeddings trong Qdrant không chứa nội dung text gốc (chỉ là vector số)
- Cần implement data deletion policy theo quy định (GDPR, PDPA) nếu lưu thông tin cá nhân

---

## Thành Viên Nhóm

| Thành viên | MSSV | Vai trò | Phụ trách |
| :--- | :---: | :--- | :--- |
| **Hoàng Quốc Hùng** | 24022343 | Backend Lead | FastAPI, RAG Engine, Celery Worker |
| **Nguyễn Duy Khánh** | 24022361 | Frontend Lead | React UI, Admin Dashboard |
| **Ngô Trọng Hiệp** | 24022325 | DevOps & Infrastructure | Docker, Nginx, CI/CD |
| **Lương Quang Hoàng** | 24022337 | AI/ML Engineering | Vector DB, Embeddings, RAG Optimization |

---

## Additional Resources

| Tài nguyên | Liên kết |
| :--- | :--- |
| Groq API Documentation | [console.groq.com/docs](https://console.groq.com/docs) |
| LangChain Documentation | [python.langchain.com/docs](https://python.langchain.com/docs) |
| Qdrant Documentation | [qdrant.tech/documentation](https://qdrant.tech/documentation) |
| FastAPI Documentation | [fastapi.tiangolo.com](https://fastapi.tiangolo.com) |
| sentence-transformers | [sbert.net](https://www.sbert.net) |
| React Documentation | [react.dev](https://react.dev) |

---

## License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

**Project Version**: 1.0.0 &nbsp;|&nbsp; **Last Updated**: May 2026
