"""Scheduler router — job status, execution history, manual triggers.

Endpoints:
    GET  /api/scheduler/status          — All job statuses (next run, state)
    GET  /api/scheduler/history         — Paginated etl_refresh_log entries
    POST /api/scheduler/trigger/{job_id} — Manually trigger a specific job
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from models.database import get_db
from models.phase4_tables import ETLRefreshLog

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scheduler")


@router.get("/status")
async def get_scheduler_status():
    """All registered jobs with their next run time and state."""
    from services.scheduler_service import get_scheduler_service
    scheduler = get_scheduler_service()

    jobs = scheduler.get_job_status()

    # Enrich with last run info
    for job in jobs:
        last_run = scheduler.get_last_run(job["job_id"])
        job["last_run"] = last_run

    return {"data": jobs}


@router.get("/history")
async def get_scheduler_history(
    job_name: str | None = Query(None, description="Filter by job name"),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """Paginated etl_refresh_log entries."""
    query = db.query(ETLRefreshLog).order_by(ETLRefreshLog.id.desc())

    if job_name:
        query = query.filter(ETLRefreshLog.job_name == job_name)

    total = query.count()
    entries = query.offset(offset).limit(limit).all()

    return {
        "data": [
            {
                "id": e.id,
                "job_name": e.job_name,
                "started_at": e.started_at,
                "finished_at": e.finished_at,
                "status": e.status,
                "records_processed": e.records_processed,
                "error_message": e.error_message,
            }
            for e in entries
        ],
        "meta": {"total": total, "limit": limit, "offset": offset},
    }


@router.post("/trigger/{job_id}")
async def trigger_job(job_id: str):
    """Manually trigger a scheduled job."""
    from services.scheduler_service import get_scheduler_service
    result = await get_scheduler_service().trigger_job(job_id)

    if "error" in result:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=result["error"])

    return {"data": result}
