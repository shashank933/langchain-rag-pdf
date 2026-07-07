"""
FastAPI Backend for LangChain RAG with DeepSeek - PDF Question Answering.

Provides REST API endpoints for:
- Uploading and processing PDFs
- Asking questions about loaded PDFs
- Managing sessions
- LLM interaction logging to database
"""

import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlalchemy.orm import Session

# Add project root to sys.path so rag_pipeline.py can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_pipeline import RAGPipeline, GuardrailViolation

from .database import get_db, init_db
from .models import LLMLog

load_dotenv()

app = FastAPI(
    title="PDF RAG with DeepSeek API",
    description="Upload PDFs and ask questions using LangChain + DeepSeek",
    version="1.0.0",
)


@app.on_event("startup")
def on_startup():
    init_db()


def get_client_ip(request: Request) -> str:
    """
    Extract the real client IP when behind Traefik/nginx reverse proxy.

    In Docker behind Traefik:
      - X-Forwarded-For contains the original client IP as the leftmost entry
      - request.client.host will be the Docker gateway/Traefik container IP

    Priority:
      1. X-Forwarded-For (first IP, left of any comma)
      2. X-Real-IP (set by nginx)
      3. request.client.host (direct connection / fallback)
    """
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "unknown"


# CORS - allow React frontend (kept for development with Vite dev server)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- Pydantic Models ----------

class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str
    sources: list


class SourceDocument(BaseModel):
    content: str
    page: Optional[int] = None
    chunk_id: Optional[int] = None
    source: Optional[str] = None


class SessionStatus(BaseModel):
    session_id: str
    pdf_loaded: bool
    pdf_name: Optional[str] = None
    chunk_count: int = 0


class LLMLogEntry(BaseModel):
    id: int
    session_id: str
    user_question: str
    llm_answer: str
    sources_count: int
    client_ip: Optional[str] = None
    guardrail_violation: int
    created_at: str

    class Config:
        from_attributes = True


# ---------- In-memory session store ----------

sessions: Dict[str, RAGPipeline] = {}
session_info: Dict[str, dict] = {}


# ---------- API Endpoints ----------

@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.post("/api/sessions", response_model=SessionStatus)
async def create_session():
    """Create a new RAG session."""
    session_id = str(uuid.uuid4())
    sessions[session_id] = None
    session_info[session_id] = {
        "pdf_loaded": False,
        "pdf_name": None,
        "chunk_count": 0,
    }
    return SessionStatus(
        session_id=session_id,
        pdf_loaded=False,
        pdf_name=None,
        chunk_count=0,
    )


@app.get("/api/sessions/{session_id}", response_model=SessionStatus)
async def get_session(session_id: str):
    """Get session status."""
    if session_id not in session_info:
        raise HTTPException(status_code=404, detail="Session not found")
    info = session_info[session_id]
    return SessionStatus(
        session_id=session_id,
        pdf_loaded=info["pdf_loaded"],
        pdf_name=info["pdf_name"],
        chunk_count=info["chunk_count"],
    )


@app.post("/api/sessions/{session_id}/upload")
async def upload_pdf(session_id: str, file: UploadFile = File(...)):
    """Upload and process a PDF file for the given session."""
    if session_id not in session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise HTTPException(status_code=500, detail="DEEPSEEK_API_KEY not configured")

        pipeline = RAGPipeline(deepseek_api_key=api_key)
        chunk_count = pipeline.load_pdf(tmp_path)
        os.unlink(tmp_path)

        sessions[session_id] = pipeline
        session_info[session_id] = {
            "pdf_loaded": True,
            "pdf_name": file.filename,
            "chunk_count": chunk_count,
        }

        return {
            "message": f"Processed '{file.filename}' into {chunk_count} chunks",
            "chunk_count": chunk_count,
            "pdf_name": file.filename,
        }

    except HTTPException:
        raise
    except Exception as e:
        if "tmp_path" in locals():
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@app.post("/api/sessions/{session_id}/ask", response_model=AskResponse)
async def ask_question(
    session_id: str,
    ask_req: AskRequest,
    http_req: Request,
    db: Session = Depends(get_db),
):
    """
    Ask a question about the loaded PDF in the session.
    Logs LLM input, output, and client IP to the database.
    """
    if session_id not in session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    pipeline = sessions.get(session_id)
    if pipeline is None:
        raise HTTPException(
            status_code=400,
            detail="No PDF has been loaded yet. Please upload a PDF first.",
        )

    question = ask_req.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    client_ip = get_client_ip(http_req)

    try:
        result = pipeline.ask(question)
        answer = result["answer"]
        source_docs = result["source_documents"]

        sources = []
        for doc in source_docs:
            sources.append(
                SourceDocument(
                    content=doc.page_content,
                    page=doc.metadata.get("page"),
                    chunk_id=doc.metadata.get("chunk_id"),
                    source=doc.metadata.get("source"),
                )
            )

        db.add(LLMLog(
            session_id=session_id,
            user_question=question,
            llm_answer=answer,
            sources_count=len(source_docs),
            client_ip=client_ip,
            guardrail_violation=0,
        ))
        db.commit()

        return AskResponse(answer=answer, sources=[s.model_dump() for s in sources])

    except GuardrailViolation as e:
        refusal_msg = str(e)
        db.add(LLMLog(
            session_id=session_id,
            user_question=question,
            llm_answer=refusal_msg,
            sources_count=0,
            client_ip=client_ip,
            guardrail_violation=1,
        ))
        db.commit()
        return AskResponse(answer=refusal_msg, sources=[])

    except Exception as e:
        db.add(LLMLog(
            session_id=session_id,
            user_question=question,
            llm_answer=f"ERROR: {str(e)}",
            sources_count=0,
            client_ip=client_ip,
        ))
        db.commit()
        raise HTTPException(status_code=500, detail=f"Error generating answer: {str(e)}")


@app.delete("/api/sessions/{session_id}")
async def clear_session(session_id: str):
    """Clear a session and its data."""
    if session_id not in session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    pipeline = sessions.get(session_id)
    if pipeline:
        pipeline.clear()

    del sessions[session_id]
    del session_info[session_id]

    return {"message": "Session cleared"}


@app.get("/api/logs", response_model=List[LLMLogEntry])
def get_llm_logs(
    limit: int = 100,
    offset: int = 0,
    session_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    """
    Retrieve LLM interaction logs.
    Supports optional filtering by session_id and pagination.
    """
    query = db.query(LLMLog).order_by(LLMLog.created_at.desc())
    if session_id:
        query = query.filter(LLMLog.session_id == session_id)
    logs = query.offset(offset).limit(limit).all()
    return [
        LLMLogEntry(
            id=log.id,
            session_id=log.session_id,
            user_question=log.user_question,
            llm_answer=log.llm_answer,
            sources_count=log.sources_count,
            client_ip=log.client_ip,
            guardrail_violation=log.guardrail_violation,
            created_at=log.created_at.isoformat() if log.created_at else "",
        )
        for log in logs
    ]


# ---------- Frontend Static Files ----------
# Serve the built React frontend.
# Mount static assets first, then catch-all for SPA routing.
# IMPORTANT: must be defined AFTER all API routes.

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="frontend_assets")

    @app.get("/")
    async def serve_frontend_root():
        return FileResponse(str(frontend_dist / "index.html"), media_type="text/html")

    @app.get("/{full_path:path}")
    async def serve_frontend_spa(full_path: str):
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("redoc") or full_path.startswith("openapi"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(frontend_dist / "index.html"), media_type="text/html")

    print(f"[OK] Serving frontend static files from: {frontend_dist}")
else:
    print(f"[WARN] Frontend dist directory not found at: {frontend_dist}")
    print("   Run 'cd frontend && npm run build' to build the frontend.")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
