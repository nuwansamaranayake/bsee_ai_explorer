"""Beacon GoM API — AI Safety & Regulatory Intelligence for Offshore Operations."""

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

app = FastAPI(
    title="Beacon GoM API",
    description="AI Safety & Regulatory Intelligence for Offshore Operations",
    version="0.3.0",
)

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

    return {
        "status": "ok",
        "service": "beacon-gom-api",
        "version": "0.3.0",
        "ai_available": claude.is_available,
        "ai_tokens_used": token_tracker.summary,
        "chromadb": chroma_status,
    }
