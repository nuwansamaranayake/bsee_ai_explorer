"""Chat endpoint — natural language Q&A with SSE streaming.

Pipeline: user question → generate SQL → execute → synthesize answer.
Streams three phases via SSE: sql, data, answer.
"""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from services.claude_service import get_claude_service, ClaudeServiceError
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


async def _stream_chat_response(message: str) -> AsyncGenerator[str, None]:
    """Stream the chat response as SSE events.

    Phases:
    1. data: {"type": "sql", "content": "SELECT ..."}
    2. data: {"type": "data", "content": [...rows]}
    3. data: {"type": "answer", "content": "Based on..."}
    4. data: {"type": "done"}
    """
    sql_service = get_sql_service()

    try:
        result = await sql_service.answer_question(message)

        # Phase 1: SQL query (if generated)
        if result.get("sql"):
            yield f"data: {json.dumps({'type': 'sql', 'content': result['sql']})}\n\n"

        # Check if the query was refused (destructive attempt)
        if result.get("refused"):
            yield f"data: {json.dumps({'type': 'answer', 'content': result['answer']})}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
            return

        # Phase 2: Raw data
        if result.get("data"):
            yield f"data: {json.dumps({'type': 'data', 'content': result['data'][:50]})}\n\n"

        # Phase 3: AI narrative answer
        if result.get("answer"):
            yield f"data: {json.dumps({'type': 'answer', 'content': result['answer']})}\n\n"

        # Phase 4: Done
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        logger.error("Chat stream error: %s", e)
        error_msg = (
            "I encountered an error while processing your question. "
            "Please try rephrasing or ask a different question."
        )
        yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"
        yield f"data: {json.dumps({'type': 'done'})}\n\n"


@router.post("/chat")
async def chat(req: ChatRequest):
    """Natural language Q&A with SSE streaming response."""
    _check_ai_available()

    # Pydantic min_length=1 handles empty-string validation.
    # Strip whitespace for the downstream pipeline.
    message = req.message.strip()
    if not message:
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    return StreamingResponse(
        _stream_chat_response(message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
        },
    )
