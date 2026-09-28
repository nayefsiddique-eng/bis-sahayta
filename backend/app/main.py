import logging

from fastapi import FastAPI, Depends
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader

from app.routers import query, compliance, translate, voice, standards, feedback
from app.routers import chat, documents, flashcards, certification, tasks
from app.routers.chat import sessions_router
from app.core.exceptions import (
    APIException,
    api_exception_handler,
    validation_exception_handler,
    global_exception_handler,
)
from app.core.middleware import RequestTracingAndAuthMiddleware
from app.core.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Registers X-API-Key in OpenAPI so Swagger shows the Authorize button.
# Enforcement is still done by RequestTracingAndAuthMiddleware.
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

app = FastAPI(
    title="BIS Compliance & Intelligence Assistant API",
    description=(
        "Production-ready backend for BIS standards compliance, certification guidance, "
        "multilingual Q&A, OCR, RAG document retrieval, flashcards, and async task processing."
    ),
    version=settings.VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    dependencies=[Depends(api_key_scheme)],
)

# -- Exception Handlers
app.add_exception_handler(APIException, api_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, global_exception_handler)

# -- Middleware (last added = outermost)
app.add_middleware(RequestTracingAndAuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

# -- Routers (original)
app.include_router(query.router)
app.include_router(compliance.router)
app.include_router(translate.router)
app.include_router(voice.router)
app.include_router(standards.router)
app.include_router(feedback.router)

# -- Routers (new)
app.include_router(chat.router)
app.include_router(chat.router, prefix='/api', include_in_schema=False)
app.include_router(sessions_router)
app.include_router(sessions_router, prefix='/api', include_in_schema=False)
app.include_router(documents.router)
app.include_router(flashcards.router)
app.include_router(certification.router)
app.include_router(tasks.router)


# -- Health & Readiness

@app.get("/health", tags=["ops"])
def health_check():
    """Basic liveness check. Always returns 200 if the process is running."""
    return {"status": "ok", "service": "bis-compliance-backend"}


@app.get("/ready", tags=["ops"])
def readiness_check():
    """
    Readiness check - verifies that required dependencies are operational.
    Returns 200 if ready, 503 if critical dependencies are down.
    """
    checks: dict = {}
    all_ok = True

    # Compliance engine (critical - always runs)
    try:
        from app.services.compliance_engine import load_qco_data
        data = load_qco_data()
        checks["compliance_engine"] = {"status": "ok", "entries": len(data)}
    except Exception as exc:
        checks["compliance_engine"] = {"status": "error", "detail": str(exc)}
        all_ok = False

    # Session DB (critical)
    try:
        from app.services.session_db import list_sessions
        list_sessions(limit=1)
        checks["session_db"] = {"status": "ok"}
    except Exception as exc:
        checks["session_db"] = {"status": "error", "detail": str(exc)}
        all_ok = False

    # Cache (optional - degrades to in-memory)
    try:
        from app.services.cache_service import get_cache
        cache = get_cache()
        checks["cache"] = {"status": "ok", "backend": cache.backend}
    except Exception as exc:
        checks["cache"] = {"status": "degraded", "detail": str(exc)}

    # RAG / Vector store (optional)
    try:
        from app.services.rag_service import RAGService
        checks["rag"] = {
            "status": "ok" if RAGService.is_available() else "unavailable",
            "detail": "Vector store loaded" if RAGService.is_available() else "FAISS index not found",
        }
    except Exception as exc:
        checks["rag"] = {"status": "unavailable", "detail": str(exc)}

    # LLM (optional - mock always works)
    try:
        from app.services.llm_service import get_llm_provider
        provider = get_llm_provider()
        checks["llm"] = {"status": "ok", "provider": provider.name}
    except Exception as exc:
        checks["llm"] = {"status": "unavailable", "detail": str(exc)}

    # Celery (optional)
    try:
        from app.workers.celery_app import CELERY_AVAILABLE
        checks["celery"] = {"status": "ok" if CELERY_AVAILABLE else "unavailable"}
    except Exception as exc:
        checks["celery"] = {"status": "unavailable", "detail": str(exc)}

    from fastapi.responses import JSONResponse
    status_code = 200 if all_ok else 503
    return JSONResponse(
        content={"status": "ready" if all_ok else "degraded", "checks": checks},
        status_code=status_code,
    )

