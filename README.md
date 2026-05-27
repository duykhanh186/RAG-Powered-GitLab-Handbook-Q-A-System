# RAG Solution - Hệ thống Hỏi Đáp GitLab Handbook Microservices

Hệ thống Hỏi đáp (Q&A) thông minh dựa trên nội dung **GitLab Handbook**, sử dụng kiến trúc **RAG (Retrieval-Augmented Generation)** tiên tiến kết hợp sức mạnh của mô hình ngôn ngữ lớn (LLM) và cơ sở dữ liệu Vector. Dự án được phát triển dưới dạng **Microservices** chạy hoàn toàn trên Docker Container, tích hợp sẵn hệ thống **Admin Dashboard** quản trị chuyên sâu.

---

## Mục lục

* [Mô tả dự án](#-mô-tả-dự-án)
* [Kiến trúc hệ thống](#-kiến-trúc-hệ-thống)
* [Công nghệ sử dụng](#-công-nghệ-sử-dụng)
* [Yêu cầu hệ thống](#-yêu-cầu-hệ-thống)
* [Cài đặt & Chạy](#-cài-đặt--chạy)
* [Cấu hình biến môi trường](#-cấu-hình-biến-môi-trường)
* [Hướng dẫn sử dụng](#-hướng-dẫn-sử-dụng)
* [Cấu trúc thư mục](#-cấu-trúc-thư-mục)
* [Thành viên nhóm](#-thành-viên-nhóm)

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

![Sơ đồ kiến trúc hệ thống RAG](btl.drawio.png)
```mermaid
graph TD
    User([Người dùng / Quản trị viên]) <-->|Cổng 80| Nginx[Reverse Proxy - Nginx]
    
    %% Định tuyến Nginx
    Nginx <-->|Định tuyến /| Frontend[ReactJS SPA Frontend]
    Nginx <-->|Định tuyến /api/| Backend[FastAPI Core Backend]
    
    %% Giao tiếp Backend
    Backend <-->|Quản lý User & Lịch sử Chat| Postgres[(PostgreSQL Database)]
    Backend <-->|Cất/Tải file gốc| MinIO[(MinIO Object Storage)]
    Backend --->|Đẩy tác vụ ingestion| Redis[Redis Broker]
    Backend <-->|Truy vấn vectors tương đồng| Qdrant[(Qdrant Vector DB)]
    Backend <-->|Gọi LLM Inference| Groq[Groq API <br/> Llama-3.3-70b-versatile]

    %% Hàng đợi Celery
    Redis <--> Celery[Celery Ingestion Worker]
    Celery <-->|Lấy file gốc| MinIO
    Celery --->|Trích xuất text & chunking| ChunkProcessor[Text Chunk Processor]
    Celery --->|Embedding Generation| EmbedModel[Local HF Embedding Model <br/> paraphrase-multilingual-MiniLM-L12-v2]
    Celery --->|Lưu trữ Vectors & Metadata| Qdrant
```

---

### 2. Luồng hoạt động RAG (Retrieval-Augmented Generation)

#### Quy trình nạp dữ liệu nền (Document Ingestion Pipeline)
Quá trình xử lý tài liệu thô diễn ra bất đồng bộ thông qua Celery Worker để tránh quá tải cho API chính:

```mermaid
sequenceDiagram
    participant User as Admin UI
    participant Backend as FastAPI Backend
    participant MinIO as MinIO Storage
    participant Celery as Celery Worker
    participant DB as Qdrant Vector DB

    User->>Backend: 1. Đăng tải file tài liệu (PDF, DOCX, TXT)
    Backend->>MinIO: 2. Đẩy file gốc lưu trữ dạng Object
    Backend->>Celery: 3. Khởi tạo tác vụ Ingest bất đồng bộ
    Backend-->>User: 4. Phản hồi tải file thành công (Đang xử lý nền)
    
    rect rgb(240, 248, 255)
        Note over Celery, DB: Tiến trình Celery Background Processing
        Celery->>MinIO: 5. Đọc tải file gốc về Worker
        Celery->>Celery: 6. Cắt nhỏ văn bản (Chunk Size: 1000, Overlap: 150)
        Celery->>Celery: 7. Gọi local model sinh embeddings (384 chiều)
        Celery->>DB: 8. Lưu vector nhúng kèm metadata nguồn của file
    end
```

- **Cắt nhỏ văn bản (Chunking):** Tự động chuẩn hóa văn bản thô, cắt thành từng đoạn nhỏ tối ưu `1000` token và độ chồng lấp `150` token để giữ trọn ngữ cảnh.
- **Embedding Model:** Sử dụng mô hình cục bộ song ngữ Anh - Việt `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` thông qua thư viện `langchain_huggingface` để sinh vector nhúng 384 chiều.

#### Quy trình trả lời hỏi đáp (Retrieval & Generation Pipeline)
Luồng xử lý câu hỏi của người dùng và sinh câu trả lời dựa trên ngữ cảnh:

```mermaid
sequenceDiagram
    participant User as Client UI
    participant API as FastAPI Backend
    participant Qdrant as Qdrant DB
    participant Groq as Groq LLM (Llama 3)

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

---

### 3. Danh sách cổng kết nối (Ports Mapping)

| Thành phần Dịch vụ | Cổng ngoài (Host) | Cổng trong (Container) | Địa chỉ truy cập / Endpoint | Mô tả & Chức năng |
| :--- | :---: | :---: | :--- | :--- |
| **Nginx (Reverse Proxy)** | `80` | `80` | `http://localhost/` | **Cổng truy cập chính**. Tự động định tuyến giữa Frontend và Backend. |
| **Frontend (React)** | `3000` | `80` | `http://localhost:3000/` | Giao diện tương tác Chatbot & hệ thống quản trị Admin Dashboard. |
| **Backend (FastAPI)** | `8000` | `8000` | `http://localhost:8000/` | RESTful API dịch vụ Core, nơi điều phối dữ liệu và AI Engine. |
| **Swagger UI Docs** | `8000` | `8000` | `http://localhost:8000/docs` | Tài liệu hướng dẫn & công cụ kiểm thử API trực quan (FastAPI Docs). |
| **Qdrant Vector DB** | `6333` | `6333` | `http://localhost:6333/` | Lưu trữ vector nhúng của các mảnh văn bản tài liệu gốc. |
| **MinIO Console** | `9001` | `9001` | `http://localhost:9001/` | Web Dashboard quản lý tài liệu, file đính kèm lưu trữ dạng Object. |
| **MinIO API** | `9000` | `9000` | `http://localhost:9000/` | Cổng API Object Storage (tương thích S3) phục vụ lưu trữ file gốc. |
| **PostgreSQL Database** | `5432` | `5432` | `localhost:5432` | Hệ quản trị CSDL quan hệ lưu thông tin Người dùng & Phiên chat (Session). |
| **Redis Broker** | `6379` | `6379` | `localhost:6379` | Broker chuyển tiếp tin nhắn cho Celery Worker và làm bộ nhớ Cache. |

---

## Công nghệ sử dụng

Hệ thống được phát triển dựa trên các công nghệ hiện đại, đảm bảo tính mở rộng và khả năng chịu tải tốt:

- **Frontend (Giao diện):**
  - **ReactJS SPA (Single Page Application)** làm nền tảng phát triển giao diện.
  - **Axios** để gửi các yêu cầu HTTP không đồng bộ tới Backend.
  - **React Router (v7)** quản lý định tuyến trang (Chat client, Admin Dashboard).
  - **Vanilla CSS (Premium Styles)** tối ưu hóa trải nghiệm thị giác với giao diện Dark Mode cao cấp, hiệu ứng chuyển động mượt mà và Layout đáp ứng (Responsive).

- **Backend (Dịch vụ lõi):**
  - **FastAPI (Python):** Framework hiệu năng cực cao, hỗ trợ lập trình bất đồng bộ (`asyncio`) và tự động tạo tài liệu API Swagger.
  - **SQLAlchemy (ORM):** Quản lý, tương tác và ánh xạ cơ sở dữ liệu quan hệ PostgreSQL sang các đối tượng Python.
  - **Pydantic (v2):** Định nghĩa Schema dữ liệu và kiểm thực kiểu dữ liệu nghiêm ngặt.
  - **Celery:** Trình phân phối tác vụ nền (Task Queue) chạy bất đồng bộ để nhúng tài liệu và nạp dữ liệu nền.
  - **Uvicorn:** ASGI Web Server siêu tốc cho Python FastAPI.

- **Trí tuệ nhân tạo & RAG Engine:**
  - **LangChain & LangChain-Core:** Khung làm việc (Framework) mạnh mẽ để xây dựng các chuỗi liên kết RAG pipeline.
  - **Local Embedding Model:** `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` thông qua thư viện `langchain_huggingface` để chuyển đổi văn bản thành các vector 384 chiều, tối ưu cho đa ngôn ngữ (Anh - Việt).
  - **Qdrant Client & LangChain-Qdrant:** Thư viện tích hợp và tương tác trực tiếp với Qdrant Vector DB.
  - **Groq Cloud SDK:** Tích hợp mô hình ngôn ngữ lớn **Llama-3.3-70b-versatile** với tốc độ suy luận cực nhanh từ Groq API.
  - **File Processors:** `pypdf` để đọc tệp PDF và `python-docx` để đọc tệp Word (.docx).

- **Cơ sở dữ liệu & Lưu trữ (Databases & Storage):**
  - **PostgreSQL (15-alpine):** Lưu trữ bền vững dữ liệu quan hệ như thông tin người dùng, lịch sử phòng chat, metadata tài liệu.
  - **Qdrant Vector DB:** Hệ CSDL chuyên biệt để lưu trữ và thực hiện tìm kiếm tương đồng ngữ nghĩa trên không gian Vector 384 chiều (Cosine Similarity).
  - **MinIO Object Storage:** Hệ thống lưu trữ đối tượng dạng S3-compatible, dùng để cất giữ tài liệu thô tải lên từ trang Admin.
  - **Redis (7-alpine):** Broker tin nhắn trung gian chuyển tiếp tác vụ đến Celery Worker và làm bộ nhớ cache tăng tốc độ phản hồi.

- **Hạ tầng & Triển khai (Infrastructure):**
  - **Docker & Docker Compose:** Đóng gói toàn bộ các dịch vụ thành các container cô lập, dễ triển khai bằng một dòng lệnh duy nhất.
  - **Nginx (Alpine):** Đóng vai trò là Reverse Proxy và Load Balancer định tuyến các luồng yêu cầu mạng.

---

## Yêu cầu hệ thống

Trước khi bắt đầu cài đặt và khởi chạy dự án, hãy đảm bảo hệ thống của bạn đáp ứng các yêu cầu tối thiểu sau:

### 1. Phần mềm bắt buộc
- **Docker Desktop:** Phiên bản `20.10.x` trở lên (đã kích hoạt Docker Compose).
- **Git:** Để nhân bản (clone) mã nguồn từ repository.
- **Trình duyệt Web hiện đại:** Google Chrome, Microsoft Edge, Brave, Firefox, hoặc Safari để trải nghiệm giao diện người dùng tối ưu.

### 2. Yêu cầu phần cứng khuyến nghị
- **Hệ điều hành:** Windows 10/11 (được khuyến nghị sử dụng WSL2), macOS hoặc Linux.
- **RAM:** Tối thiểu **8 GB** (khuyến nghị **16 GB** để chạy mượt mà cùng lúc các container Database, Vector DB, Web servers và local Embedding model).
- **Bộ nhớ trống:** Tối thiểu **5 GB** dung lượng đĩa trống (để lưu trữ ảnh Docker, mô hình embedding cục bộ và dữ liệu mount).
- **Mạng:** Kết nối Internet ổn định (cần thiết cho lần chạy đầu tiên để tải các Docker images, tải model từ HuggingFace về cache, và để giao tiếp với Groq LLM API).

---

## Cài đặt & Chạy

Đảm bảo **Docker** & **Docker Desktop** đã được cài đặt và đang chạy trên thiết bị của bạn.

### Các bước triển khai chi tiết:

#### Bước 1: Clone dự án và di chuyển vào thư mục nguồn
```bash
git clone https://github.com/HoangQuocHung0605/THAI-Group-Skibidi.git
cd THAI-Group-Skibidi
```

#### Bước 2: Tạo và cấu hình tệp môi trường `.env`
Sao chép tệp cấu hình mẫu:
```bash
cp .env.example .env
```
Mở tệp `.env` vừa tạo và cập nhật các thông số bảo mật, đặc biệt là khóa **`GROQ_API_KEY`** của bạn (Bạn có thể lấy khóa này miễn phí tại [Groq Cloud Console](https://console.groq.com/)):
```env
GROQ_API_KEY=gsk_your_api_key_here
```

#### Bước 3: Triển khai các container bằng Docker Compose
Khởi chạy toàn bộ hệ thống microservices chỉ bằng một câu lệnh duy nhất:
```bash
docker compose up -d --build
```
*Lưu ý: Quá trình build lần đầu có thể mất từ 3-7 phút tùy thuộc vào tốc độ mạng của bạn để tải các Docker images và cài đặt các thư viện phụ thuộc.*

#### Bước 4: Kiểm tra trạng thái hoạt động của các container
Bạn có thể theo dõi xem các container đã chạy ổn định chưa bằng lệnh:
```bash
docker compose ps
```
Hoặc xem log hoạt động trực tiếp của hệ thống:
```bash
docker compose logs -f
```

#### Bước 5: Truy cập hệ thống trải nghiệm
Sau khi quá trình khởi chạy hoàn tất thành công, bạn có thể mở trình duyệt và truy cập các cổng dịch vụ sau:
**Giao diện Chatbot & Quản trị:** [http://localhost](http://localhost) (hoặc [http://localhost:3000](http://localhost:3000))
**Hệ thống Quản trị (Admin):** [http://localhost/admin](http://localhost/admin) (hoặc [http://localhost:3000/admin](http://localhost:3000/admin))
**Tài liệu API Swagger:** [http://localhost:8000/docs](http://localhost:8000/docs)
**Giao diện lưu trữ MinIO:** [http://localhost:9001](http://localhost:9001) (Tài khoản/Mật khẩu mặc định: `minioadmin` / `minioadmin`)

---

## Cấu hình biến môi trường

Hệ thống điều khiển toàn bộ cấu hình thông qua tệp `.env`. Dưới đây là bảng giải nghĩa chi tiết các thông số cấu hình:

| Tên biến môi trường | Giá trị mặc định | Trạng thái | Mô tả & Vai trò |
| :--- | :--- | :---: | :--- |
| **`GROQ_API_KEY`** | *Trống (Cần điền)* | **Bắt buộc** | Khóa API để gọi mô hình ngôn ngữ lớn siêu tốc Llama-3.3 từ nhà cung cấp dịch vụ Groq Cloud. |
| **`POSTGRES_DB`** | `rag_db` | Tùy chọn | Tên cơ sở dữ liệu quan hệ của hệ thống PostgreSQL. |
| **`POSTGRES_USER`** | `postgres` | Tùy chọn | Tài khoản quản trị tối cao của cơ sở dữ liệu PostgreSQL. |
| **`POSTGRES_PASSWORD`** | `postgres` | Tùy chọn | Mật khẩu truy cập cơ sở dữ liệu PostgreSQL. |
| **`QDRANT_API_KEY`** | `qdrant_key` | Tùy chọn | Khóa bảo mật API dùng để xác thực quyền đọc/ghi vào CSDL Vector Qdrant. |
| **`REDIS_PASSWORD`** | *Trống* | Tùy chọn | Mật khẩu bảo vệ của Redis (mặc định để trống trong mạng nội bộ Docker). |
| **`DATABASE_URL`** | `postgresql://postgres:postgres@postgres:5432/rag_db` | Tự động | Đường dẫn URI kết nối CSDL PostgreSQL cho SQLAlchemy ORM. |
| **`REDIS_URL`** | `redis://redis:6379` | Tự động | Đường dẫn kết nối Redis Broker cho Celery và bộ nhớ đệm cache. |
| **`REACT_APP_API_URL`** | `http://localhost:8000` | Tự động | Đường dẫn URL của API Backend để Client Frontend gọi HTTP request tới. |

---

## Hướng dẫn sử dụng

### 1. Giao diện trò chuyện thông thường (Chat Client)
- **Tạo phòng trò chuyện mới:** Truy cập trang chủ [http://localhost](http://localhost), nhấn nút **"New Chat"** ở thanh thanh Sidebar bên trái để bắt đầu một phiên chat mới.
- **Hỏi đáp thông minh:** Nhập câu hỏi liên quan đến quy trình, chính sách hoặc tài liệu của GitLab (Ví dụ: *"Chính sách làm việc từ xa của GitLab như thế nào?"* hoặc *"GitLab hướng dẫn onboarding ra sao?"*).
- **Theo dõi tài liệu tham chiếu:** Trong mỗi phản hồi từ chatbot, hệ thống sẽ hiển thị một danh sách các khối thông tin nhỏ chứa **"Nguồn tham khảo" (Sources)**. Bạn có thể nhấn vào để đọc đoạn văn gốc được trích xuất trực tiếp từ tài liệu nền làm căn cứ cho câu trả lời của AI.
- **Lịch sử trò chuyện:** Hệ thống tự động lưu trữ các đoạn hội thoại theo phiên (`session_id`). Bạn có thể quay lại bất kỳ lúc nào thông qua danh sách phòng chat cũ ở sidebar hoặc xóa phòng chat khi không còn nhu cầu sử dụng.

### 2. Giao diện Quản trị (Admin Dashboard - `/admin`)
Để vào trang quản trị, truy cập trực tiếp đường dẫn [http://localhost/admin](http://localhost/admin):

1. **Dashboard Stats (Số liệu tổng quan):**
   - Xem tổng quan các chỉ số đo lường: Tổng số thành viên đăng ký, tổng số phòng chat được tạo và tổng số vector lưu trong Qdrant.
   - Thống kê tình trạng tài liệu trong hệ thống (Đang xử lý, đã nhúng thành công, thất bại).
   - Kiểm tra trạng thái kết nối trực tiếp (Real-time Health Check) của PostgreSQL, Redis, Qdrant và dịch vụ Celery Worker.
2. **Quản lý Tài Liệu (Documents Management):**
   - **Tải lên tài liệu mới:** Kéo thả tệp PDF, DOCX, TXT vào vùng **Drag & Drop Zone**. Hệ thống sẽ ngay lập tức đẩy file lên MinIO Object Storage và tự động gửi một background task tới Celery Worker để thực thi chuỗi nạp (Chunking -> Embedding -> Vector DB).
   - **Tái lập chỉ mục (Re-index):** Nhấp chọn biểu tượng Refresh cạnh tài liệu để bắt đầu nạp lại dữ liệu trong trường hợp phát hiện lỗi nhúng hoặc muốn cập nhật nội dung.
   - **Xóa tài liệu (Delete):** Nhấn nút xóa để loại bỏ tài liệu khỏi MinIO, PostgreSQL và đồng thời xóa sạch các vector điểm tương ứng trong CSDL Vector Qdrant.
3. **Quản lý Người dùng (Users Management):**
   - Liệt kê danh sách tất cả các tài khoản người dùng có quyền truy cập hệ thống.
   - Tạo tài khoản người dùng mới, thiết lập/thay đổi vai trò của người dùng (`admin` hoặc `user`) hoặc vô hiệu hóa tài khoản.
4. **Cấu hình hệ thống (Settings Panel):**
   - Giám sát các tham số vận hành RAG: mô hình nhúng cục bộ đang chạy, độ dài mảnh cắt (`chunk_size`), khoảng chồng lấp (`chunk_overlap`) và tình trạng API Keys.

### 3. Hướng dẫn sử dụng chi tiết hệ thống REST API
Hệ thống cung cấp tài liệu API chuẩn hóa tại `/docs`. Dưới đây là các Endpoint quan trọng hỗ trợ tích hợp ngoại vi:

#### A. Nhóm API Chat & Lịch Sử
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
* **`GET /api/history/sessions`**
  - **Mục đích:** Trả về danh sách tất cả các phòng trò chuyện trước đây của người dùng.
* **`GET /api/history/`**
  - **Mục đích:** Truy xuất toàn bộ danh sách tin nhắn hội thoại cũ trong phòng chat cụ thể (truyền tham số query `session_id`).

#### B. Nhóm API Quản Trị (`/api/admin`)
* **`GET /api/admin/dashboard`**
  - **Mục đích:** Lấy trạng thái hoạt động của hạ tầng và thống kê tổng hợp số liệu.
* **`GET /api/admin/documents`**
  - **Mục đích:** Trả về danh sách toàn bộ các file tài liệu đã được tải lên kèm dung lượng, số lượng chunk cắt được và trạng thái nhúng vector.
* **`DELETE /api/admin/documents/{doc_id}`**
  - **Mục đích:** Xóa vĩnh viễn tài liệu khỏi mọi dịch vụ lưu trữ (MinIO, Postgres, Qdrant).
* **`POST /api/admin/reindex/{doc_id}`**
  - **Mục đích:** Bắt buộc Celery chạy lại luồng nhúng dữ liệu cho tệp tài liệu này.

---

## Cấu trúc thư mục

Hệ thống sử dụng cấu trúc **Monorepo** gọn gàng, rõ ràng và phân định rạch ròi trách nhiệm giữa các dịch vụ:

```text
THAI-Group-Skibidi/
├── backend/                 # FastAPI Backend & RAG Engine
│   ├── ai_engine/          # Lớp xử lý AI chuyên biệt
│   │   ├── embedding.py    # Khởi tạo mô hình nhúng cục bộ (paraphrase-multilingual)
│   │   ├── processor.py    # Cắt nhỏ văn bản (Chunking), làm sạch ký tự lạ
│   │   ├── vector_db.py    # Kết nối, tạo collection, chèn và xóa index trên Qdrant
│   │   └── rag_chain.py    # Thiết lập RAG pipeline (Lấy context + Groq Llama 3)
│   ├── app/                # FastAPI Application Core
│   │   ├── api/            # API Endpoints được gom nhóm theo logic nghiệp vụ
│   │   │   ├── admin.py    # Cổng API dành riêng cho trang quản trị Admin
│   │   │   ├── chat.py     # Cổng API chính nhận thông điệp chatbot
│   │   │   ├── history.py  # Cổng API quản trị lịch sử phiên trò chuyện
│   │   │   ├── upload.py   # API tải file gốc lên MinIO & khởi động Celery Ingest
│   │   │   └── ingest.py   # API tải file JSON Handbook định sẵn vào Qdrant
│   │   ├── core/           # Cấu hình biến môi trường, thiết lập kết nối DB, Redis, MinIO
│   │   ├── models/         # Khai báo cấu trúc bảng CSDL (PostgreSQL Models: User, Message, Document)
│   │   ├── schemas/        # Định nghĩa cấu trúc truyền nhận dữ liệu (Pydantic Models)
│   │   ├── services/       # Lớp xử lý logic nghiệp vụ phụ trợ
│   │   ├── tasks/          # Định nghĩa tác vụ nền chạy bất đồng bộ bằng Celery
│   │   └── worker/         # Khởi tạo Celery worker instance kết nối Redis
│   ├── main.py             # Điểm khởi chạy chính của dịch vụ FastAPI Backend
│   ├── requirements.txt    # Danh sách thư viện Python cần thiết
│   └── dockerfile          # Hướng dẫn đóng gói container Backend
├── frontend/               # React SPA Frontend
│   ├── public/             # Tài nguyên tĩnh công khai (logo, favicon, v.v.)
│   ├── src/                # Mã nguồn JavaScript của giao diện React
│   │   ├── components/     # Các thành phần giao diện tái sử dụng (Sidebar, Chat Window)
│   │   ├── services/       # Các hàm gọi API kết nối đến Backend qua Axios
│   │   ├── pages/          # Các trang giao diện chính
│   │   │   ├── Chat.jsx    # Trang chatbot người dùng tương tác
│   │   │   └── AdminDocuments.jsx # Giao diện Quản trị viên quản lý danh sách tài liệu
│   │   └── App.css         # CSS styling cao cấp, hiệu ứng chuyển màu
│   ├── package.json        # Định nghĩa các thư viện Node.js và scripts khởi chạy
│   └── dockerfile          # Hướng dẫn build Frontend React và chạy qua Nginx
├── nginx/                  # Cấu hình Reverse Proxy Nginx
│   └── default.conf        # Định tuyến cổng 80 cho các luồng requests (Frontend/Backend)
├── data/                   # Lưu trữ dữ liệu bền vững qua Volume Mount
│   ├── postgres/           # Cơ sở dữ liệu PostgreSQL vật lý
│   ├── qdrant/             # Cơ sở dữ liệu Qdrant Vector vật lý
│   └── minio/              # Tài liệu thô lưu trên MinIO
├── docker-compose.yml      # File điều phối toàn bộ hệ thống microservices Docker
├── .env.example            # Bản mẫu cấu hình biến môi trường
└── README.md               # Tài liệu hướng dẫn sử dụng chi tiết hệ thống
```

---

## Thành viên nhóm

Dự án được xây dựng và phát triển bởi đội ngũ thành viên **Skibidi Group**:
Hoàng Quốc Hùng 
Nguyễn Duy Khánh 24022361
Ngô Trọng Hiệp
Lương Quang Hoàng
