"""
FastAPI application service for Project Atlas.
Implements endpoints:
- POST /chat
- POST /ingest
- GET /escalations
- GET /health
- POST /feedback
- GET /reports
"""
import time
import os
import logging
from typing import List, Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, Header, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.models import (
    ChatRequest, ChatResponse, IngestResponse, EscalationItem,
    FeedbackRequest, HealthResponse
)
from src.agent import agent
from src.vector_store import vector_store
from src.db import (
    get_escalations, record_feedback, get_all_reports,
    is_mysql_available, log_audit_event
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("atlas_api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event: Ingest report seed data upon startup."""
    logger.info("Initializing Project Atlas API Service...")
    seed_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "seed_data", "reports")
    chunks_indexed = vector_store.ingest_reports_directory(seed_dir)
    logger.info(f"Startup complete: {chunks_indexed} document chunks indexed.")
    yield
    logger.info("Project Atlas API Service shutting down.")


app = FastAPI(
    title="Project Atlas: Report Copilot API",
    description="Intelligent Syndicated Market Research Copilot with RAG, Entitlement Filtering, and AST Guardrails.",
    version="1.0.0",
    lifespan=lifespan
)

# Enable CORS for CodeIgniter 3 and external frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    authorization: Optional[str] = Header(None, alias="Authorization")
):
    """
    Validates API key from X-API-Key header or Authorization: Bearer token.
    Allows transparent development mode while enforcing strict authentication in production.
    """
    token = x_api_key
    if not token and authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            token = parts[1]

    # If API_KEY is set in settings, validate
    if settings.API_KEY and token != settings.API_KEY:
        # In development mode, allow localhost requests without strict key if not provided
        if settings.ENVIRONMENT == "development" and not token:
            return True
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API Key. Provide a valid 'X-API-Key' header."
        )
    return True


@app.get("/health", response_model=HealthResponse, tags=["System"])
def health_check():
    """Health check endpoint indicating database connectivity and indexed chunks."""
    db_status = "MySQL (Active)" if is_mysql_available() else "SQLite (Local Fallback)"
    return HealthResponse(
        status="healthy",
        database=db_status,
        indexed_chunks=len(vector_store.chunks),
        llm_provider=settings.LLM_PROVIDER,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    )


@app.post("/chat", response_model=ChatResponse, tags=["Copilot"])
async def chat_endpoint(
    request: ChatRequest,
    _auth: bool = Depends(verify_api_key)
):
    """
    Main Report Copilot chat endpoint.
    Performs router classification, entitlement-aware vector retrieval,
    conflict detection, CAGR projections, and fact-checking.
    """
    try:
        response = agent.process_chat(request)
        return response
    except Exception as e:
        logger.error(f"Error processing chat request: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal copilot error: {str(e)}"
        )


@app.post("/ingest", response_model=IngestResponse, tags=["Knowledge Base"])
def ingest_endpoint(
    reports_dir: Optional[str] = None,
    _auth: bool = Depends(verify_api_key)
):
    """Re-ingests all reports from the specified directory or seed data folder."""
    target_dir = reports_dir or os.path.join(os.path.dirname(os.path.dirname(__file__)), "seed_data", "reports")
    chunks = vector_store.ingest_reports_directory(target_dir)
    return IngestResponse(
        status="success",
        indexed_reports=len(set(c.report_id for c in vector_store.chunks)),
        chunks_count=chunks,
        message=f"Successfully indexed {chunks} chunks from {target_dir}"
    )


@app.get("/escalations", response_model=List[EscalationItem], tags=["Human-in-the-Loop"])
def get_escalations_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    _auth: bool = Depends(verify_api_key)
):
    """Retrieves pending analyst escalation tickets."""
    raw_escalations = get_escalations(limit=limit)
    items = []
    for r in raw_escalations:
        items.append(
            EscalationItem(
                id=r["id"],
                client_id=r["client_id"],
                question=r["question"],
                reason=r["reason"],
                confidence=float(r["confidence"]),
                status=r["status"],
                created_at=str(r.get("created_at", ""))
            )
        )
    return items


@app.post("/feedback", tags=["Feedback"])
def submit_feedback(
    feedback: FeedbackRequest,
    _auth: bool = Depends(verify_api_key)
):
    """Records thumbs-up / thumbs-down rating and comments for a conversation."""
    success = record_feedback(
        conversation_id=feedback.conversation_id,
        rating=feedback.rating,
        comments=feedback.comments
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to record feedback. Verify that conversation_id exists."
        )
    return {"status": "success", "message": "Feedback recorded."}


@app.get("/reports", tags=["Knowledge Base"])
def list_reports(_auth: bool = Depends(verify_api_key)):
    """Lists all available reports in the syndicated research catalog."""
    return get_all_reports()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.main:app", host=settings.HOST, port=settings.PORT, reload=True)
