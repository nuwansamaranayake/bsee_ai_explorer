"""Beacon GoM API — AI Safety & Regulatory Intelligence for Offshore Operations."""

import logging
import os
import sys
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Startup validation — fail fast with clear messages
# ---------------------------------------------------------------------------

_REQUIRED_ENV = {
    "DATABASE_PATH": "Path to the SQLite database file",
}

_missing = [
    f"  {k}: {desc}"
    for k, desc in _REQUIRED_ENV.items()
    if not os.getenv(k)
]
if _missing:
    print("FATAL: Missing required environment variables:", file=sys.stderr)
    for m in _missing:
        print(m, file=sys.stderr)
    # Don't exit — allow container to start with defaults for dev

# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------

LOG_FORMAT = (
    '{"time":"%(asctime)s","level":"%(levelname)s","logger":"%(name)s",'
    '"message":"%(message)s"}'
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format=LOG_FORMAT,
    datefmt="%Y-%m-%dT%H:%M:%S",
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start scheduler on startup, shut down on exit."""
    try:
        # Create Phase 4 tables if they don't exist
        from models.database import engine, Base
        from models.phase4_tables import AlertSummary, FederalRegisterDigest, ETLRefreshLog  # noqa: F401
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified")
    except Exception as e:
        logger.error("Database table creation failed: %s", e)
        # Continue — app can still start, just some features may not work

    try:
        # Start scheduler
        from services.scheduler_service import get_scheduler_service
        scheduler = get_scheduler_service()
        await scheduler.start()
        logger.info("Scheduler started")
    except Exception as e:
        logger.error("Scheduler failed to start: %s", e)
        # Continue without scheduler — core API still works

    yield

    # Shutdown scheduler
    try:
        from services.scheduler_service import get_scheduler_service
        await get_scheduler_service().shutdown()
        logger.info("Scheduler shut down")
    except Exception:
        pass


# ---------------------------------------------------------------------------
# App creation
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Beacon GoM API",
    description="AI Safety & Regulatory Intelligence for Offshore Operations",
    version="0.5.0",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# Global exception handler — MUST be installed before middleware
# ---------------------------------------------------------------------------

from middleware.error_handler import install_exception_handlers
install_exception_handlers(app)

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

# Monitoring middleware (must be added before CORS)
from middleware.monitoring import MonitoringMiddleware
app.add_middleware(MonitoringMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev
        "http://localhost:3000",
        "http://localhost",
        "https://gomsafety.aigniteconsulting.ai",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

from routers import operators, incidents, incs, platforms, production, analyze, chat, documents, reports, metrics
from routers import regulatory, scheduler, monitoring, auth
from middleware.auth_middleware import get_current_user, require_admin

# Auth router — public (login, logout do NOT require a token)
app.include_router(auth.router, prefix="/api", tags=["auth"])

# Protected routers — require valid JWT token
app.include_router(operators.router, prefix="/api", tags=["operators"], dependencies=[Depends(get_current_user)])
app.include_router(incidents.router, prefix="/api", tags=["incidents"], dependencies=[Depends(get_current_user)])
app.include_router(incs.router, prefix="/api", tags=["incs"], dependencies=[Depends(get_current_user)])
app.include_router(platforms.router, prefix="/api", tags=["platforms"], dependencies=[Depends(get_current_user)])
app.include_router(production.router, prefix="/api", tags=["production"], dependencies=[Depends(get_current_user)])
app.include_router(metrics.router, prefix="/api", tags=["metrics"], dependencies=[Depends(get_current_user)])
app.include_router(analyze.router, prefix="/api", tags=["analyze"], dependencies=[Depends(get_current_user)])
app.include_router(chat.router, prefix="/api", tags=["chat"], dependencies=[Depends(get_current_user)])
app.include_router(documents.router, prefix="/api", tags=["documents"], dependencies=[Depends(get_current_user)])
app.include_router(reports.router, prefix="/api", tags=["reports"], dependencies=[Depends(get_current_user)])
# Phase 4 routers — protected
app.include_router(regulatory.router, prefix="/api", tags=["regulatory"], dependencies=[Depends(get_current_user)])
app.include_router(scheduler.router, prefix="/api", tags=["scheduler"], dependencies=[Depends(get_current_user)])
# Monitoring — admin only
app.include_router(monitoring.router, prefix="/api", tags=["monitoring"], dependencies=[Depends(require_admin)])


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
async def health_check():
    """Health check with AI availability status and token usage."""
    from services.claude_service import get_claude_service, token_tracker

    claude = get_claude_service()

    # ChromaDB status
    chroma_status = {"available": False, "chunks": 0}
    try:
        from services.rag_service import get_rag_service
        rag = get_rag_service()
        chroma_status = {
            "available": True,
            "chunks": rag.collection.count(),
        }
    except Exception:
        pass

    # Scheduler status
    scheduler_status = None
    try:
        from services.scheduler_service import get_scheduler_service
        scheduler_status = get_scheduler_service().get_job_status()
    except Exception:
        pass

    # Database status
    db_status = {"available": False}
    try:
        from models.database import engine
        with engine.connect() as conn:
            conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = {"available": True}
    except Exception:
        pass

    return {
        "status": "ok",
        "service": "beacon-gom-api",
        "version": "0.5.0",
        "ai_available": claude.is_available,
        "ai_tokens_used": token_tracker.summary,
        "chromadb": chroma_status,
        "database": db_status,
        "scheduler": scheduler_status,
    }
