"""Document intelligence endpoints — RAG search over BSEE documents."""

import logging

from fastapi import APIRouter, HTTPException

from models.schemas import DocumentSearchRequest
from services.claude_service import get_claude_service, ClaudeServiceError, token_tracker
from services.input_sanitizer import sanitize_user_input
from services.rag_service import get_rag_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/documents/search")
async def search_documents(req: DocumentSearchRequest):
    """RAG search — semantic search over BSEE documents with AI synthesis."""
    # Check AI availability
    claude = get_claude_service()
    if not claude.is_available:
        raise HTTPException(
            status_code=503,
            detail={"error": "AI features are not currently available. Please try again later."},
        )

    rag = get_rag_service()

    # Check corpus is not empty
    if rag.collection.count() == 0:
        raise HTTPException(
            status_code=404,
            detail={"error": "No documents have been indexed yet. The document corpus is being prepared."},
        )

    # Sanitize query — reject prompt injection attempts
    try:
        clean_query = sanitize_user_input(req.query, max_length=300, endpoint="documents")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        result = await rag.search(
            query=clean_query,
            top_k=req.top_k,
            doc_type=req.doc_type,
        )
    except ValueError as e:
        # sanitize_user_input inside rag.search may also raise
        raise HTTPException(status_code=400, detail=str(e))
    except ClaudeServiceError as e:
        logger.error("Document search AI error: %s", e)
        raise HTTPException(
            status_code=502,
            detail={"error": "Document search temporarily unavailable. Please try again."},
        )

    return {
        "data": result,
        "meta": {"status": "ok", "tokens_used": token_tracker.summary},
    }


@router.get("/documents/stats")
async def get_document_stats():
    """Corpus statistics — document counts and date range."""
    rag = get_rag_service()
    stats = rag.get_stats()
    return {"data": stats}
