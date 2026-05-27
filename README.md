# RAG-Powered GitLab Handbook Q&A System

> An intelligent question-answering system for the GitLab Handbook, built with **Retrieval-Augmented Generation (RAG)**, powered by LLMs and vector databases, fully containerized as microservices.

Hệ thống Hỏi & Đáp (Q&A) thông minh dựa trên nội dung **GitLab Handbook**, sử dụng kiến trúc **RAG (Retrieval-Augmented Generation)** kết hợp mô hình ngôn ngữ lớn (LLM) và cơ sở dữ liệu vector. Dự án được triển khai hoàn toàn bằng **Docker Compose** theo mô hình Microservices, tích hợp giao diện Chatbot và hệ thống Admin Dashboard toàn diện.

---

## Mục Lục

* [Mô tả dự án](#-mô-tả-dự-án)
* [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
* [Công nghệ sử dụng](#-công-nghệ-sử-dụng)
* [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
* [Cài đặt & Chạy](#-cài-đặt--chạy)
* [Cấu hình biến môi trường](#-cấu-hình-biến-môi-trường)
* [Lược đồ cơ sở dữ liệu](#-lược-đồ-cơ-sở-dữ-liệu-database-schema)
* [Hướng dẫn sử dụng](#-hướng-dẫn-sử-dụng)
* [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
* [Thành viên nhóm](#-thành-viên-nhóm)
* [Xử lý sự cố thường gặp](#-xử-lý-sự-cố-thường-gặp-troubleshooting)

---

## Mô tả dự án

**RAG Solution - GitLab Handbook Q&A Chatbot** là một giải pháp toàn diện cho phép người dùng đặt câu hỏi và tra cứu thông tin nhanh chóng từ cuốn sổ tay hướng dẫn khổng lồ của GitLab (GitLab Handbook). Hệ thống giải quyết bài toán quá tải thông tin bằng cách kết hợp cơ chế tìm kiếm ngữ nghĩa thông minh và mô hình tạo ngôn ngữ tự nhiên.

### Các tính năng cốt lõi:
- **Trò chuyện thông minh (AI Chatbot):** Giao diện chat trực quan, hỗ trợ duy trì ngữ cảnh phòng trò chuyện (Session-based) và trích xuất nguồn tài liệu tham khảo chính xác (Sources Reference).
- **Hệ thống Quản trị chuyên sâu (Admin Dashboard):** Theo dõi hiệu năng hệ thống, quản lý tài liệu (Tải lên, nhúng vector, xóa tài liệu), quản lý người dùng & phân quyền, và cấu hình hệ thống.
- **Nạp dữ liệu nền bất đồng bộ (Asynchronous Ingestion Pipeline):** Xử lý tài liệu dung lượng lớn (PDF, DOCX, TXT) thông qua hàng đợi Celery Worker, trích xuất văn bản, sinh Embedding và index dữ liệu an toàn mà không làm nghẽn dịch vụ chính.

---

## Kiến trúc hệ thống

Hệ thống được thiết kế theo mô hình **Microservices** phân tách độc lập, giao tiếp thông qua mạng nội bộ Docker và được định tuyến tập trung bởi Reverse Proxy **Nginx**.

### 1. Sơ đồ kiến trúc tổng quan

Dưới đây là sơ đồ chi tiết luồng giao tiếp giữa các thành phần dịch vụ trong hệ thống:

![Sơ đồ kiến trúc hệ thống RAG](So_do_kien_truc.png)
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

    User->>Backend: 1. Đăng tải file tài liệu (PDF, DOCX, TXT)
    Backend->>MinIO: 2. Đẩy file gốc lưu trữ dạng Object
    Backend->>Celery: 3. Khởi tạo tác vụ Ingest bất đồng bộ
    Backend-->>User: 4. Phản hồi tải file thành công (Đang xử lý nền)
    rect rgb(240, 248, 255)
        Note over Celery, DB: Tiến trình Celery Background Processing
        Celery->>MinIO: 5. Đọc tải file gốc về Worker
        Celery->>Celery: 6. Cắt nhỏ văn bản (Theo Chunk Size & Overlap từ cấu hình RAG động)
        Celery->>Celery: 7. Gọi local model sinh embeddings (384 chiều)
        Celery->>DB: 8. Lưu vector nhúng kèm metadata nguồn của file
    end
```

- **Cắt nhỏ văn bản (Chunking):** Chuẩn hóa văn bản thô và cắt thành các đoạn nhỏ. Các tham số **Chunk Size** (Độ dài đoạn văn) và **Chunk Overlap** (Độ chồng lấp) được quản lý và cấu hình linh động trực tiếp từ trang quản trị **Admin Settings** (giá trị mặc định tối ưu lần lượt là `1000` và `150` ký tự/token) giúp bảo toàn ngữ cảnh tốt nhất cho từng loại tài liệu.
- **Embedding Model:** Sử dụng mô hình cục bộ song ngữ Anh - Việt `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` thông qua thư viện `langchain_huggingface` để sinh vector nhúng 384 chiều.
- **Query Condensation:** Trước khi tìm kiếm, hệ thống sử dụng LLM để chuyển đổi câu hỏi tiếp nối (follow-up) thành câu hỏi độc lập dựa trên lịch sử hội thoại (tối đa 5 lượt gần nhất), giúp truy vấn Vector DB chính xác hơn.
- **Off-Topic Detection:** Hệ thống tự động nhận diện câu hỏi ngoài phạm vi GitLab Handbook (lời chào, kiến thức chung) bằng tiền tố `[OFFTOPIC]` và phản hồi lịch sự mà không đính kèm nguồn tài liệu.

#### Quy trình trả lời hỏi đáp (Retrieval & Generation Pipeline)
Luồng xử lý câu hỏi của người dùng và sinh câu trả lời dựa trên ngữ cảnh:

```mermaid
sequenceDiagram
    participant User as Client UI
    participant API as FastAPI Backend
    participant VDB as Qdrant Vector DB
    participant DB as PostgreSQL
    participant LLM as Groq API

    User->>API: 1. Gửi câu hỏi kèm session_id
    API->>API: 2. Nhúng câu hỏi thành vector biểu diễn ngữ nghĩa
    API->>Qdrant: 3. So khớp tìm kiếm vector tương đồng (Cosine Similarity)
    Qdrant-->>API: 4. Trả về top K đoạn văn liên quan nhất
    API->>API: 5. Lấy lịch sử hội thoại cũ trong CSDL PostgreSQL
    API->>API: 6. Gộp ngữ cảnh (Context) + Lịch sử + Câu hỏi thành Prompt tối ưu
    API->>Groq: 7. Gửi Prompt yêu cầu sinh câu trả lời
    Groq-->>API: 8. Trả về nội dung câu trả lời
    API-->>User: 9. Trả về câu trả lời + Các nguồn tài liệu tham chiếu (Sources)
```

- **Top-K Retrieval:** Truy vấn tìm kiếm `8` đoạn văn bản tương đồng nhất (Cosine Similarity) từ Qdrant Vector DB để xây dựng ngữ cảnh.
- **Conversational Memory:** Hệ thống giữ tối đa `10` lượt hội thoại gần nhất trong prompt để đảm bảo tính nhất quán khi trả lời các câu hỏi tiếp nối.

---

### 3. Danh sách cổng kết nối (Ports Mapping)

| Thành phần Dịch vụ | Cổng ngoài (Host) | Cổng trong (Container) | Địa chỉ truy cập / Endpoint | Mô tả & Chức năng |
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
docker compose down
```

#### Bước 5: Truy cập hệ thống trải nghiệm
Sau khi quá trình khởi chạy hoàn tất thành công, bạn có thể mở trình duyệt và truy cập các cổng dịch vụ sau:

| Dịch vụ | Địa chỉ truy cập | Ghi chú |
| :--- | :--- | :--- |
| **Giao diện Chatbot** | [http://localhost](http://localhost) hoặc [http://localhost:3000](http://localhost:3000) | Trang chủ hỏi đáp AI |
| **Admin Dashboard** | [http://localhost/admin](http://localhost/admin) | Quản trị hệ thống (Dashboard, Tài liệu, Users, Settings) |
| **Swagger API Docs** | [http://localhost:8000/docs](http://localhost:8000/docs) | Tài liệu & kiểm thử API tương tác |
| **MinIO Console** | [http://localhost:9001](http://localhost:9001) | Quản lý file Object Storage (TK: `minioadmin` / MK: `minioadmin`) |
| **Qdrant Dashboard** | [http://localhost:6333/dashboard](http://localhost:6333/dashboard) | Quản lý Vector DB trực quan |

#### Bước 6: Dừng hệ thống
Khi cần tắt toàn bộ hệ thống:
```bash
docker compose down
```
Nếu muốn xóa sạch dữ liệu và volumes để cài lại từ đầu:
```bash
docker compose down -v
```

---

## Cấu Hình Biến Môi Trường

Hệ thống điều khiển toàn bộ cấu hình thông qua tệp `.env`. Dưới đây là bảng giải nghĩa chi tiết các thông số cấu hình:

### Biến cần cấu hình thủ công

| Biến | Giá trị mặc định | Bắt buộc | Mô tả |
| :--- | :--- | :---: | :--- |
| **`GROQ_API_KEY`** | *Trống (Cần điền)* | **Bắt buộc** | Khóa API để gọi mô hình ngôn ngữ lớn siêu tốc Llama-3.3-70b-versatile từ nhà cung cấp dịch vụ [Groq Cloud](https://console.groq.com/). |
| **`POSTGRES_DB`** | `rag_db` | Tùy chọn | Tên cơ sở dữ liệu quan hệ của hệ thống PostgreSQL. |
| **`POSTGRES_USER`** | `postgres` | Tùy chọn | Tài khoản quản trị tối cao của cơ sở dữ liệu PostgreSQL. |
| **`POSTGRES_PASSWORD`** | `postgres` | Tùy chọn | Mật khẩu truy cập cơ sở dữ liệu PostgreSQL. |
| **`QDRANT_API_KEY`** | `qdrant_key` | Tùy chọn | Khóa bảo mật API dùng để xác thực quyền đọc/ghi vào CSDL Vector Qdrant. |
| **`MINIO_ROOT_USER`** | `minioadmin` | Tùy chọn | Tài khoản đăng nhập vào MinIO Object Storage Console. |
| **`MINIO_ROOT_PASSWORD`** | `minioadmin` | Tùy chọn | Mật khẩu đăng nhập MinIO Object Storage Console. |
| **`REDIS_PASSWORD`** | *Trống* | Tùy chọn | Mật khẩu bảo vệ của Redis (mặc định để trống trong mạng nội bộ Docker). |

### Biến tự động sinh bởi Docker Compose

| Tên biến môi trường | Giá trị mặc định | Mô tả & Vai trò |
| :--- | :--- | :--- |
| **`DATABASE_URL`** | `postgresql://postgres:postgres@postgres:5432/rag_db` | Đường dẫn URI kết nối CSDL PostgreSQL cho SQLAlchemy ORM. |
| **`REDIS_URL`** | `redis://redis:6379` | Đường dẫn kết nối Redis Broker cho Celery và bộ nhớ đệm cache. |
| **`QDRANT_URL`** | `http://qdrant:6333` | Đường dẫn kết nối Qdrant Vector DB trong mạng nội bộ Docker. |
| **`MINIO_URL`** | `http://minio:9000` | Đường dẫn kết nối MinIO Object Storage API trong mạng Docker. |
| **`REACT_APP_API_URL`** | `http://localhost:8000` | Đường dẫn URL của API Backend để Client Frontend gọi HTTP request tới. |
| **`OPENAI_API_KEY`** | `sk-placeholder-key` | Khóa API OpenAI (dự phòng, hiện không sử dụng chính). |
| **`GOOGLE_API_KEY`** | *Trống* | Khóa API Google Gemini (dự phòng, hiện không sử dụng chính). |

---

## Hướng Dẫn Sử Dụng

### 1. Giao diện trò chuyện thông thường (Chat Client)
- **Tạo phòng trò chuyện mới:** Truy cập trang chủ [http://localhost](http://localhost), nhấn nút **"Đoạn chat mới"** ở thanh Sidebar bên trái để bắt đầu một phiên chat mới.
- **Hỏi đáp thông minh:** Nhập câu hỏi liên quan đến quy trình, chính sách hoặc tài liệu của GitLab (Ví dụ: *"Chính sách làm việc từ xa của GitLab như thế nào?"* hoặc *"GitLab hướng dẫn onboarding ra sao?"*).
- **Theo dõi tài liệu tham chiếu:** Trong mỗi phản hồi từ chatbot, hệ thống sẽ hiển thị một danh sách các khối thông tin nhỏ chứa **"Nguồn tham khảo" (Sources)**. Bạn có thể nhấn vào để đọc đoạn văn gốc được trích xuất trực tiếp từ tài liệu nền làm căn cứ cho câu trả lời của AI. *Lưu ý: Với câu hỏi ngoài phạm vi GitLab Handbook (câu chào, kiến thức chung), hệ thống sẽ tự động ẩn nguồn tham khảo.*
- **Lịch sử trò chuyện:** Hệ thống tự động lưu trữ các đoạn hội thoại theo phiên (`session_id`) trên trình duyệt (LocalStorage). Bạn có thể quay lại bất kỳ lúc nào thông qua danh sách phòng chat cũ ở sidebar, tìm kiếm, đổi tên, hoặc xóa phòng chat khi không còn nhu cầu sử dụng.
- **Chế độ Sáng/Tối (Light/Dark Mode):** Nhấn nút chuyển đổi giao diện ở cuối sidebar để thay đổi giữa chế độ sáng ☀️ và tối 🌙.

### 2. Giao diện Quản trị (Admin Dashboard - `/admin`)
Để vào trang quản trị, truy cập trực tiếp đường dẫn [http://localhost/admin](http://localhost/admin). Trang Admin có 4 module chính truy cập qua thanh điều hướng bên trái:

1. **Dashboard Stats (`/admin/dashboard`) — Số liệu tổng quan:**
   - Xem tổng quan các chỉ số đo lường: Tổng số thành viên đăng ký, tổng số phòng chat được tạo, tổng số tin nhắn và tổng số vector lưu trong Qdrant.
   - Thống kê tình trạng tài liệu trong hệ thống (Đang xử lý, đã nhúng thành công, thất bại).
   - Kiểm tra trạng thái kết nối trực tiếp (Real-time Health Check) của PostgreSQL, Redis, Qdrant và dịch vụ Celery Worker.
2. **Quản lý Tài Liệu (`/admin/documents`) — Documents Management:**
   - **Tải lên tài liệu mới:** Kéo thả tệp vào vùng **Drag & Drop Zone**. Định dạng được hỗ trợ: `.json`, `.txt`, `.md`, `.pdf`, `.docx`. Hệ thống sẽ ngay lập tức đẩy file lên MinIO Object Storage và tự động gửi một background task tới Celery Worker để thực thi chuỗi nạp (Chunking → Embedding → Vector DB).
   - **Tái lập chỉ mục (Re-index):** Nhấp chọn biểu tượng Refresh cạnh tài liệu để bắt đầu nạp lại dữ liệu trong trường hợp phát hiện lỗi nhúng hoặc muốn cập nhật nội dung.
   - **Xóa tài liệu (Delete):** Nhấn nút xóa để loại bỏ tài liệu khỏi **cả 3 nơi lưu trữ** đồng thời: MinIO (file gốc), PostgreSQL (metadata) và Qdrant (vector nhúng).
3. **Quản lý Người dùng (`/admin/users`) — Users Management:**
   - Liệt kê danh sách tất cả các tài khoản người dùng có quyền truy cập hệ thống.
   - Tạo tài khoản người dùng mới (yêu cầu `username` và `email` duy nhất).
   - Thiết lập/thay đổi vai trò của người dùng (`admin` hoặc `user`).
   - Xóa tài khoản người dùng khỏi hệ thống.
4. **Cấu hình hệ thống (`/admin/settings`) — Settings Panel:**
   - Giám sát và tùy chỉnh các tham số vận hành RAG: mô hình nhúng cục bộ đang chạy, độ dài mảnh cắt (`chunk_size`), khoảng chồng lấp (`chunk_overlap`).
   - **Cơ chế ràng buộc dữ liệu (Validation Rules):**
     * **Chunk Size:** Cho phép cấu hình từ `100` đến `5000` ký tự.
     * **Chunk Overlap:** Cho phép cấu hình từ `0` đến `chunk_size - 1` (bắt buộc phải nhỏ hơn `chunk_size` để đảm bảo logic cắt đoạn).
     * Cả Frontend và Backend đều thực hiện xác thực (validation) chặt chẽ, hiển thị thông báo lỗi rõ ràng nếu nhập sai quy chuẩn.
   - **Tác động của thay đổi:** Các thay đổi sẽ được lưu lập tức vào `rag_settings.json` và tự động áp dụng cho các tài liệu được nạp/tái lập chỉ mục (Re-index) sau thời điểm lưu cấu hình. (Lưu ý: Đối với tài liệu cũ đã nhúng trước đó, quản trị viên cần nhấn nút **Tái lập chỉ mục** để áp dụng cấu hình mới).
   - Theo dõi tình trạng kết nối của các API Keys (Groq, OpenAI).
   - Kiểm tra trạng thái hệ thống (Qdrant, Redis, Celery, Database).
   - Lưu cấu hình RAG vào file `rag_settings.json` (persistent qua Docker volume).

### 3. Định dạng tài liệu được hỗ trợ

| Định dạng | Phần mở rộng | Thư viện xử lý | Mô tả |
| :--- | :---: | :--- | :--- |
| **JSON** | `.json` | Python `json` | Dữ liệu GitLab Handbook có cấu trúc |
| **Plain Text** | `.txt` | Python built-in | Tệp văn bản thuần |
| **Markdown** | `.md` | Python built-in | Tài liệu Markdown |
| **PDF** | `.pdf` | `pypdf` v4.2 | Tệp PDF (trích xuất text từ tất cả trang) |
| **Word Document** | `.docx` | `python-docx` v1.1 | Tệp Microsoft Word |

### 4. Hướng dẫn sử dụng chi tiết hệ thống REST API
Hệ thống cung cấp tài liệu API chuẩn hóa tự động tại [http://localhost:8000/docs](http://localhost:8000/docs). Dưới đây là danh sách đầy đủ các Endpoint hỗ trợ tích hợp ngoại vi:

#### A. API Hệ thống (System)
* **`GET /health`** — Kiểm tra trạng thái hoạt động nhanh của Backend.
* **`GET /`** — Trang chào mừng mặc định, xác nhận Backend đang chạy.

#### B. Nhóm API Chat & Lịch Sử (`/api/chat`, `/api/history`)
* **`POST /api/chat/`**
  - **Mục đích:** Gửi câu hỏi và nhận câu trả lời từ RAG.
  - **Payload mẫu:**
    ```json
    {
      "message": "GitLab Onboarding quy định những gì?",
      "session_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    }
    ```
  - **Response mẫu:**
    ```json
    {
      "answer": "Theo GitLab Handbook, quy trình onboarding bao gồm...",
      "sources": [
        {
          "document_name": "gitlab_onboarding.pdf",
          "content": "Quy trình onboarding của GitLab bắt đầu từ ngày đầu tiên..."
        }
      ]
    }
    ```
* **`GET /api/history/sessions`** — Trả về danh sách tất cả các phòng trò chuyện trước đây (hỗ trợ tham số `limit`, `offset`, `user_id`).
* **`GET /api/history/?session_id=<id>`** — Truy xuất toàn bộ danh sách tin nhắn hội thoại cũ trong phòng chat cụ thể.
* **`DELETE /api/history/?session_id=<id>`** — Xóa lịch sử trò chuyện (theo phiên cụ thể hoặc toàn bộ nếu không truyền `session_id`).

#### C. Nhóm API Upload File (`/api/upload`)
* **`POST /api/upload/`** — Tải file tài liệu lên MinIO và tự động khởi tạo Celery ingest task bất đồng bộ. Trả về `task_id` để theo dõi tiến trình.
* **`GET /api/upload/files`** — Liệt kê tất cả file đang lưu trữ trong MinIO Object Storage.
* **`DELETE /api/upload/files/{object_name}`** — Xóa file khỏi MinIO và xóa các vectors tương ứng trong Qdrant.

#### D. Nhóm API Ingest (`/api/ingest`)
* **`POST /api/ingest/`** — Nạp trực tiếp file JSON Handbook vào Qdrant (chỉ chấp nhận `.json`).
* **`GET /api/ingest/status`** — Kiểm tra trạng thái Qdrant và đếm tổng số chunk đã nhúng.

#### E. Nhóm API Quản Trị (`/api/admin`)
* **`GET /api/admin/dashboard`** — Lấy trạng thái hoạt động hạ tầng và thống kê tổng hợp (users, conversations, messages, vectors, documents).
* **`GET /api/admin/documents`** — Danh sách tài liệu đã tải lên kèm dung lượng, số chunk và trạng thái nhúng.
* **`POST /api/admin/documents`** — Tải file tài liệu lên và xử lý nhúng trực tiếp (JSON, TXT, MD, PDF, DOCX).
* **`DELETE /api/admin/documents/{doc_id}`** — Xóa vĩnh viễn tài liệu khỏi mọi dịch vụ lưu trữ (MinIO + Postgres + Qdrant).
* **`POST /api/admin/reindex/{doc_id}`** — Bắt buộc Celery chạy lại luồng nhúng dữ liệu cho tệp tài liệu này.
* **`GET /api/admin/users`** — Danh sách toàn bộ tài khoản người dùng.
* **`POST /api/admin/users`** — Tạo tài khoản người dùng mới (body: `username`, `email`, `role`).
* **`PATCH /api/admin/users/{user_id}`** — Cập nhật vai trò người dùng (body: `role`).
* **`DELETE /api/admin/users/{user_id}`** — Xóa tài khoản người dùng.
* **`GET /api/admin/settings`** — Lấy cấu hình RAG hiện tại và trạng thái hệ thống.
* **`PUT /api/admin/settings`** — Cập nhật cấu hình RAG (body: `chunk_size`, `chunk_overlap`, `embedding_model`).

---

## Lược đồ cơ sở dữ liệu (Database Schema)

Hệ thống sử dụng **PostgreSQL** để lưu trữ dữ liệu quan hệ với 3 bảng chính:

```mermaid
erDiagram
    users {
        int id PK "Khóa chính, tự tăng"
        varchar username UK "Tên đăng nhập (duy nhất)"
        varchar email UK "Email (duy nhất)"
        varchar role "Vai trò: admin | user"
        timestamptz created_at "Thời điểm tạo tài khoản"
    }

    messages {
        int id PK "Khóa chính, tự tăng"
        text question "Nội dung câu hỏi của người dùng"
        text answer "Nội dung câu trả lời từ AI"
        text sources "JSON array nguồn tài liệu tham khảo"
        varchar session_id "ID phiên trò chuyện (nhóm chat)"
        int user_id FK "Liên kết tới bảng users"
        timestamptz created_at "Thời điểm gửi tin nhắn"
    }

    documents {
        int id PK "Khóa chính, tự tăng"
        varchar filename "Tên file gốc tải lên"
        varchar minio_object_name "Tên object trong MinIO Storage"
        int file_size "Dung lượng file (bytes)"
        int chunk_count "Số lượng chunk đã cắt"
        varchar status "Trạng thái: processing | embedded | failed"
        timestamptz created_at "Thời điểm tải file lên"
    }

    users ||--o{ messages : "has many"
```

---

## Cấu trúc thư mục

Hệ thống sử dụng cấu trúc **Monorepo** gọn gàng, rõ ràng và phân định rạch ròi trách nhiệm giữa các dịch vụ:

```text
THAI-Group-Skibidi/
├── backend/                          # FastAPI Backend & RAG Engine
│   ├── ai_engine/                   # Lớp xử lý AI chuyên biệt
│   │   ├── __init__.py              # Khởi tạo module ai_engine
│   │   ├── embedding.py             # Khởi tạo mô hình nhúng cục bộ (paraphrase-multilingual)
│   │   ├── processor.py             # Cắt nhỏ văn bản (Chunking), làm sạch ký tự lạ
│   │   ├── rag_chain.py             # Thiết lập RAG pipeline (Lấy context + Groq Llama 3)
│   │   └── vector_db.py             # Kết nối, tạo collection, chèn và xóa index trên Qdrant
│   ├── app/                         # FastAPI Application Core
│   │   ├── api/                     # API Endpoints được gom nhóm theo logic nghiệp vụ
│   │   │   ├── __init__.py          # Đăng ký và gom nhóm các API Router
│   │   │   ├── admin.py             # Cổng API dành riêng cho trang quản trị Admin
│   │   │   ├── chat.py              # Cổng API chính nhận thông điệp chatbot
│   │   │   ├── history.py           # Cổng API quản trị lịch sử phiên trò chuyện
│   │   │   ├── ingest.py            # API tải file JSON Handbook định sẵn vào Qdrant
│   │   │   └── upload.py            # API tải file gốc lên MinIO & khởi động Celery Ingest
│   │   ├── core/                    # Cấu hình hệ thống & kết nối hạ tầng
│   │   │   ├── __init__.py          # Khởi tạo module core
│   │   │   ├── celery_app.py        # Khởi tạo Celery App instance kết nối Redis Broker
│   │   │   ├── config.py            # Đọc & quản lý biến môi trường (.env) bằng Pydantic Settings
│   │   │   ├── database.py          # Thiết lập kết nối SQLAlchemy Engine & SessionLocal tới PostgreSQL
│   │   │   └── minio_client.py      # Khởi tạo MinIO Client kết nối Object Storage
│   │   ├── models/                  # Khai báo cấu trúc bảng CSDL (SQLAlchemy ORM Models)
│   │   │   ├── __init__.py          # Export các model: User, Message, Document
│   │   │   ├── document.py          # Model bảng Document (metadata tài liệu tải lên)
│   │   │   ├── message.py           # Model bảng Message (tin nhắn hội thoại chat)
│   │   │   └── user.py              # Model bảng User (thông tin người dùng & phân quyền)
│   │   ├── schemas/                 # Định nghĩa cấu trúc truyền nhận dữ liệu (Pydantic Schemas)
│   │   │   ├── __init__.py          # Export các schema dùng chung
│   │   │   ├── chat.py              # Schema request/response cho API Chat
│   │   │   ├── ingest.py            # Schema request/response cho API Ingest
│   │   │   └── message.py           # Schema request/response cho Message & History
│   │   ├── services/                # Lớp xử lý logic nghiệp vụ phụ trợ (Business Logic)
│   │   │   ├── __init__.py          # Export các service classes
│   │   │   ├── chat_service.py      # Xử lý logic hỏi đáp: nhúng câu hỏi, gọi RAG, lưu lịch sử
│   │   │   ├── history_service.py   # Truy vấn & quản lý lịch sử phiên trò chuyện
│   │   │   └── ingest_service.py    # Xử lý logic nạp tài liệu: đọc file, chunk, nhúng vector
│   │   ├── tasks/                   # Định nghĩa tác vụ nền chạy bất đồng bộ bằng Celery
│   │   │   └── ingest_task.py       # Celery Task xử lý pipeline nạp tài liệu nền
│   │   └── worker/                  # Khởi tạo Celery Worker instance
│   │       ├── __init__.py          # Khởi tạo module worker
│   │       ├── database.py          # Session DB riêng cho worker process (tách biệt khỏi API)
│   │       └── tasks.py             # Đăng ký & định nghĩa các Celery tasks cho worker
│   ├── documents/                   # Thư mục chứa tài liệu mẫu hướng dẫn
│   │   └── guide.txt               # Hướng dẫn sử dụng cơ bản
│   ├── scripts/                     # Scripts tiện ích cho Backend
│   │   └── ingest_handbook.py       # Script nạp dữ liệu Handbook ban đầu vào Vector DB
│   ├── temp_celery_uploads/         # Thư mục tạm cho Celery Worker tải file xử lý
│   ├── temp_uploads/                # Thư mục tạm cho API upload file
│   ├── .dockerignore                # Loại trừ file không cần thiết khi build Docker image
│   ├── dockerfile                   # Hướng dẫn đóng gói container Backend
│   ├── entrypoint.sh                # Script khởi chạy container (migration DB + start server)
│   ├── main.py                      # Điểm khởi chạy chính của dịch vụ FastAPI Backend
│   ├── migrate_add_session.py       # Script migration bổ sung cột session vào CSDL
│   └── requirements.txt             # Danh sách thư viện Python cần thiết
│
├── frontend/                         # React SPA Frontend
│   ├── nginx/                       # Cấu hình Nginx riêng cho Frontend container
│   │   └── default.conf             # Định tuyến SPA (fallback về index.html cho React Router)
│   ├── public/                      # Tài nguyên tĩnh công khai
│   │   └── index.html               # Template HTML gốc cho React mount
│   ├── src/                         # Mã nguồn JavaScript của giao diện React
│   │   ├── components/              # Các thành phần giao diện tái sử dụng
│   │   │   ├── Chat.jsx             # Component Chat Window chính (hiển thị tin nhắn)
│   │   │   └── admin/               # Các component dùng chung cho Admin Dashboard
│   │   │       ├── AdminLayout.jsx  # Layout khung chính trang Admin (Sidebar + Content)
│   │   │       ├── ConfirmModal.jsx # Modal xác nhận hành động nguy hiểm (Xóa, Vô hiệu hóa)
│   │   │       └── StatusBadge.jsx  # Badge hiển thị trạng thái (Online/Offline/Processing)
│   │   ├── pages/                   # Các trang giao diện chính
│   │   │   ├── AdminDashboard.jsx   # Trang tổng quan thống kê Admin Dashboard
│   │   │   ├── AdminDocuments.jsx   # Trang quản lý tài liệu (Upload, Re-index, Delete)
│   │   │   ├── AdminSettings.jsx    # Trang cấu hình hệ thống RAG
│   │   │   ├── AdminUsers.jsx       # Trang quản lý người dùng & phân quyền
│   │   │   ├── Chat.jsx             # Trang chatbot người dùng tương tác
│   │   │   └── Dashboard.jsx        # Trang Dashboard tổng quan cho người dùng thường
│   │   ├── services/                # Các hàm gọi API kết nối đến Backend
│   │   │   └── api.js               # Axios instance & các hàm gọi RESTful API
│   │   ├── App.css                  # CSS styling cao cấp, hiệu ứng chuyển màu & Dark Mode
│   │   ├── App.jsx                  # Component gốc React, cấu hình Router & Layout chính
│   │   ├── index.html               # HTML entry point (Vite/Webpack)
│   │   └── index.js                 # Điểm khởi chạy React (ReactDOM.render)
│   ├── .dockerignore                # Loại trừ node_modules khi build Docker image
│   ├── dockerfile                   # Hướng dẫn build Frontend React và phục vụ qua Nginx
│   ├── index.html                   # HTML entry point chính (Vite root)
│   ├── package.json                 # Định nghĩa các thư viện Node.js và scripts khởi chạy
│   └── package-lock.json            # Khóa phiên bản chính xác các thư viện phụ thuộc
│
├── nginx/                            # Cấu hình Reverse Proxy Nginx (Gateway chính)
│   └── default.conf                 # Định tuyến cổng 80: / → Frontend, /api/ → Backend
│
├── data/                             # Lưu trữ dữ liệu bền vững qua Docker Volume Mount
│   ├── handbook/                    # Dữ liệu GitLab Handbook gốc (Markdown)
│   │   ├── _index.md               # Trang mục lục chính Handbook
│   │   ├── roadmap.md              # Lộ trình phát triển GitLab
│   │   ├── about/                  # Thông tin giới thiệu về GitLab
│   │   ├── communication/          # Quy tắc giao tiếp nội bộ
│   │   ├── company/                # Thông tin công ty & cấu trúc tổ chức
│   │   ├── finance/                # Chính sách tài chính
│   │   ├── hiring/                 # Quy trình tuyển dụng
│   │   ├── security/               # Chính sách bảo mật
│   │   ├── total-rewards/          # Chế độ đãi ngộ & phúc lợi
│   │   └── values/                 # Giá trị cốt lõi của GitLab
│   ├── minio/                      # Dữ liệu MinIO Object Storage (Docker Volume)
│   ├── postgres/                   # Dữ liệu PostgreSQL (Docker Volume)
│   ├── qdrant/                     # Dữ liệu Qdrant Vector DB (Docker Volume)
│   └── rag_settings.json           # File cấu hình tham số RAG (chunk_size, overlap, model)
│
├── backend_cache/                    # Cache mô hình HuggingFace Embedding (Docker Volume)
│   └── huggingface/                 # Thư mục cache model sentence-transformers
│
├── scripts/                          # Scripts tiện ích cấp dự án (dự phòng mở rộng)
│
├── .env                              # File biến môi trường thực tế (không commit lên Git)
├── .env.example                      # Bản mẫu cấu hình biến môi trường
├── .gitignore                        # Quy tắc loại trừ file khỏi Git version control
├── btl.drawio.png                    # Sơ đồ kiến trúc hệ thống (draw.io export)
├── docker-compose.yml                # File điều phối toàn bộ hệ thống microservices Docker
└── README.md                         # Tài liệu hướng dẫn sử dụng chi tiết hệ thống
```

---

## Thành viên nhóm

Dự án được xây dựng và phát triển bởi đội ngũ thành viên **Skibidi Group**:

| STT | Họ và tên sinh viên | Mã số sinh viên |
| :---: | :--- | :---: |
| 1 | Hoàng Quốc Hùng | 24022343 |
| 2 | Nguyễn Duy Khánh | 24022361 |
| 3 | Ngô Trọng Hiệp | 24022325 |
| 4 | Lương Quang Hoàng | 24022337 |

---

## Xử lý sự cố thường gặp (Troubleshooting)

| Vấn đề | Nguyên nhân | Cách khắc phục |
| :--- | :--- | :--- |
| Container `backend` khởi động chậm hoặc restart liên tục | Lần đầu cần tải mô hình Embedding (~100MB) từ HuggingFace | Đợi 2-3 phút, kiểm tra log: `docker compose logs -f backend` |
| Lỗi `GROQ_API_KEY` khi chat | Chưa cấu hình khóa API Groq | Điền `GROQ_API_KEY` trong file `.env` và restart: `docker compose restart backend` |
| Chatbot trả lời "Không tìm thấy tài liệu liên quan" | Chưa nạp dữ liệu Handbook vào Vector DB | Vào Admin → Documents → Tải lên file tài liệu `.json`, `.pdf`, `.docx` |
| Frontend hiển thị lỗi kết nối API | Backend chưa khởi động xong hoặc Nginx chưa sẵn sàng | Kiểm tra: `docker compose ps`, đảm bảo tất cả services đều `healthy` |
| MinIO Console không truy cập được | Container MinIO chưa khởi động | Kiểm tra: `docker compose logs minio`, đảm bảo port `9001` không bị chiếm |
| Port `80` bị chiếm bởi ứng dụng khác | Nginx không thể bind port 80 | Tắt ứng dụng chiếm port hoặc đổi port trong `docker-compose.yml` |
| Lỗi `psycopg2` hoặc Database connection | PostgreSQL chưa sẵn sàng | Backend có healthcheck tự chờ Postgres, nếu vẫn lỗi: `docker compose restart backend` |
