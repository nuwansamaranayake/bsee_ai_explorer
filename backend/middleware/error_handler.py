"""Global exception handler middleware — catches ALL unhandled exceptions
and translates them into user-friendly JSON responses.

RULE: No Python tracebacks, file paths, class names, or internal variable
names EVER appear in an API response. Those details stay in server logs.
"""

import logging
import sqlite3
import traceback
import uuid

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# User-friendly error message mapping
# ---------------------------------------------------------------------------

_FRIENDLY_MESSAGES: dict[type, tuple[int, str]] = {}


def _register_errors() -> None:
    """Register exception types → (status_code, user_friendly_message).

    Called lazily so imports don't fail at module load time.
    """
    global _FRIENDLY_MESSAGES

    _FRIENDLY_MESSAGES[sqlite3.OperationalError] = (
        503, "Data service temporarily unavailable. Please retry in a moment."
    )
    _FRIENDLY_MESSAGES[sqlite3.DatabaseError] = (
        503, "Data service temporarily unavailable."
    )
    _FRIENDLY_MESSAGES[FileNotFoundError] = (
        404, "Requested resource not found."
    )
    _FRIENDLY_MESSAGES[ValueError] = (
        400, "Please check your input and try again."
    )
    _FRIENDLY_MESSAGES[PermissionError] = (
        403, "Access denied."
    )
    _FRIENDLY_MESSAGES[TimeoutError] = (
        504, "Request timed out. Please try again."
    )
    _FRIENDLY_MESSAGES[ConnectionError] = (
        503, "External service unavailable. Please retry in a moment."
    )
    _FRIENDLY_MESSAGES[ConnectionRefusedError] = (
        503, "External service unavailable."
    )

    # Try to register AI-specific errors
    try:
        from openai import RateLimitError, APIConnectionError, APIError, AuthenticationError, APITimeoutError
        _FRIENDLY_MESSAGES[RateLimitError] = (
            503, "AI analysis is temporarily busy — please retry in a moment."
        )
        _FRIENDLY_MESSAGES[APITimeoutError] = (
            504, "Analysis is taking longer than expected — please try again."
        )
        _FRIENDLY_MESSAGES[AuthenticationError] = (
            503, "AI service configuration error. Please contact support."
        )
        _FRIENDLY_MESSAGES[APIConnectionError] = (
            503, "Unable to reach AI service. Please try again shortly."
        )
        _FRIENDLY_MESSAGES[APIError] = (
            502, "AI service returned an error. Please try again."
        )
    except ImportError:
        pass

    # Try to register httpx errors
    try:
        import httpx
        _FRIENDLY_MESSAGES[httpx.ConnectError] = (
            503, "External service unavailable."
        )
        _FRIENDLY_MESSAGES[httpx.TimeoutException] = (
            504, "External request timed out. Please try again."
        )
    except ImportError:
        pass

    # ClaudeServiceError
    try:
        from services.claude_service import ClaudeServiceError
        _FRIENDLY_MESSAGES[ClaudeServiceError] = (
            502, "AI analysis failed. Please try again."
        )
    except ImportError:
        pass

    # SQLServiceError
    try:
        from services.sql_service import SQLServiceError
        _FRIENDLY_MESSAGES[SQLServiceError] = (
            400, "Unable to process that query. Please try rephrasing."
        )
    except ImportError:
        pass


_errors_registered = False


def _ensure_errors_registered() -> None:
    global _errors_registered
    if not _errors_registered:
        _register_errors()
        _errors_registered = True


def _get_friendly_message(exc: Exception) -> tuple[int, str]:
    """Look up a user-friendly message for the exception type."""
    _ensure_errors_registered()

    exc_type = type(exc)

    # Direct match
    if exc_type in _FRIENDLY_MESSAGES:
        return _FRIENDLY_MESSAGES[exc_type]

    # Check MRO (parent classes)
    for cls in exc_type.__mro__:
        if cls in _FRIENDLY_MESSAGES:
            return _FRIENDLY_MESSAGES[cls]

    # ClaudeServiceError has its own message field
    if hasattr(exc, 'error_type') and hasattr(exc, 'message'):
        return 502, str(exc.message)

    # Catch-all
    return 500, "Something unexpected happened. Please try again or contact support."


# ---------------------------------------------------------------------------
# Install exception handlers on the FastAPI app
# ---------------------------------------------------------------------------

def install_exception_handlers(app: FastAPI) -> None:
    """Register global exception handlers on the FastAPI application.

    This catches:
    1. HTTPException (FastAPI) — sanitize detail field
    2. StarletteHTTPException — same
    3. ValidationError (Pydantic) — friendly message
    4. All other exceptions — log + return friendly message
    """

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Handle HTTPException — sanitize the detail field."""
        # If detail is a dict with our expected shape, use it
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": exc.detail["error"],
                    "status": exc.status_code,
                },
            )

        # If detail is a string, use it (it's already user-facing from our code)
        if isinstance(exc.detail, str):
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "error": exc.detail,
                    "status": exc.status_code,
                },
            )

        # Fallback
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": "Request could not be processed.",
                "status": exc.status_code,
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        """Catch-all for any unhandled exception.

        - Log full traceback server-side
        - Return a clean, user-friendly JSON response
        - NEVER expose internal details
        """
        error_id = str(uuid.uuid4())[:8]
        status_code, friendly_msg = _get_friendly_message(exc)

        # Log full details server-side for debugging
        logger.error(
            "Unhandled exception [%s] %s %s | type=%s | message=%s",
            error_id,
            request.method,
            request.url.path,
            type(exc).__name__,
            str(exc)[:500],
            exc_info=True,
        )

        return JSONResponse(
            status_code=status_code,
            content={
                "error": friendly_msg,
                "status": status_code,
                "ref": error_id,
            },
        )

    # Handle Pydantic validation errors (direct)
    try:
        from pydantic import ValidationError

        @app.exception_handler(ValidationError)
        async def validation_exception_handler(request: Request, exc: ValidationError) -> JSONResponse:
            logger.warning(
                "Validation error on %s %s: %s",
                request.method, request.url.path, str(exc)[:300],
            )
            return JSONResponse(
                status_code=422,
                content={
                    "error": "Please check your input and try again.",
                    "status": 422,
                },
            )
    except ImportError:
        pass

    # Handle FastAPI RequestValidationError (from request body/params parsing).
    # We return a user-friendly message plus the field-level detail so the
    # frontend can highlight specific invalid fields.
    try:
        from fastapi.exceptions import RequestValidationError

        @app.exception_handler(RequestValidationError)
        async def request_validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
            # Build a concise list of field errors for the frontend
            field_errors = []
            for err in exc.errors():
                loc = " → ".join(str(l) for l in err.get("loc", []) if l != "body")
                field_errors.append(f"{loc}: {err.get('msg', 'invalid')}")

            logger.warning(
                "Request validation error on %s %s: %s",
                request.method, request.url.path, "; ".join(field_errors)[:300],
            )
            return JSONResponse(
                status_code=422,
                content={
                    "error": "Please check your input and try again.",
                    "status": 422,
                    "fields": field_errors,
                },
            )
    except ImportError:
        pass
