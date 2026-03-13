"""FastAPI middleware for automatic request timing and error tracking.

Wraps every request to record duration and status code in MonitoringService.
Excludes /health and /docs endpoints to avoid noise.
"""

import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger(__name__)

# Paths to exclude from monitoring (high-frequency, low-value, or streaming)
EXCLUDED_PATHS = {"/health", "/docs", "/openapi.json", "/redoc", "/favicon.ico"}
# Prefixes to exclude (SSE streaming endpoints that conflict with BaseHTTPMiddleware buffering)
EXCLUDED_PREFIXES = ("/api/analyze/stream", "/api/chat/stream")


class MonitoringMiddleware(BaseHTTPMiddleware):
    """Automatically records request timing and errors for all API endpoints."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Skip excluded paths and streaming endpoints
        if path in EXCLUDED_PATHS or path.startswith(EXCLUDED_PREFIXES):
            return await call_next(request)

        from services.monitoring_service import get_monitoring_service
        monitoring = get_monitoring_service()

        start = time.perf_counter()
        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start) * 1000
            monitoring.record_request(
                method=request.method,
                path=path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            return response
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            monitoring.record_request(
                method=request.method,
                path=path,
                status_code=500,
                duration_ms=duration_ms,
            )
            monitoring.record_error(
                method=request.method,
                path=path,
                error_type=type(exc).__name__,
            )
            raise
