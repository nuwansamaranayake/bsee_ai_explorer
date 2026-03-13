"""Beacon GoM API — AI Safety & Regulatory Intelligence for Offshore Operations."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start scheduler on startup, shut down on exit."""
    # Create Phase 4 tables if they don't exist
    from models.database import engine, Base
    from models.phase4_tables import AlertSummary, FederalRegisterDigest, ETLRefreshLog  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified")

    # Start scheduler
    from services.scheduler_service import get_scheduler_service
    scheduler = get_scheduler_service()
    await scheduler.start()
    logger.info("Scheduler started")

    yield

    # Shutdown scheduler
    await scheduler.shutdown()
    logger.info("Scheduler shut down")


app = FastAPI(
    title="Beacon GoM API",
    description="AI Safety & Regulatory Intelligence for Offshore Operations",
    version="0.4.0",
    lifespan=lifespan,
)

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

# Import and include routers
from routers import operators, incidents, incs, platforms, production, analyze, chat, documents, reports, metrics
from routers import regulatory, scheduler, monitoring

app.include_router(operators.router, prefix="/api", tags=["operators"])
app.include_router(incidents.router, prefix="/api", tags=["incidents"])
app.include_router(incs.router, prefix="/api", tags=["incs"])
app.include_router(platforms.router, prefix="/api", tags=["platforms"])
app.include_router(production.router, prefix="/api", tags=["production"])
app.include_router(metrics.router, prefix="/api", tags=["metrics"])
app.include_router(analyze.router, prefix="/api", tags=["analyze"])
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(documents.router, prefix="/api", tags=["documents"])
app.include_router(reports.router, prefix="/api", tags=["reports"])
# Phase 4 routers
app.include_router(regulatory.router, prefix="/api", tags=["regulatory"])
app.include_router(scheduler.router, prefix="/api", tags=["scheduler"])
app.include_router(monitoring.router, prefix="/api", tags=["monitoring"])


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

    return {
        "status": "ok",
        "service": "beacon-gom-api",
        "version": "0.4.0",
        "ai_available": claude.is_available,
        "ai_tokens_used": token_tracker.summary,
        "chromadb": chroma_status,
        "scheduler": scheduler_status,
    }
