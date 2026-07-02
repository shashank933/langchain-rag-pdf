"""
FastAPI Backend for LangChain RAG with DeepSeek - PDF Question Answering.

Provides REST API endpoints for:
- Uploading and processing PDFs
- Asking questions about loaded PDFs
- Managing sessions
"""

import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add project root to sys.path so rag_pipeline.py can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_pipeline import RAGPipeline, GuardrailViolation

load_dotenv()

app = FastAPI(
    title="PDF RAG with DeepSeek API",
    description="Upload PDFs and ask questions using LangChain + DeepSeek",
    version="1.0.0",
)

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

# ---------- Frontend Static Files ----------
# Serve the built React frontend.
# We mount static assets (JS, CSS, etc.) under /assets/ first,
# then use a catch-all route for SPA client-side routing.

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"

if frontend_dist.exists():
    # Mount static assets (JS, CSS, images) - these have unique filenames with hashes
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="frontend_assets")

    # Serve index.html for the root
    @app.get("/")
    async def serve_frontend_root():
        return FileResponse(str(frontend_dist / "index.html"), media_type="text/html")

    # Catch-all for SPA client-side routing (e.g., /login, /dashboard)
    # Must be defined AFTER all API routes to avoid intercepting them
    @app.get("/{full_path:path}")
    async def serve_frontend_spa(full_path: str):
        # Don't intercept API routes
        if full_path.startswith("api/") or full_path.startswith("docs") or full_path.startswith("redoc") or full_path.startswith("openapi"):
            raise HTTPException(status_code=404, detail="Not found")
        file_path = frontend_dist / full_path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        # Fallback to index.html for SPA routing
        return FileResponse(str(frontend_dist / "index.html"), media_type="text/html")

    print(f"✅ Serving frontend static files from: {frontend_dist}")
else:
    print(f"⚠️ Frontend dist directory not found at: {frontend_dist}")
    print("   Run 'cd frontend && npm run build' to build the frontend.")

# In-memory session store
# Maps session_id -> RAGPipeline instance
sessions: Dict[str, RAGPipeline] = {}
session_info: Dict[str, dict] = {}


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
    """
    Upload and process a PDF file for the given session.
    """
    if session_id not in session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    try:
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_path = tmp_file.name

        # Initialize pipeline
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500, detail="DEEPSEEK_API_KEY not configured"
            )

        pipeline = RAGPipeline(deepseek_api_key=api_key)

        # Load and index PDF
        chunk_count = pipeline.load_pdf(tmp_path)

        # Clean up temp file
        os.unlink(tmp_path)

        # Store in session
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
        # Clean up temp file if it exists
        if "tmp_path" in locals():
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


@app.post("/api/sessions/{session_id}/ask", response_model=AskResponse)
async def ask_question(session_id: str, request: AskRequest):
    """
    Ask a question about the loaded PDF in the session.
    """
    if session_id not in session_info:
        raise HTTPException(status_code=404, detail="Session not found")

    pipeline = sessions.get(session_id)
    if pipeline is None:
        raise HTTPException(
            status_code=400,
            detail="No PDF has been loaded yet. Please upload a PDF first.",
        )

    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        result = pipeline.ask(request.question)
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

        return AskResponse(answer=answer, sources=[s.model_dump() for s in sources])

    except GuardrailViolation as e:
        return AskResponse(answer=str(e), sources=[])

    except Exception as e:
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
