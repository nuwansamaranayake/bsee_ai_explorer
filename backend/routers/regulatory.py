"""Regulatory router — BSEE Safety Alert tracking and AI digests.

Endpoints:
    GET  /api/regulatory/alerts           — List alerts with filters
    GET  /api/regulatory/alerts/{id}      — Get full alert detail
    POST /api/regulatory/alerts/{id}/digest — Generate AI digest for an alert
    PATCH /api/regulatory/alerts/{id}/status — Update alert status
    POST /api/regulatory/scrape           — Manually trigger a scrape
    GET  /api/regulatory/stats            — Alert statistics
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/regulatory")


class StatusUpdate(BaseModel):
    status: str  # new, reviewed, dismissed


@router.get("/alerts")
async def list_alerts(
    status: str | None = Query(None, description="Filter: new, reviewed, dismissed"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """List regulatory alerts with optional status filter."""
    from services.regulatory_service import get_regulatory_service
    alerts, total = get_regulatory_service().get_alerts(status=status, limit=limit, offset=offset)
    return {
        "data": alerts,
        "meta": {"total": total, "limit": limit, "offset": offset},
    }


@router.get("/alerts/{alert_id}")
async def get_alert_detail(alert_id: int):
    """Get full detail for a single alert."""
    from services.regulatory_service import get_regulatory_service
    alert = get_regulatory_service().get_alert_detail(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"data": alert}


@router.post("/alerts/{alert_id}/digest")
async def generate_digest(alert_id: int):
    """Generate an AI digest for a specific alert."""
    from services.regulatory_service import get_regulatory_service
    result = await get_regulatory_service().generate_digest(alert_id)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"data": result}


@router.patch("/alerts/{alert_id}/status")
async def update_alert_status(alert_id: int, body: StatusUpdate):
    """Update an alert's status."""
    from services.regulatory_service import get_regulatory_service
    ok = get_regulatory_service().update_alert_status(alert_id, body.status)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid alert ID or status")
    return {"data": {"id": alert_id, "status": body.status}}


@router.post("/scrape")
async def trigger_scrape():
    """Manually trigger a BSEE Safety Alert scrape."""
    from services.regulatory_service import get_regulatory_service
    new_count = await get_regulatory_service().scrape_new_alerts()
    return {"data": {"new_alerts": new_count}}


@router.get("/stats")
async def get_alert_stats(db: Session = Depends(get_db)):
    """Get alert statistics (counts by status)."""
    from models.phase4_tables import AlertSummary
    from sqlalchemy import func

    counts = dict(
        db.query(AlertSummary.status, func.count(AlertSummary.id))
        .group_by(AlertSummary.status)
        .all()
    )
    return {
        "data": {
            "total": sum(counts.values()),
            "new": counts.get("new", 0),
            "reviewed": counts.get("reviewed", 0),
            "dismissed": counts.get("dismissed", 0),
        }
    }
