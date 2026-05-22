# RAG Solution

## Cau Truc Du An

Toan bo du an theo cau truc Microservices:

```
rag-solution/
├── backend/                 # Backend (FastAPI + LangChain)
│   ├── app/
│   │   ├── api/            # Endpoints
│   │   ├── core/           # Config, DB, Redis
│   │   ├── models/         # SQLAlchemy Models
│   │   ├── services/       # Business Logic
│   │   └── worker/         # Celery Tasks
│   ├── ai_engine/          # AI Engine
│   ├── main.py             # Entry Point
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/               # Frontend (React)
│   ├── src/
│   │   ├── components/
│   │   ├── services/
│   │   ├── pages/
│   │   └── index.html
│   ├── nginx/
│   ├── package.json
│   └── Dockerfile
├── nginx/                  # Reverse Proxy
├── data/
│   ├── postgres/          # PostgreSQL Data
│   └── qdrant/            # Qdrant Vector DB
├── docker-compose.yml
├── .env.example
└── README.md
```

## Cac Thanh Phan

- **Backend**: FastAPI + LangChain + Celery
- **Frontend**: React
- **Database**: PostgreSQL
- **Vector DB**: Qdrant
- **Cache**: Redis
- **Reverse Proxy**: Nginx

## Cai Dat Nhanh

1. Sao chep `.env.example` thanh `.env`:
```bash
cp .env.example .env
```

2. Dien OpenAI API key vao `.env`.

3. Chay Docker Compose:
```bash
docker compose up --build
```

4. Mo trinh duyet:
- Frontend: `http://localhost:3000`
- Frontend cho admin: `http://localhost:3000/admin`
- Backend API: `http://localhost:8000`
- Health Check: `http://localhost:8000/health`

## Phat Trien

- Backend code trong `backend/app/`
- Frontend code trong `frontend/src/`
- AI Engine code trong `backend/ai_engine/`

Sau khi code xong, run `docker compose up --build` de test, roi commit va deploy.

## Cau Hinh

Chi tiet chi tiet trong `.env.example`.
