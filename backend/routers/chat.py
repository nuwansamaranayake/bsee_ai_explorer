"""Chat endpoint — intelligent multi-query Q&A with SSE streaming.

Three-phase pipeline: PLAN → EXECUTE → ANALYZE.
Streams progress events so the frontend can show rich loading states.
"""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.claude_service import get_claude_service, ClaudeServiceError
from services.input_sanitizer import sanitize_user_input
from services.sql_service import get_sql_service, SQLServiceError
from services.prompts import SQL_REFUSAL_MESSAGE

logger = logging.getLogger(__name__)
router = APIRouter()

# Maximum input length for user messages (characters)
MAX_MESSAGE_LENGTH = 2000


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=MAX_MESSAGE_LENGTH)
    conversation_id: str | None = None  # For future multi-turn


def _check_ai_available():
    """Raise 503 if AI features are not available."""
    service = get_claude_service()
    if not service.is_available:
        raise HTTPException(
            status_code=503,
            detail={"error": "AI features are not currently available. Please try again later."},
        )


def _sse(data: dict) -> str:
    """Format a dict as an SSE data line."""
    return f"data: {json.dumps(data)}\n\n"


async def _stream_chat_response(message: str) -> AsyncGenerator[str, None]:
    """Stream the chat response as SSE events with multi-phase progress.

    Event types:
    - {"type": "phase", "phase": "planning|executing|analyzing", ...}
    - {"type": "sql", "content": "SELECT ...", "query_number": 1, "total": 2}
    - {"type": "data", "content": [...rows]}
    - {"type": "answer", "content": "Based on..."}
    - {"type": "complexity", "content": "simple|analytical|comparative"}
    - {"type": "error", "content": "..."}
    - {"type": "done"}
    """
    sql_service = get_sql_service()

    # Collect progress events emitted by the pipeline
    progress_events: list[tuple[str, dict]] = []

    def on_progress(phase: str, details: dict):
        progress_events.append((phase, details))

    try:
        # Run the three-phase pipeline with progress callback
        result = await sql_service.answer_question(message, on_progress=on_progress)

        # Stream progress events that were collected during execution
        for phase, details in progress_events:
            yield _sse({
                "type": "phase",
                "phase": phase,
                "message": details.get("message", ""),
                **{k: v for k, v in details.items() if k != "message"},
            })

        # Check if the query was refused (destructive attempt)
        if result.get("refused"):
            if result.get("answer"):
                yield _sse({"type": "answer", "content": result["answer"]})
            yield _sse({"type": "done"})
            return

        # Emit complexity level
        complexity = result.get("complexity", "simple")
        yield _sse({"type": "complexity", "content": complexity})

        # Emit SQL queries (may be multiple)
        queries = result.get("queries", [])
        for i, sql in enumerate(queries):
            yield _sse({
                "type": "sql",
                "content": sql,
                "query_number": i + 1,
                "total": len(queries),
            })

        # Emit raw data (combined from all queries)
        if result.get("data"):
            yield _sse({"type": "data", "content": result["data"][:50]})

        # Emit AI analysis answer
        if result.get("answer"):
            yield _sse({"type": "answer", "content": result["answer"]})

        # Done
        yield _sse({"type": "done"})

    except Exception as e:
        logger.error("Chat stream error: %s", e)
        error_msg = (
            "I encountered an error while processing your question. "
            "Please try rephrasing or ask a different question."
        )
        yield _sse({"type": "error", "content": error_msg})
        yield _sse({"type": "done"})


@router.post("/chat")
async def chat(req: ChatRequest):
    """Natural language Q&A with SSE streaming response."""
    _check_ai_available()

    # Pydantic min_length=1 handles empty-string validation.
    # Strip whitespace for the downstream pipeline.
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    # Sanitize input — reject prompt injection attempts
    try:
        message = sanitize_user_input(message, max_length=500, endpoint="chat")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return StreamingResponse(
        _stream_chat_response(message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
        },
    )
