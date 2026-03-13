"""SchedulerService — APScheduler wrapper for recurring ETL and maintenance jobs.

Jobs:
- etl_bsee_incidents: Daily 02:00 UTC — incremental incident/INC fetch
- etl_pdf_ingest: Daily 03:00 UTC — check for new Safety Alert PDFs
- regulatory_scrape: Every 6 hours — BSEE Safety Alert scraper
- token_flush: Daily 23:55 UTC — flush token usage to DB
- health_heartbeat: Every 5 minutes — write heartbeat to etl_refresh_log

Uses etl_refresh_log for:
1. Mutex locking (skip if status='running' for this job)
2. Audit trail (every execution recorded)
3. Incremental fetch (last successful finished_at = watermark)
"""

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from models.database import SessionLocal
from models.phase4_tables import ETLRefreshLog

logger = logging.getLogger(__name__)


class SchedulerService:
    """Manages scheduled background jobs via APScheduler."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="UTC")
        self._register_jobs()
        logger.info("SchedulerService initialized with %d jobs", len(self.scheduler.get_jobs()))

    def _register_jobs(self):
        """Register all scheduled jobs."""
        # Daily ETL: incidents/INCs
        self.scheduler.add_job(
            _job_etl_bsee_incidents,
            CronTrigger(hour=2, minute=0),
            id="etl_bsee_incidents",
            name="BSEE Incident/INC ETL",
            replace_existing=True,
        )
        # Daily ETL: PDF ingestion
        self.scheduler.add_job(
            _job_etl_pdf_ingest,
            CronTrigger(hour=3, minute=0),
            id="etl_pdf_ingest",
            name="PDF Download & Ingest",
            replace_existing=True,
        )
        # Every 6 hours: regulatory scrape
        self.scheduler.add_job(
            _job_regulatory_scrape,
            IntervalTrigger(hours=6),
            id="regulatory_scrape",
            name="BSEE Safety Alert Scraper",
            replace_existing=True,
        )
        # Daily: flush token usage
        self.scheduler.add_job(
            _job_token_flush,
            CronTrigger(hour=23, minute=55),
            id="token_flush",
            name="Flush Token Usage to DB",
            replace_existing=True,
        )
        # Every 5 minutes: heartbeat
        self.scheduler.add_job(
            _job_health_heartbeat,
            IntervalTrigger(minutes=5),
            id="health_heartbeat",
            name="Health Heartbeat",
            replace_existing=True,
        )

    async def start(self) -> None:
        """Start the scheduler. Called from FastAPI lifespan startup."""
        self.scheduler.start()
        logger.info("Scheduler started with %d jobs", len(self.scheduler.get_jobs()))

    async def shutdown(self) -> None:
        """Gracefully shut down. Called from FastAPI lifespan shutdown."""
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler shut down gracefully")

    def get_job_status(self) -> list[dict]:
        """Get status of all registered jobs."""
        jobs = []
        for job in self.scheduler.get_jobs():
            next_run = job.next_run_time
            jobs.append({
                "job_id": job.id,
                "name": job.name,
                "next_run": next_run.isoformat() if next_run else None,
                "state": "scheduled" if next_run else "paused",
            })
        return jobs

    async def trigger_job(self, job_id: str) -> dict:
        """Manually trigger a job by ID. Returns job info or error."""
        job = self.scheduler.get_job(job_id)
        if not job:
            return {"error": f"Job '{job_id}' not found"}

        # Run immediately
        job.modify(next_run_time=datetime.now(timezone.utc))
        logger.info("Manually triggered job: %s", job_id)
        return {"job_id": job_id, "name": job.name, "triggered": True}

    def get_last_run(self, job_name: str) -> dict | None:
        """Get the most recent etl_refresh_log entry for a job."""
        db = SessionLocal()
        try:
            entry = (
                db.query(ETLRefreshLog)
                .filter(ETLRefreshLog.job_name == job_name)
                .order_by(ETLRefreshLog.id.desc())
                .first()
            )
            if entry:
                return {
                    "job_name": entry.job_name,
                    "started_at": entry.started_at,
                    "finished_at": entry.finished_at,
                    "status": entry.status,
                    "records_processed": entry.records_processed,
                    "error_message": entry.error_message,
                }
            return None
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Job mutex helpers
# ---------------------------------------------------------------------------

def _acquire_lock(db, job_name: str) -> ETLRefreshLog | None:
    """Try to acquire a mutex lock via etl_refresh_log. Returns log entry or None."""
    # Check for running instance
    running = (
        db.query(ETLRefreshLog)
        .filter(ETLRefreshLog.job_name == job_name, ETLRefreshLog.status == "running")
        .first()
    )
    if running:
        logger.warning("Job %s already running (started %s), skipping", job_name, running.started_at)
        return None

    entry = ETLRefreshLog(
        job_name=job_name,
        started_at=datetime.now(timezone.utc).isoformat(),
        status="running",
        records_processed=0,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _release_lock(db, entry: ETLRefreshLog, status: str, records: int = 0, error: str | None = None):
    """Release the mutex lock by updating the log entry."""
    entry.finished_at = datetime.now(timezone.utc).isoformat()
    entry.status = status
    entry.records_processed = records
    entry.error_message = error
    db.commit()


def _get_last_success(db, job_name: str) -> str | None:
    """Get the finished_at timestamp of the last successful run."""
    entry = (
        db.query(ETLRefreshLog)
        .filter(ETLRefreshLog.job_name == job_name, ETLRefreshLog.status == "success")
        .order_by(ETLRefreshLog.id.desc())
        .first()
    )
    return entry.finished_at if entry else None


# ---------------------------------------------------------------------------
# Job implementations
# ---------------------------------------------------------------------------

async def _job_etl_bsee_incidents():
    """Incremental fetch of new BSEE incidents/INCs."""
    db = SessionLocal()
    lock = None
    try:
        lock = _acquire_lock(db, "etl_bsee_incidents")
        if not lock:
            return

        last_success = _get_last_success(db, "etl_bsee_incidents")
        logger.info("Running etl_bsee_incidents (last success: %s)", last_success or "never")

        # Placeholder: actual BSEE API incremental fetch would go here
        # For now, just log success
        records = 0
        _release_lock(db, lock, "success", records)
        logger.info("etl_bsee_incidents completed: %d records", records)

    except Exception as e:
        logger.error("etl_bsee_incidents failed: %s", e)
        try:
            if lock:
                _release_lock(db, lock, "failed", error=str(e)[:500])
        except Exception:
            pass
    finally:
        db.close()


async def _job_etl_pdf_ingest():
    """Download new Safety Alert PDFs and ingest into ChromaDB."""
    db = SessionLocal()
    lock = None
    try:
        lock = _acquire_lock(db, "etl_pdf_ingest")
        if not lock:
            return

        logger.info("Running etl_pdf_ingest")

        # Re-use existing download + ingest pipeline
        from etl.download_safety_alerts import download_all
        stats = await download_all()
        new_downloads = stats.get("downloaded", 0)

        if new_downloads > 0:
            from etl.ingest_pdfs import ingest_all
            ingest_all(force=False)

        _release_lock(db, lock, "success", new_downloads)
        logger.info("etl_pdf_ingest completed: %d new PDFs", new_downloads)

    except Exception as e:
        logger.error("etl_pdf_ingest failed: %s", e)
        try:
            if lock:
                _release_lock(db, lock, "failed", error=str(e)[:500])
        except Exception:
            pass
    finally:
        db.close()


async def _job_regulatory_scrape():
    """Scrape BSEE for new Safety Alerts."""
    db = SessionLocal()
    lock = None
    try:
        lock = _acquire_lock(db, "regulatory_scrape")
        if not lock:
            return

        logger.info("Running regulatory_scrape")

        from services.regulatory_service import get_regulatory_service
        service = get_regulatory_service()
        new_alerts = await service.scrape_new_alerts()

        _release_lock(db, lock, "success", new_alerts)
        logger.info("regulatory_scrape completed: %d new alerts", new_alerts)

    except Exception as e:
        logger.error("regulatory_scrape failed: %s", e)
        try:
            if lock:
                _release_lock(db, lock, "failed", error=str(e)[:500])
        except Exception:
            pass
    finally:
        db.close()


async def _job_token_flush():
    """Flush daily token usage to etl_refresh_log."""
    try:
        from services.monitoring_service import get_monitoring_service
        flushed = get_monitoring_service().flush_daily_tokens()  # sync method
        logger.info("token_flush completed: %d tokens recorded", flushed)
    except Exception as e:
        logger.error("token_flush failed: %s", e)


async def _job_health_heartbeat():
    """Write a heartbeat entry to etl_refresh_log."""
    db = SessionLocal()
    try:
        now = datetime.now(timezone.utc).isoformat()
        entry = ETLRefreshLog(
            job_name="health_heartbeat",
            started_at=now,
            finished_at=now,
            status="success",
            records_processed=1,
        )
        db.add(entry)
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error("health_heartbeat failed: %s", e)
    finally:
        db.close()


# Singleton
_scheduler_service: SchedulerService | None = None


def get_scheduler_service() -> SchedulerService:
    """Get or create the singleton SchedulerService instance."""
    global _scheduler_service
    if _scheduler_service is None:
        _scheduler_service = SchedulerService()
    return _scheduler_service
