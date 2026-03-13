"""Monitoring router — system health, token usage, endpoint stats, errors.

Endpoints:
    GET /api/monitoring/health      — System health snapshot
    GET /api/monitoring/tokens      — Token usage summary (today + 7-day trend)
    GET /api/monitoring/endpoints   — Per-route response time percentiles
    GET /api/monitoring/errors      — Recent errors by endpoint
"""

import logging

from fastapi import APIRouter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/monitoring")


@router.get("/health")
async def get_system_health():
    """System health snapshot: uptime, DB size, ChromaDB, memory."""
    from services.monitoring_service import get_monitoring_service
    monitoring = get_monitoring_service()

    health = monitoring.get_system_health()

    # Add scheduler status if available
    try:
        from services.scheduler_service import get_scheduler_service
        scheduler = get_scheduler_service()
        health["scheduler"] = scheduler.get_job_status()
    except Exception:
        health["scheduler"] = None

    return {"data": health}


@router.get("/tokens")
async def get_token_usage():
    """Token usage: today's totals, 7-day trend, per-endpoint breakdown."""
    from services.monitoring_service import get_monitoring_service
    return {"data": get_monitoring_service().get_token_summary()}


@router.get("/endpoints")
async def get_endpoint_stats():
    """Per-route response time percentiles (P50/P95/P99) and error rates."""
    from services.monitoring_service import get_monitoring_service
    return {"data": get_monitoring_service().get_endpoint_stats()}


@router.get("/errors")
async def get_recent_errors():
    """Recent errors grouped by endpoint and type."""
    from services.monitoring_service import get_monitoring_service
    return {"data": get_monitoring_service().get_recent_errors()}
