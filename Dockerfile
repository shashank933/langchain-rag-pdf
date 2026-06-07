# =============================================================================
# Dockerfile for PDF RAG with DeepSeek
# =============================================================================
# Single-stage: FastAPI backend serves both the API and frontend static files.
# No nginx needed - FastAPI handles everything on a single port.
# =============================================================================

FROM python:3.11-slim

WORKDIR /app

# Copy requirements first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 10 --timeout 120 \
        --index-url https://download.pytorch.org/whl/cpu torch \
    && pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt

# Copy application code
COPY rag_pipeline.py .
COPY backend/ ./backend/

# Copy pre-built React frontend static files
COPY frontend/dist ./frontend/dist

# Expose port (FastAPI serves both API and frontend)
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')" || exit 1

# Run FastAPI directly - serves both API and frontend static files
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
