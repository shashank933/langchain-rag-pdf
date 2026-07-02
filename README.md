# SmartChat — RAG-Powered PDF Q&A with LangChain + DeepSeek

A Retrieval-Augmented Generation (RAG) application that answers questions from PDF documents using LangChain and DeepSeek LLM.

## Features

- 📄 Upload and process PDF documents
- 🔍 Semantic search with vector embeddings
- 🤖 Answers powered by DeepSeek LLM
- 💬 Interactive chat interface (React)
- 📚 Citation-grounded responses with source display

## Tech Stack

- **Backend**: FastAPI (Python)
- **Frontend**: React + Vite
- **LangChain** - Orchestration framework
- **DeepSeek** - LLM for answer generation
- **ChromaDB** - Vector store
- **HuggingFace Embeddings** - Text embeddings (all-MiniLM-L6-v2)

## Project Structure

```
langchain-rag-pdf/
├── backend/
│   └── main.py              # FastAPI backend with REST endpoints
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Main React application
│   │   ├── api.js           # API client service
│   │   ├── index.css        # Styles
│   │   └── main.jsx         # Entry point
│   ├── index.html
│   ├── vite.config.js       # Vite config with API proxy
│   └── package.json
├── rag_pipeline.py          # RAG pipeline logic (shared)
├── requirements.txt         # Python dependencies
├── Dockerfile               # Multi-stage Docker build
├── Dockerfile.backend       # Backend-only Docker build
├── docker-compose.yml       # Docker Compose configuration
├── nginx.conf               # Nginx config for production
├── .dockerignore
├── .env.example
└── README.md
```

## Setup

### Option 1: Local Development

#### Prerequisites

- Python 3.12+
- Node.js 20+

#### 1. Backend Setup

```bash
# Install Python dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env and add your DeepSeek API key

# Run the FastAPI backend
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at http://localhost:8000
API docs (Swagger UI) at http://localhost:8000/docs

#### 2. Frontend Setup

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm run dev
```

The frontend will be available at http://localhost:3000

The Vite dev server proxies `/api` requests to the backend at `http://localhost:8000`.

### Option 2: Docker Setup (Development)

```bash
# Set up environment variables
cp .env.example .env
# Edit .env and add your DeepSeek API key

# Build and run with Docker Compose
docker-compose up --build
```

This will start:
- **Backend** (FastAPI) on port 8000
- **Frontend** (React/Vite dev server) on port 3000

### Option 3: Docker Setup (Production)

```bash
# Build the multi-stage production image
docker build -t langchain-rag-pdf .

# Run the container
docker run -p 80:80 --env-file .env langchain-rag-pdf
```

This single container serves:
- The React frontend (via Nginx) on port 80
- The FastAPI backend (proxied through Nginx)

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| POST | `/api/sessions` | Create a new RAG session |
| GET | `/api/sessions/{id}` | Get session status |
| POST | `/api/sessions/{id}/upload` | Upload and process a PDF |
| POST | `/api/sessions/{id}/ask` | Ask a question about the PDF |
| DELETE | `/api/sessions/{id}` | Clear a session |

## Usage

1. Upload a PDF file using the sidebar (drag & drop or click)
2. Wait for the document to be processed and indexed
3. Ask questions about the document in the chat input
4. Get AI-powered answers with source citations
5. Click "📚 View Sources" to see the source documents used

## Environment Variables

| Variable | Description |
|----------|-------------|
| `DEEPSEEK_API_KEY` | Your DeepSeek API key (get from [platform.deepseek.com](https://platform.deepseek.com/)) |
