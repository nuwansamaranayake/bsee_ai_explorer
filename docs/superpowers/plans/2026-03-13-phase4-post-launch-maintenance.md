# Phase 4: Post-Launch & Maintenance Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add regulatory change tracking, scheduled ETL with data freshness monitoring, and system-wide observability (token costs, response times, error rates) to the Beacon GoM platform.

**Architecture:** Monolithic extension of the existing FastAPI backend. APScheduler runs in-process via FastAPI lifespan events. All new tables live in the existing SQLite database. No new infrastructure dependencies beyond two pip packages (apscheduler, beautifulsoup4).

**Tech Stack:** FastAPI, APScheduler 3.x (AsyncIOScheduler), BeautifulSoup4, SQLAlchemy ORM, React 18+ with TanStack Query, shadcn/ui, Recharts.

---

## File Structure

### New Backend Files
| File | Responsibility |
|---|---|
| `backend/models/phase4_tables.py` | 3 new ORM models: AlertSummary, FederalRegisterDigest, ETLRefreshLog |
| `backend/services/regulatory_service.py` | BSEE Safety Alert scraper + AI digest generator |
| `backend/services/scheduler_service.py` | APScheduler wrapper: job registration, locking, manual trigger |
| `backend/services/monitoring_service.py` | In-memory metrics: token tracking, response times, error counts |
| `backend/routers/regulatory.py` | 6 endpoints for regulatory alerts |
| `backend/routers/scheduler.py` | 3 endpoints for scheduler status/history/trigger |
| `backend/routers/monitoring.py` | 4 endpoints for health/tokens/endpoints/errors |
| `backend/middleware/__init__.py` | Package init |
| `backend/middleware/monitoring.py` | MonitoringMiddleware for automatic request timing |

### New Frontend Files
| File | Responsibility |
|---|---|
| `frontend/src/pages/Regulatory.tsx` | Regulatory alerts page with alert cards and digest viewer |
| `frontend/src/pages/Monitoring.tsx` | System health dashboard with 4 card sections |
| `frontend/src/hooks/useRegulatory.ts` | TanStack Query hooks for regulatory endpoints |
| `frontend/src/hooks/useMonitoring.ts` | TanStack Query hooks for monitoring + scheduler endpoints |
| `frontend/src/components/DataFreshness.tsx` | Sidebar widget: green/yellow/red dot with popover |

### Modified Files
| File | Change |
|---|---|
| `backend/requirements.txt` | Add `apscheduler>=3.10,<4`, `beautifulsoup4>=4.12`, `psutil>=5.9` |
| `backend/models/database.py` | No changes needed (table creation handled in main.py lifespan) |
| `backend/main.py` | Add lifespan (scheduler start/stop), MonitoringMiddleware, 3 new routers, bump version |
| `backend/services/__init__.py` | Export new services |
| `backend/services/claude_service.py` | Add 1-line monitoring callback after each AI call |
| `backend/services/prompts.py` | Add REGULATORY_DIGEST prompt templates |
| `frontend/src/App.tsx` | Add 2 new routes: /regulatory, /monitoring |
| `frontend/src/components/AppSidebar.tsx` | Add 2 nav items + DataFreshness widget |

---

## Chunk 1: Database Schema & Dependencies

### Task 1: Add pip dependencies

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add apscheduler and beautifulsoup4 to requirements.txt**

Append these three lines to the end of `backend/requirements.txt`:

```
apscheduler>=3.10,<4
beautifulsoup4>=4.12
psutil>=5.9
```

- [ ] **Step 2: Install and verify dependencies**

Run: `cd /d E:\AiGNITE\projects\Beacon_GoM\backend && pip install apscheduler beautifulsoup4 psutil`
Expected: All three packages install successfully.

Run: `python -c "from apscheduler.schedulers.asyncio import AsyncIOScheduler; from bs4 import BeautifulSoup; import psutil; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add apscheduler and beautifulsoup4 dependencies for Phase 4"
```

---

### Task 2: Create Phase 4 ORM models

**Files:**
- Create: `backend/models/phase4_tables.py`
- Modify: `backend/models/database.py`

- [ ] **Step 1: Create phase4_tables.py with 3 new ORM models**

Create `backend/models/phase4_tables.py`:

```python
"""Phase 4 ORM models: regulatory tracking, ETL audit log.

Tables:
- alert_summaries: AI-digested BSEE Safety Alerts
- federal_register_digests: Federal Register rule change digests
- etl_refresh_log: Audit trail for all scheduled/manual ETL jobs
"""

from sqlalchemy import (
    Column, Integer, String, Float, Text, DateTime, Index
)
from models.database import Base


class AlertSummary(Base):
    """AI-digested BSEE Safety Alert summaries."""
    __tablename__ = "alert_summaries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_number = Column(String(20), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    published_date = Column(String(30), index=True)  # ISO 8601
    source_url = Column(String(1000))
    pdf_url = Column(String(1000))
    raw_text = Column(Text)  # Full extracted text from PDF
    ai_summary = Column(Text)  # Claude-generated plain-language digest
    ai_impact = Column(Text)  # Claude-generated operator impact analysis
    ai_action_items = Column(Text)  # JSON array of recommended actions
    status = Column(String(20), default="new", index=True)  # new, reviewed, dismissed
    created_at = Column(String(30))  # ISO 8601
    updated_at = Column(String(30))  # ISO 8601

    __table_args__ = (
        Index("ix_alert_status_date", "status", "published_date"),
    )


class FederalRegisterDigest(Base):
    """Federal Register rule change digests (future use)."""
    __tablename__ = "federal_register_digests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_number = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(500), nullable=False)
    published_date = Column(String(30), index=True)
    agency = Column(String(200))
    action_type = Column(String(100))  # Final Rule, Proposed Rule, Notice
    source_url = Column(String(1000))
    ai_summary = Column(Text)
    relevance_score = Column(Float)  # 0.0-1.0 relevance to GoM operations
    created_at = Column(String(30))


class ETLRefreshLog(Base):
    """Audit trail for all scheduled and manual ETL job executions."""
    __tablename__ = "etl_refresh_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_name = Column(String(100), nullable=False, index=True)
    started_at = Column(String(30), nullable=False)
    finished_at = Column(String(30))
    status = Column(String(20), nullable=False, index=True)  # running, success, failed
    records_processed = Column(Integer, default=0)
    error_message = Column(Text)

    __table_args__ = (
        Index("ix_etl_job_status", "job_name", "status"),
    )
```

- [ ] **Step 2: Verify tables can be created (no database.py changes needed — table creation is handled in main.py lifespan)**

Note: Do NOT add imports to `database.py` — that would create a circular import since `phase4_tables.py` already imports `Base` from `database.py`. Table creation is handled by the explicit import + `Base.metadata.create_all()` in the lifespan function added in Task 12.

Run: `cd /d E:\AiGNITE\projects\Beacon_GoM\backend && python -c "from models.database import engine, Base; from models.phase4_tables import AlertSummary, FederalRegisterDigest, ETLRefreshLog; Base.metadata.create_all(engine); print('Tables created:', [t for t in Base.metadata.tables.keys() if t in ('alert_summaries', 'federal_register_digests', 'etl_refresh_log')])"`

Expected: `Tables created: ['alert_summaries', 'federal_register_digests', 'etl_refresh_log']`

- [ ] **Step 3: Commit**

```bash
git add backend/models/phase4_tables.py
git commit -m "feat: add Phase 4 ORM models (alert_summaries, federal_register_digests, etl_refresh_log)"
```

---

## Chunk 2: Monitoring Service & Middleware (Step 4.3 — Foundation)

Building monitoring first because the scheduler (4.2) and regulatory service (4.1) both need to record metrics.

### Task 3: Create MonitoringService

**Files:**
- Create: `backend/services/monitoring_service.py`

- [ ] **Step 1: Create monitoring_service.py**

Create `backend/services/monitoring_service.py`:

```python
"""MonitoringService — in-memory metrics for API observability.

Tracks:
- AI token usage per endpoint (flushed to etl_refresh_log daily)
- Request response times (ring buffer, last 1000)
- Error counts by endpoint
- System health (uptime, DB size, ChromaDB count)

No external dependencies — uses stdlib collections only.
"""

import logging
import os
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class RequestTiming:
    """Single request timing record."""
    method: str
    path: str
    status_code: int
    duration_ms: float
    timestamp: str  # ISO 8601


@dataclass
class TokenRecord:
    """Token usage for a single AI call."""
    model: str
    input_tokens: int
    output_tokens: int
    endpoint: str
    timestamp: str


@dataclass
class EndpointStat:
    """Aggregated stats for a single endpoint."""
    path: str
    request_count: int
    error_count: int
    error_rate: float
    p50_ms: float
    p95_ms: float
    p99_ms: float


# Model pricing (USD per 1M tokens) — update as pricing changes
MODEL_PRICING = {
    "anthropic/claude-sonnet-4": {"input": 3.00, "output": 15.00},
    "anthropic/claude-sonnet-4-5-20250514": {"input": 3.00, "output": 15.00},
    "claude-sonnet-4-5-20250514": {"input": 3.00, "output": 15.00},
}
DEFAULT_PRICING = {"input": 3.00, "output": 15.00}


class MonitoringService:
    """In-memory metrics collector for Beacon GoM API."""

    def __init__(self):
        self._start_time = datetime.now(timezone.utc)
        self._token_records: list[TokenRecord] = []
        self._response_times: deque[RequestTiming] = deque(maxlen=1000)
        self._error_counts: Counter = Counter()
        self._daily_token_totals: dict[str, dict] = {}  # date_str -> {input, output, cost, by_endpoint}
        logger.info("MonitoringService initialized")

    def record_tokens(
        self, model: str, input_tokens: int, output_tokens: int, endpoint: str
    ) -> None:
        """Record token usage from an AI API call."""
        now = datetime.now(timezone.utc)
        self._token_records.append(
            TokenRecord(
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                endpoint=endpoint,
                timestamp=now.isoformat(),
            )
        )

        # Accumulate into daily totals
        date_key = now.strftime("%Y-%m-%d")
        if date_key not in self._daily_token_totals:
            self._daily_token_totals[date_key] = {
                "input_tokens": 0,
                "output_tokens": 0,
                "cost_usd": 0.0,
                "by_endpoint": Counter(),
            }
        day = self._daily_token_totals[date_key]
        day["input_tokens"] += input_tokens
        day["output_tokens"] += output_tokens

        pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
        cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000
        day["cost_usd"] += cost
        day["by_endpoint"][endpoint] += input_tokens + output_tokens

    def record_request(
        self, method: str, path: str, status_code: int, duration_ms: float
    ) -> None:
        """Record a request timing."""
        self._response_times.append(
            RequestTiming(
                method=method,
                path=path,
                status_code=status_code,
                duration_ms=duration_ms,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
        )

    def record_error(self, method: str, path: str, error_type: str) -> None:
        """Record an error occurrence."""
        self._error_counts[f"{method} {path} [{error_type}]"] += 1

    def get_system_health(self) -> dict:
        """Get aggregated system health snapshot."""
        import psutil  # Lazy import — may not be available

        uptime_seconds = (datetime.now(timezone.utc) - self._start_time).total_seconds()

        # DB size
        db_path = os.getenv("DATABASE_PATH", "./data/bsee.db")
        db_size_mb = 0.0
        try:
            db_size_mb = os.path.getsize(db_path) / (1024 * 1024)
        except OSError:
            pass

        # ChromaDB count
        chroma_chunks = 0
        try:
            from services.rag_service import get_rag_service
            chroma_chunks = get_rag_service().collection.count()
        except Exception:
            pass

        # Memory
        memory_mb = 0.0
        try:
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / (1024 * 1024)
        except Exception:
            pass

        return {
            "status": "ok",
            "uptime_seconds": int(uptime_seconds),
            "uptime_human": _format_uptime(uptime_seconds),
            "db_size_mb": round(db_size_mb, 2),
            "chroma_chunks": chroma_chunks,
            "memory_mb": round(memory_mb, 1),
            "total_requests_tracked": len(self._response_times),
            "total_errors": sum(self._error_counts.values()),
        }

    def get_token_summary(self) -> dict:
        """Get token usage summary: today + 7-day trend."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        today_data = self._daily_token_totals.get(today, {
            "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "by_endpoint": Counter()
        })

        # 7-day trend
        trend = []
        for date_key in sorted(self._daily_token_totals.keys())[-7:]:
            day = self._daily_token_totals[date_key]
            trend.append({
                "date": date_key,
                "input_tokens": day["input_tokens"],
                "output_tokens": day["output_tokens"],
                "total_tokens": day["input_tokens"] + day["output_tokens"],
                "cost_usd": round(day["cost_usd"], 4),
            })

        # By endpoint breakdown (today)
        by_endpoint = [
            {"endpoint": ep, "tokens": count}
            for ep, count in today_data.get("by_endpoint", Counter()).most_common(10)
        ]

        return {
            "today": {
                "input_tokens": today_data.get("input_tokens", 0),
                "output_tokens": today_data.get("output_tokens", 0),
                "total_tokens": today_data.get("input_tokens", 0) + today_data.get("output_tokens", 0),
                "cost_usd": round(today_data.get("cost_usd", 0.0), 4),
            },
            "trend_7d": trend,
            "by_endpoint": by_endpoint,
        }

    def get_endpoint_stats(self) -> list[dict]:
        """Get per-route response time percentiles and error rates."""
        from collections import defaultdict

        by_path: dict[str, list[float]] = defaultdict(list)
        error_by_path: Counter = Counter()

        for timing in self._response_times:
            by_path[timing.path].append(timing.duration_ms)
            if timing.status_code >= 400:
                error_by_path[timing.path] += 1

        stats = []
        for path, durations in sorted(by_path.items()):
            durations_sorted = sorted(durations)
            n = len(durations_sorted)
            errors = error_by_path.get(path, 0)
            stats.append({
                "path": path,
                "request_count": n,
                "error_count": errors,
                "error_rate": round(errors / n, 4) if n > 0 else 0.0,
                "p50_ms": round(durations_sorted[n // 2], 1) if n > 0 else 0.0,
                "p95_ms": round(durations_sorted[int(n * 0.95)], 1) if n > 0 else 0.0,
                "p99_ms": round(durations_sorted[int(n * 0.99)], 1) if n > 0 else 0.0,
            })

        return stats

    def get_recent_errors(self) -> list[dict]:
        """Get recent errors grouped by endpoint and type."""
        return [
            {"key": key, "count": count}
            for key, count in self._error_counts.most_common(20)
        ]

    def flush_daily_tokens(self) -> int:
        """Flush daily token totals to etl_refresh_log. Called by scheduler.

        Note: This is a sync function (not async) because it uses synchronous
        SQLAlchemy sessions. APScheduler's AsyncIOScheduler handles sync
        callables correctly via run_in_executor.
        """
        from models.database import SessionLocal
        from models.phase4_tables import ETLRefreshLog

        now = datetime.now(timezone.utc)
        today = now.strftime("%Y-%m-%d")
        today_data = self._daily_token_totals.get(today)

        if not today_data:
            return 0

        db = SessionLocal()
        try:
            log_entry = ETLRefreshLog(
                job_name="token_usage",
                started_at=now.isoformat(),
                finished_at=now.isoformat(),
                status="success",
                records_processed=today_data.get("input_tokens", 0) + today_data.get("output_tokens", 0),
                error_message=None,
            )
            db.add(log_entry)
            db.commit()
            return log_entry.records_processed
        except Exception as e:
            db.rollback()
            logger.error("Failed to flush token data: %s", e)
            return 0
        finally:
            db.close()


def _format_uptime(seconds: float) -> str:
    """Format seconds into human-readable uptime string."""
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    minutes = int((seconds % 3600) // 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


# Singleton
_monitoring_service: MonitoringService | None = None


def get_monitoring_service() -> MonitoringService:
    """Get or create the singleton MonitoringService instance."""
    global _monitoring_service
    if _monitoring_service is None:
        _monitoring_service = MonitoringService()
    return _monitoring_service
```

- [ ] **Step 2: Verify module imports correctly**

Run: `cd /d E:\AiGNITE\projects\Beacon_GoM\backend && python -c "from services.monitoring_service import get_monitoring_service; m = get_monitoring_service(); m.record_tokens('test', 100, 50, 'test_ep'); m.record_request('GET', '/api/test', 200, 45.3); print(m.get_system_health()); print(m.get_token_summary())"`

Expected: Prints health dict and token summary dict without errors.

- [ ] **Step 3: Commit**

```bash
git add backend/services/monitoring_service.py
git commit -m "feat: add MonitoringService for in-memory API metrics tracking"
```

---

### Task 4: Create MonitoringMiddleware

**Files:**
- Create: `backend/middleware/__init__.py`
- Create: `backend/middleware/monitoring.py`

- [ ] **Step 1: Create middleware package init**

Create `backend/middleware/__init__.py`:

```python
```

(Empty file — package marker only.)

- [ ] **Step 2: Create monitoring middleware**

Create `backend/middleware/monitoring.py`:

```python
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
```

- [ ] **Step 3: Commit**

```bash
git add backend/middleware/__init__.py backend/middleware/monitoring.py
git commit -m "feat: add MonitoringMiddleware for automatic request timing"
```

---

### Task 5: Wire MonitoringService into ClaudeService

**Files:**
- Modify: `backend/services/claude_service.py` (line ~177, after `token_tracker.record()`)

- [ ] **Step 1: Add monitoring callback to generate() method**

In `backend/services/claude_service.py`, in the `generate()` method, immediately after the line `token_tracker.record(input_tokens, output_tokens)` (around line 177), add:

```python
            # Record in monitoring service
            try:
                from services.monitoring_service import get_monitoring_service
                get_monitoring_service().record_tokens(
                    model=self.model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    endpoint="ai_call",
                )
            except Exception:
                pass  # Monitoring must never break AI calls
```

- [ ] **Step 2: Verify ClaudeService still imports cleanly**

Run: `cd /d E:\AiGNITE\projects\Beacon_GoM\backend && python -c "from services.claude_service import get_claude_service; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/services/claude_service.py
git commit -m "feat: wire ClaudeService token tracking into MonitoringService"
```

---

### Task 6: Create monitoring router

**Files:**
- Create: `backend/routers/monitoring.py`

- [ ] **Step 1: Create monitoring router with 4 endpoints**

Create `backend/routers/monitoring.py`:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/routers/monitoring.py
git commit -m "feat: add monitoring router (health, tokens, endpoints, errors)"
```

---

## Chunk 3: Scheduler Service (Step 4.2)

### Task 7: Create SchedulerService

**Files:**
- Create: `backend/services/scheduler_service.py`

- [ ] **Step 1: Create scheduler_service.py**

Create `backend/services/scheduler_service.py`:

```python
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
```

- [ ] **Step 2: Verify module imports**

Run: `cd /d E:\AiGNITE\projects\Beacon_GoM\backend && python -c "from services.scheduler_service import get_scheduler_service; s = get_scheduler_service(); print('Jobs:', [j.id for j in s.scheduler.get_jobs()])"`

Expected: `Jobs: ['etl_bsee_incidents', 'etl_pdf_ingest', 'regulatory_scrape', 'token_flush', 'health_heartbeat']`

- [ ] **Step 3: Commit**

```bash
git add backend/services/scheduler_service.py
git commit -m "feat: add SchedulerService with APScheduler for recurring ETL jobs"
```

---

### Task 8: Create scheduler router

**Files:**
- Create: `backend/routers/scheduler.py`

- [ ] **Step 1: Create scheduler router with 3 endpoints**

Create `backend/routers/scheduler.py`:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/routers/scheduler.py
git commit -m "feat: add scheduler router (status, history, manual trigger)"
```

---

## Chunk 4: Regulatory Service (Step 4.1)

### Task 9: Add regulatory prompt templates

**Files:**
- Modify: `backend/services/prompts.py`

- [ ] **Step 1: Add regulatory digest prompts to prompts.py**

Append to the end of `backend/services/prompts.py`:

```python

# ---------------------------------------------------------------------------
# Step 4.1 — Regulatory Change Tracker
# ---------------------------------------------------------------------------

REGULATORY_DIGEST_SYSTEM = """\
You are a regulatory analyst specializing in offshore oil and gas operations \
in the Gulf of Mexico. Given a BSEE Safety Alert, produce a structured digest \
that helps HSE managers quickly understand the alert's implications.

Your digest should:
1. Summarize the alert in 2-3 plain-language sentences
2. Identify which types of operators/facilities are affected
3. List specific action items operators should take
4. Assess the urgency level (critical, high, medium, low)

Write for a busy safety director who needs to decide in 30 seconds whether \
this alert requires immediate action from their team."""

REGULATORY_DIGEST_USER = """\
Generate a structured digest for this BSEE Safety Alert:

**Alert Number:** {alert_number}
**Title:** {title}
**Published Date:** {published_date}

**Full Text:**
{alert_text}

Respond with a JSON object:
{{
  "summary": "2-3 sentence plain-language summary",
  "impact": "Who is affected and how",
  "action_items": ["action 1", "action 2", ...],
  "urgency": "critical|high|medium|low"
}}"""
```

- [ ] **Step 2: Commit**

```bash
git add backend/services/prompts.py
git commit -m "feat: add regulatory digest prompt templates"
```

---

### Task 10: Create RegulatoryService

**Files:**
- Create: `backend/services/regulatory_service.py`

- [ ] **Step 1: Create regulatory_service.py**

Create `backend/services/regulatory_service.py`:

```python
"""RegulatoryService — BSEE Safety Alert scraper and AI digest generator.

Scrapes the BSEE Safety Alerts listing page, discovers new alerts,
downloads their PDFs, extracts text, and generates AI digests.

BSEE Safety Alerts page: https://www.bsee.gov/resources-tools/safety-alerts
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from models.database import SessionLocal
from models.phase4_tables import AlertSummary

logger = logging.getLogger(__name__)

BSEE_ALERTS_URL = "https://www.bsee.gov/resources-tools/safety-alerts"
USER_AGENT = "BeaconGoM/1.0 (BSEE data research; contact: info@aigniteconsulting.ai)"


class RegulatoryService:
    """Scrapes BSEE Safety Alerts and generates AI digests."""

    def __init__(self):
        logger.info("RegulatoryService initialized")

    async def scrape_new_alerts(self) -> int:
        """Scrape BSEE listing page for new Safety Alerts.

        Returns count of newly discovered alerts.
        """
        try:
            alert_links = await self._fetch_alert_listing()
        except Exception as e:
            logger.error("Failed to fetch BSEE alerts listing: %s", e)
            return 0

        db = SessionLocal()
        new_count = 0
        try:
            for alert_info in alert_links:
                alert_num = alert_info.get("alert_number", "")
                if not alert_num:
                    continue

                # Skip if already in DB
                existing = (
                    db.query(AlertSummary)
                    .filter(AlertSummary.alert_number == alert_num)
                    .first()
                )
                if existing:
                    continue

                # Create new entry
                now = datetime.now(timezone.utc).isoformat()
                entry = AlertSummary(
                    alert_number=alert_num,
                    title=alert_info.get("title", "Unknown"),
                    published_date=alert_info.get("date", ""),
                    source_url=alert_info.get("url", ""),
                    pdf_url=alert_info.get("pdf_url", ""),
                    status="new",
                    created_at=now,
                    updated_at=now,
                )
                db.add(entry)
                new_count += 1
                logger.info("Discovered new BSEE Safety Alert: %s", alert_num)

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error("Failed to save new alerts: %s", e)
            raise
        finally:
            db.close()

        return new_count

    async def _fetch_alert_listing(self) -> list[dict]:
        """Fetch and parse the BSEE Safety Alerts listing page."""
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            resp = await client.get(BSEE_ALERTS_URL)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        alerts = []

        # BSEE listing uses table rows or anchor links with alert numbers
        # Parse links that match Safety Alert pattern
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)

            # Match patterns like "Safety Alert 350" or "SA-350"
            alert_match = re.search(r"(?:Safety\s+Alert|SA)[- ]*(\d+)", text, re.IGNORECASE)
            if not alert_match:
                # Also check href for alert number patterns
                alert_match = re.search(r"safety-alert[- ]*(\d+)", href, re.IGNORECASE)

            if alert_match:
                alert_num = alert_match.group(1)
                full_url = href if href.startswith("http") else f"https://www.bsee.gov{href}"

                alerts.append({
                    "alert_number": alert_num,
                    "title": text[:500],
                    "url": full_url,
                    "pdf_url": "",  # Will be resolved from detail page if needed
                    "date": "",
                })

        logger.info("Scraped %d alert links from BSEE listing", len(alerts))
        return alerts

    async def generate_digest(self, alert_id: int) -> dict:
        """Generate an AI digest for a specific alert. Returns the digest dict."""
        db = SessionLocal()
        try:
            alert = db.query(AlertSummary).filter(AlertSummary.id == alert_id).first()
            if not alert:
                return {"error": "Alert not found"}

            if not alert.raw_text:
                return {"error": "No text content available for this alert. PDF may not be ingested yet."}

            from services.claude_service import get_claude_service
            from services.prompts import REGULATORY_DIGEST_SYSTEM, REGULATORY_DIGEST_USER

            claude = get_claude_service()
            user_prompt = REGULATORY_DIGEST_USER.format(
                alert_number=alert.alert_number,
                title=alert.title,
                published_date=alert.published_date or "Unknown",
                alert_text=alert.raw_text[:8000],  # Truncate to fit context
            )

            digest = await claude.generate_json(REGULATORY_DIGEST_SYSTEM, user_prompt)

            # Update DB
            now = datetime.now(timezone.utc).isoformat()
            alert.ai_summary = digest.get("summary", "")
            alert.ai_impact = digest.get("impact", "")
            alert.ai_action_items = json.dumps(digest.get("action_items", []))
            alert.updated_at = now
            db.commit()

            return digest

        except Exception as e:
            db.rollback()
            logger.error("Failed to generate digest for alert %d: %s", alert_id, e)
            return {"error": str(e)}
        finally:
            db.close()

    def get_alerts(
        self,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get alerts with optional status filter. Returns (alerts, total_count)."""
        db = SessionLocal()
        try:
            query = db.query(AlertSummary).order_by(AlertSummary.id.desc())
            if status:
                query = query.filter(AlertSummary.status == status)

            total = query.count()
            entries = query.offset(offset).limit(limit).all()

            alerts = [
                {
                    "id": a.id,
                    "alert_number": a.alert_number,
                    "title": a.title,
                    "published_date": a.published_date,
                    "source_url": a.source_url,
                    "status": a.status,
                    "has_digest": bool(a.ai_summary),
                    "ai_summary": a.ai_summary,
                    "ai_impact": a.ai_impact,
                    "ai_action_items": json.loads(a.ai_action_items) if a.ai_action_items else [],
                    "created_at": a.created_at,
                }
                for a in entries
            ]
            return alerts, total
        finally:
            db.close()

    def get_alert_detail(self, alert_id: int) -> dict | None:
        """Get full detail for a single alert."""
        db = SessionLocal()
        try:
            a = db.query(AlertSummary).filter(AlertSummary.id == alert_id).first()
            if not a:
                return None
            return {
                "id": a.id,
                "alert_number": a.alert_number,
                "title": a.title,
                "published_date": a.published_date,
                "source_url": a.source_url,
                "pdf_url": a.pdf_url,
                "status": a.status,
                "has_digest": bool(a.ai_summary),
                "raw_text": a.raw_text,
                "ai_summary": a.ai_summary,
                "ai_impact": a.ai_impact,
                "ai_action_items": json.loads(a.ai_action_items) if a.ai_action_items else [],
                "created_at": a.created_at,
                "updated_at": a.updated_at,
            }
        finally:
            db.close()

    def update_alert_status(self, alert_id: int, status: str) -> bool:
        """Update an alert's status (new, reviewed, dismissed)."""
        if status not in ("new", "reviewed", "dismissed"):
            return False
        db = SessionLocal()
        try:
            alert = db.query(AlertSummary).filter(AlertSummary.id == alert_id).first()
            if not alert:
                return False
            alert.status = status
            alert.updated_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()


# Singleton
_regulatory_service: RegulatoryService | None = None


def get_regulatory_service() -> RegulatoryService:
    """Get or create the singleton RegulatoryService instance."""
    global _regulatory_service
    if _regulatory_service is None:
        _regulatory_service = RegulatoryService()
    return _regulatory_service
```

- [ ] **Step 2: Verify module imports**

Run: `cd /d E:\AiGNITE\projects\Beacon_GoM\backend && python -c "from services.regulatory_service import get_regulatory_service; s = get_regulatory_service(); print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/services/regulatory_service.py
git commit -m "feat: add RegulatoryService for BSEE Safety Alert scraping and AI digests"
```

---

### Task 11: Create regulatory router

**Files:**
- Create: `backend/routers/regulatory.py`

- [ ] **Step 1: Create regulatory router with 6 endpoints**

Create `backend/routers/regulatory.py`:

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add backend/routers/regulatory.py
git commit -m "feat: add regulatory router (alerts CRUD, digest generation, scrape trigger)"
```

---

## Chunk 5: Wire Backend — main.py & Services Init

### Task 12: Update main.py with lifespan, middleware, and new routers

**Files:**
- Modify: `backend/main.py`
- Modify: `backend/services/__init__.py`

- [ ] **Step 1: Rewrite main.py with lifespan events, middleware, and new routers**

Replace the entire contents of `backend/main.py` with:

```python
"""Beacon GoM API — AI Safety & Regulatory Intelligence for Offshore Operations."""

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: start scheduler on startup, shut down on exit."""
    # Create Phase 4 tables if they don't exist
    from models.database import engine, Base
    from models.phase4_tables import AlertSummary, FederalRegisterDigest, ETLRefreshLog  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified")

    # Start scheduler
    from services.scheduler_service import get_scheduler_service
    scheduler = get_scheduler_service()
    await scheduler.start()
    logger.info("Scheduler started")

    yield

    # Shutdown scheduler
    await scheduler.shutdown()
    logger.info("Scheduler shut down")


app = FastAPI(
    title="Beacon GoM API",
    description="AI Safety & Regulatory Intelligence for Offshore Operations",
    version="0.4.0",
    lifespan=lifespan,
)

# Monitoring middleware (must be added before CORS)
from middleware.monitoring import MonitoringMiddleware
app.add_middleware(MonitoringMiddleware)

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
from routers import regulatory, scheduler, monitoring

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
# Phase 4 routers
app.include_router(regulatory.router, prefix="/api", tags=["regulatory"])
app.include_router(scheduler.router, prefix="/api", tags=["scheduler"])
app.include_router(monitoring.router, prefix="/api", tags=["monitoring"])


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

    # Scheduler status
    scheduler_status = None
    try:
        from services.scheduler_service import get_scheduler_service
        scheduler_status = get_scheduler_service().get_job_status()
    except Exception:
        pass

    return {
        "status": "ok",
        "service": "beacon-gom-api",
        "version": "0.4.0",
        "ai_available": claude.is_available,
        "ai_tokens_used": token_tracker.summary,
        "chromadb": chroma_status,
        "scheduler": scheduler_status,
    }
```

- [ ] **Step 2: Update services/__init__.py to export new services**

Replace `backend/services/__init__.py` with:

```python
from services.claude_service import ClaudeService, get_claude_service, ClaudeServiceError, token_tracker
from services.sql_service import SQLService, get_sql_service
from services.rag_service import RAGService, get_rag_service
from services.report_service import ReportService, get_report_service
from services.monitoring_service import MonitoringService, get_monitoring_service
from services.scheduler_service import SchedulerService, get_scheduler_service
from services.regulatory_service import RegulatoryService, get_regulatory_service
```

- [ ] **Step 3: Verify the app starts without errors**

Run: `cd /d E:\AiGNITE\projects\Beacon_GoM\backend && python -c "from main import app; print('Routes:', len(app.routes))"`
Expected: Prints route count (should be ~30+) without import errors.

- [ ] **Step 4: Commit**

```bash
git add backend/main.py backend/services/__init__.py
git commit -m "feat: wire Phase 4 into main.py — lifespan, middleware, 3 new routers, v0.4.0"
```

---

## Chunk 6: Frontend — Regulatory Page

### Task 13: Create useRegulatory hooks

**Files:**
- Create: `frontend/src/hooks/useRegulatory.ts`

- [ ] **Step 1: Create useRegulatory.ts**

Create `frontend/src/hooks/useRegulatory.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

interface Alert {
  id: number
  alert_number: string
  title: string
  published_date: string
  source_url: string
  status: string
  has_digest: boolean
  ai_summary: string | null
  ai_impact: string | null
  ai_action_items: string[]
  created_at: string
}

interface AlertDetail extends Alert {
  pdf_url: string
  raw_text: string | null
  updated_at: string
}

interface AlertStats {
  total: number
  new: number
  reviewed: number
  dismissed: number
}

interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

export function useAlerts(status?: string, limit = 20, offset = 0) {
  return useQuery({
    queryKey: ["regulatory", "alerts", status, limit, offset],
    queryFn: () =>
      apiClient<ApiResponse<Alert[]>>("/api/regulatory/alerts", {
        params: { status: status || undefined, limit, offset },
      }),
  })
}

export function useAlertDetail(alertId: number | null) {
  return useQuery({
    queryKey: ["regulatory", "alert", alertId],
    queryFn: () =>
      apiClient<ApiResponse<AlertDetail>>(`/api/regulatory/alerts/${alertId}`),
    enabled: alertId !== null,
  })
}

export function useAlertStats() {
  return useQuery({
    queryKey: ["regulatory", "stats"],
    queryFn: () => apiClient<ApiResponse<AlertStats>>("/api/regulatory/stats"),
  })
}

export function useGenerateDigest() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (alertId: number) =>
      apiClient<ApiResponse<Record<string, unknown>>>(
        `/api/regulatory/alerts/${alertId}/digest`,
        { method: "POST" }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["regulatory"] })
    },
  })
}

export function useUpdateAlertStatus() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ alertId, status }: { alertId: number; status: string }) =>
      apiClient<ApiResponse<{ id: number; status: string }>>(
        `/api/regulatory/alerts/${alertId}/status`,
        {
          method: "PATCH",
          body: JSON.stringify({ status }),
        }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["regulatory"] })
    },
  })
}

export function useTriggerScrape() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () =>
      apiClient<ApiResponse<{ new_alerts: number }>>("/api/regulatory/scrape", {
        method: "POST",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["regulatory"] })
    },
  })
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useRegulatory.ts
git commit -m "feat: add useRegulatory hooks for alert CRUD and digest generation"
```

---

### Task 14: Create Regulatory page

**Files:**
- Create: `frontend/src/pages/Regulatory.tsx`

- [ ] **Step 1: Create Regulatory.tsx**

Create `frontend/src/pages/Regulatory.tsx`:

```tsx
import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  useAlerts,
  useAlertStats,
  useGenerateDigest,
  useUpdateAlertStatus,
  useTriggerScrape,
} from "@/hooks/useRegulatory"
import { AlertTriangle, RefreshCw, FileText, CheckCircle, XCircle, Loader2 } from "lucide-react"

const STATUS_COLORS: Record<string, string> = {
  new: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
  reviewed: "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200",
  dismissed: "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400",
}

export default function Regulatory() {
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [page, setPage] = useState(0)

  const { data: alertsRes, isLoading, error } = useAlerts(statusFilter, 20, page * 20)
  const { data: statsRes } = useAlertStats()
  const generateDigest = useGenerateDigest()
  const updateStatus = useUpdateAlertStatus()
  const triggerScrape = useTriggerScrape()

  const alerts = alertsRes?.data || []
  const stats = statsRes?.data
  const total = (alertsRes?.meta?.total as number) || 0

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Regulatory Tracker</h1>
          <p className="text-muted-foreground">BSEE Safety Alerts & Regulatory Changes</p>
        </div>
        <Button
          onClick={() => triggerScrape.mutate()}
          disabled={triggerScrape.isPending}
          variant="outline"
        >
          {triggerScrape.isPending ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Check for Updates
        </Button>
      </div>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-4 gap-4">
          <Card className="cursor-pointer hover:border-primary" onClick={() => setStatusFilter(undefined)}>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold">{stats.total}</div>
              <p className="text-xs text-muted-foreground">Total Alerts</p>
            </CardContent>
          </Card>
          <Card className="cursor-pointer hover:border-primary" onClick={() => setStatusFilter("new")}>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-blue-600">{stats.new}</div>
              <p className="text-xs text-muted-foreground">New / Unreviewed</p>
            </CardContent>
          </Card>
          <Card className="cursor-pointer hover:border-primary" onClick={() => setStatusFilter("reviewed")}>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-green-600">{stats.reviewed}</div>
              <p className="text-xs text-muted-foreground">Reviewed</p>
            </CardContent>
          </Card>
          <Card className="cursor-pointer hover:border-primary" onClick={() => setStatusFilter("dismissed")}>
            <CardContent className="pt-4">
              <div className="text-2xl font-bold text-gray-500">{stats.dismissed}</div>
              <p className="text-xs text-muted-foreground">Dismissed</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Alert List */}
      <div className="space-y-3">
        {isLoading && <p className="text-muted-foreground">Loading alerts...</p>}
        {error && <p className="text-destructive">Failed to load alerts: {(error as Error).message}</p>}
        {!isLoading && alerts.length === 0 && (
          <Card>
            <CardContent className="py-8 text-center text-muted-foreground">
              <AlertTriangle className="mx-auto h-8 w-8 mb-2" />
              <p>No alerts found. Click "Check for Updates" to scan for new BSEE Safety Alerts.</p>
            </CardContent>
          </Card>
        )}

        {alerts.map((alert) => (
          <Card
            key={alert.id}
            className={`cursor-pointer transition-colors hover:border-primary ${
              selectedId === alert.id ? "border-primary" : ""
            }`}
            onClick={() => setSelectedId(selectedId === alert.id ? null : alert.id)}
          >
            <CardHeader className="pb-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CardTitle className="text-base">
                    Safety Alert {alert.alert_number}
                  </CardTitle>
                  <Badge className={STATUS_COLORS[alert.status] || ""} variant="secondary">
                    {alert.status}
                  </Badge>
                  {alert.has_digest && (
                    <Badge variant="outline" className="text-xs">
                      <FileText className="mr-1 h-3 w-3" /> Digest
                    </Badge>
                  )}
                </div>
                <span className="text-xs text-muted-foreground">
                  {alert.published_date || alert.created_at?.split("T")[0]}
                </span>
              </div>
              <p className="text-sm text-muted-foreground line-clamp-2">{alert.title}</p>
            </CardHeader>

            {selectedId === alert.id && (
              <CardContent className="space-y-4 border-t pt-4">
                {/* AI Summary */}
                {alert.ai_summary ? (
                  <div className="space-y-2">
                    <h4 className="font-semibold text-sm">AI Summary</h4>
                    <p className="text-sm">{alert.ai_summary}</p>
                    {alert.ai_impact && (
                      <>
                        <h4 className="font-semibold text-sm">Impact</h4>
                        <p className="text-sm">{alert.ai_impact}</p>
                      </>
                    )}
                    {alert.ai_action_items.length > 0 && (
                      <>
                        <h4 className="font-semibold text-sm">Action Items</h4>
                        <ul className="list-disc list-inside text-sm space-y-1">
                          {alert.ai_action_items.map((item, i) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      </>
                    )}
                  </div>
                ) : (
                  <Button
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation()
                      generateDigest.mutate(alert.id)
                    }}
                    disabled={generateDigest.isPending}
                  >
                    {generateDigest.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <FileText className="mr-2 h-4 w-4" />
                    )}
                    Generate AI Digest
                  </Button>
                )}

                {/* Actions */}
                <div className="flex gap-2">
                  {alert.status !== "reviewed" && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={(e) => {
                        e.stopPropagation()
                        updateStatus.mutate({ alertId: alert.id, status: "reviewed" })
                      }}
                    >
                      <CheckCircle className="mr-1 h-4 w-4" /> Mark Reviewed
                    </Button>
                  )}
                  {alert.status !== "dismissed" && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation()
                        updateStatus.mutate({ alertId: alert.id, status: "dismissed" })
                      }}
                    >
                      <XCircle className="mr-1 h-4 w-4" /> Dismiss
                    </Button>
                  )}
                  {alert.source_url && (
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={(e) => {
                        e.stopPropagation()
                        window.open(alert.source_url, "_blank")
                      }}
                    >
                      View on BSEE
                    </Button>
                  )}
                </div>
              </CardContent>
            )}
          </Card>
        ))}
      </div>

      {/* Pagination */}
      {total > 20 && (
        <div className="flex justify-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={page === 0}
            onClick={() => setPage(page - 1)}
          >
            Previous
          </Button>
          <span className="text-sm text-muted-foreground self-center">
            Page {page + 1} of {Math.ceil(total / 20)}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={(page + 1) * 20 >= total}
            onClick={() => setPage(page + 1)}
          >
            Next
          </Button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Regulatory.tsx
git commit -m "feat: add Regulatory page with alert cards, AI digest, and status management"
```

---

## Chunk 7: Frontend — Monitoring Page & DataFreshness Widget

### Task 15: Create useMonitoring hooks

**Files:**
- Create: `frontend/src/hooks/useMonitoring.ts`

- [ ] **Step 1: Create useMonitoring.ts**

Create `frontend/src/hooks/useMonitoring.ts`:

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { apiClient } from "@/lib/api"

interface SystemHealth {
  status: string
  uptime_seconds: number
  uptime_human: string
  db_size_mb: number
  chroma_chunks: number
  memory_mb: number
  total_requests_tracked: number
  total_errors: number
  scheduler: JobStatus[] | null
}

interface TokenSummary {
  today: {
    input_tokens: number
    output_tokens: number
    total_tokens: number
    cost_usd: number
  }
  trend_7d: {
    date: string
    input_tokens: number
    output_tokens: number
    total_tokens: number
    cost_usd: number
  }[]
  by_endpoint: { endpoint: string; tokens: number }[]
}

interface EndpointStat {
  path: string
  request_count: number
  error_count: number
  error_rate: number
  p50_ms: number
  p95_ms: number
  p99_ms: number
}

interface ErrorEntry {
  key: string
  count: number
}

interface JobStatus {
  job_id: string
  name: string
  next_run: string | null
  state: string
  last_run?: {
    job_name: string
    started_at: string
    finished_at: string | null
    status: string
    records_processed: number
    error_message: string | null
  } | null
}

interface HistoryEntry {
  id: number
  job_name: string
  started_at: string
  finished_at: string | null
  status: string
  records_processed: number
  error_message: string | null
}

interface ApiResponse<T> {
  data: T
  meta?: Record<string, unknown>
}

// Monitoring hooks
export function useSystemHealth() {
  return useQuery({
    queryKey: ["monitoring", "health"],
    queryFn: () => apiClient<ApiResponse<SystemHealth>>("/api/monitoring/health"),
    refetchInterval: 30_000,
  })
}

export function useTokenUsage() {
  return useQuery({
    queryKey: ["monitoring", "tokens"],
    queryFn: () => apiClient<ApiResponse<TokenSummary>>("/api/monitoring/tokens"),
    refetchInterval: 30_000,
  })
}

export function useEndpointStats() {
  return useQuery({
    queryKey: ["monitoring", "endpoints"],
    queryFn: () => apiClient<ApiResponse<EndpointStat[]>>("/api/monitoring/endpoints"),
    refetchInterval: 30_000,
  })
}

export function useRecentErrors() {
  return useQuery({
    queryKey: ["monitoring", "errors"],
    queryFn: () => apiClient<ApiResponse<ErrorEntry[]>>("/api/monitoring/errors"),
    refetchInterval: 30_000,
  })
}

// Scheduler hooks
export function useSchedulerStatus() {
  return useQuery({
    queryKey: ["scheduler", "status"],
    queryFn: () => apiClient<ApiResponse<JobStatus[]>>("/api/scheduler/status"),
    refetchInterval: 30_000,
  })
}

export function useSchedulerHistory(jobName?: string, limit = 20) {
  return useQuery({
    queryKey: ["scheduler", "history", jobName, limit],
    queryFn: () =>
      apiClient<ApiResponse<HistoryEntry[]>>("/api/scheduler/history", {
        params: { job_name: jobName || undefined, limit },
      }),
  })
}

export function useTriggerJob() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (jobId: string) =>
      apiClient<ApiResponse<{ job_id: string; triggered: boolean }>>(
        `/api/scheduler/trigger/${jobId}`,
        { method: "POST" }
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scheduler"] })
    },
  })
}

// Data freshness hook (for sidebar widget)
export function useDataFreshness() {
  return useQuery({
    queryKey: ["scheduler", "status"],
    queryFn: () => apiClient<ApiResponse<JobStatus[]>>("/api/scheduler/status"),
    refetchInterval: 60_000, // Check every minute
    select: (data) => {
      const jobs = data.data || []
      // Find the most recent successful ETL job
      let latestSuccess: string | null = null
      for (const job of jobs) {
        if (job.last_run?.status === "success" && job.last_run.finished_at) {
          if (!latestSuccess || job.last_run.finished_at > latestSuccess) {
            latestSuccess = job.last_run.finished_at
          }
        }
      }

      if (!latestSuccess) return { status: "unknown" as const, label: "No data yet" }

      const ageMs = Date.now() - new Date(latestSuccess).getTime()
      const ageHours = ageMs / (1000 * 60 * 60)

      if (ageHours < 24) return { status: "fresh" as const, label: `${Math.round(ageHours)}h ago` }
      if (ageHours < 72) return { status: "stale" as const, label: `${Math.round(ageHours / 24)}d ago` }
      return { status: "old" as const, label: `${Math.round(ageHours / 24)}d ago` }
    },
  })
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useMonitoring.ts
git commit -m "feat: add useMonitoring and useScheduler hooks"
```

---

### Task 16: Create DataFreshness sidebar widget

**Files:**
- Create: `frontend/src/components/DataFreshness.tsx`

**Prerequisite:** The Popover component from shadcn/ui must be installed first.

- [ ] **Step 0: Install shadcn Popover component**

Run: `cd /d E:\AiGNITE\projects\Beacon_GoM\frontend && npx shadcn@latest add popover`

Expected: Creates `frontend/src/components/ui/popover.tsx`.

- [ ] **Step 1: Create DataFreshness.tsx**

Create `frontend/src/components/DataFreshness.tsx`:

```tsx
import { useDataFreshness, useSchedulerStatus } from "@/hooks/useMonitoring"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { Badge } from "@/components/ui/badge"
import { Database } from "lucide-react"

const DOT_COLORS = {
  fresh: "bg-green-500",
  stale: "bg-yellow-500",
  old: "bg-red-500",
  unknown: "bg-gray-400",
}

export function DataFreshness() {
  const { data: freshness } = useDataFreshness()
  const { data: schedulerRes } = useSchedulerStatus()
  const jobs = schedulerRes?.data || []

  const status = freshness?.status || "unknown"
  const label = freshness?.label || "Checking..."

  return (
    <Popover>
      <PopoverTrigger asChild>
        <button className="flex items-center gap-2 px-3 py-1.5 w-full text-left text-sm hover:bg-accent rounded-md transition-colors">
          <span className={`h-2 w-2 rounded-full ${DOT_COLORS[status]}`} />
          <Database className="h-3.5 w-3.5 text-muted-foreground" />
          <span className="text-muted-foreground">Data: {label}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-72">
        <div className="space-y-2">
          <h4 className="font-semibold text-sm">ETL Job Status</h4>
          {jobs.length === 0 && (
            <p className="text-xs text-muted-foreground">No scheduled jobs found</p>
          )}
          {jobs
            .filter((j) => j.job_id !== "health_heartbeat")
            .map((job) => (
              <div key={job.job_id} className="flex items-center justify-between text-xs">
                <span className="truncate">{job.name}</span>
                <div className="flex items-center gap-1.5">
                  {job.last_run ? (
                    <Badge
                      variant={job.last_run.status === "success" ? "default" : "destructive"}
                      className="text-[10px] px-1 py-0"
                    >
                      {job.last_run.status}
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="text-[10px] px-1 py-0">
                      pending
                    </Badge>
                  )}
                </div>
              </div>
            ))}
        </div>
      </PopoverContent>
    </Popover>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/components/DataFreshness.tsx
git commit -m "feat: add DataFreshness sidebar widget with status popover"
```

---

### Task 17: Create Monitoring page

**Files:**
- Create: `frontend/src/pages/Monitoring.tsx`

- [ ] **Step 1: Create Monitoring.tsx**

Create `frontend/src/pages/Monitoring.tsx`:

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import {
  useSystemHealth,
  useTokenUsage,
  useEndpointStats,
  useSchedulerStatus,
  useTriggerJob,
} from "@/hooks/useMonitoring"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts"
import { Activity, Database, Cpu, DollarSign, Play, Loader2 } from "lucide-react"

export default function Monitoring() {
  const { data: healthRes, isLoading: healthLoading } = useSystemHealth()
  const { data: tokensRes } = useTokenUsage()
  const { data: endpointsRes } = useEndpointStats()
  const { data: schedulerRes } = useSchedulerStatus()
  const triggerJob = useTriggerJob()

  const health = healthRes?.data
  const tokens = tokensRes?.data
  const endpoints = endpointsRes?.data || []
  const jobs = schedulerRes?.data || []

  return (
    <div className="p-6 space-y-6">
      <div>
        <h1 className="text-2xl font-bold">System Monitoring</h1>
        <p className="text-muted-foreground">Health, performance, and cost tracking</p>
      </div>

      {/* System Health Row */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-green-500" />
              <span className="text-xs text-muted-foreground">Uptime</span>
            </div>
            <div className="text-xl font-bold mt-1">
              {healthLoading ? "..." : health?.uptime_human || "N/A"}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-blue-500" />
              <span className="text-xs text-muted-foreground">DB Size</span>
            </div>
            <div className="text-xl font-bold mt-1">
              {health ? `${health.db_size_mb} MB` : "..."}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Database className="h-4 w-4 text-purple-500" />
              <span className="text-xs text-muted-foreground">ChromaDB</span>
            </div>
            <div className="text-xl font-bold mt-1">
              {health ? `${health.chroma_chunks} chunks` : "..."}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-4">
            <div className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-orange-500" />
              <span className="text-xs text-muted-foreground">Memory</span>
            </div>
            <div className="text-xl font-bold mt-1">
              {health ? `${health.memory_mb} MB` : "..."}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Token Usage + API Performance */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Token Usage */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <DollarSign className="h-4 w-4" />
              AI Token Usage (7-Day)
            </CardTitle>
          </CardHeader>
          <CardContent>
            {tokens?.today && (
              <div className="mb-4 grid grid-cols-3 gap-2 text-center">
                <div>
                  <div className="text-lg font-bold">{tokens.today.total_tokens.toLocaleString()}</div>
                  <div className="text-xs text-muted-foreground">Today&apos;s Tokens</div>
                </div>
                <div>
                  <div className="text-lg font-bold">${tokens.today.cost_usd.toFixed(4)}</div>
                  <div className="text-xs text-muted-foreground">Today&apos;s Cost</div>
                </div>
                <div>
                  <div className="text-lg font-bold">
                    {tokens.by_endpoint.length}
                  </div>
                  <div className="text-xs text-muted-foreground">Active Features</div>
                </div>
              </div>
            )}
            {tokens?.trend_7d && tokens.trend_7d.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={tokens.trend_7d}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} />
                  <Tooltip />
                  <Bar dataKey="total_tokens" fill="hsl(var(--primary))" name="Tokens" />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-sm text-muted-foreground text-center py-8">
                No token usage data yet
              </p>
            )}
          </CardContent>
        </Card>

        {/* API Performance */}
        <Card>
          <CardHeader>
            <CardTitle>API Performance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-1.5 pr-2">Endpoint</th>
                    <th className="text-right py-1.5 px-2">Reqs</th>
                    <th className="text-right py-1.5 px-2">P50</th>
                    <th className="text-right py-1.5 px-2">P95</th>
                    <th className="text-right py-1.5 px-2">Err%</th>
                  </tr>
                </thead>
                <tbody>
                  {endpoints.length === 0 && (
                    <tr>
                      <td colSpan={5} className="py-4 text-center text-muted-foreground">
                        No request data yet
                      </td>
                    </tr>
                  )}
                  {endpoints.slice(0, 15).map((ep) => (
                    <tr
                      key={ep.path}
                      className={`border-b ${ep.error_rate > 0.05 || ep.p95_ms > 2000 ? "bg-red-50 dark:bg-red-950" : ""}`}
                    >
                      <td className="py-1.5 pr-2 truncate max-w-[200px]">{ep.path}</td>
                      <td className="text-right py-1.5 px-2">{ep.request_count}</td>
                      <td className="text-right py-1.5 px-2">{ep.p50_ms}ms</td>
                      <td className="text-right py-1.5 px-2">{ep.p95_ms}ms</td>
                      <td className="text-right py-1.5 px-2">
                        {(ep.error_rate * 100).toFixed(1)}%
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* ETL Job Status */}
      <Card>
        <CardHeader>
          <CardTitle>Scheduled ETL Jobs</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="text-left py-2 pr-4">Job</th>
                  <th className="text-left py-2 px-4">Last Run</th>
                  <th className="text-left py-2 px-4">Status</th>
                  <th className="text-left py-2 px-4">Records</th>
                  <th className="text-left py-2 px-4">Next Run</th>
                  <th className="text-right py-2">Action</th>
                </tr>
              </thead>
              <tbody>
                {jobs.map((job) => (
                  <tr key={job.job_id} className="border-b">
                    <td className="py-2 pr-4 font-medium">{job.name}</td>
                    <td className="py-2 px-4 text-xs">
                      {job.last_run?.finished_at
                        ? new Date(job.last_run.finished_at).toLocaleString()
                        : "Never"}
                    </td>
                    <td className="py-2 px-4">
                      {job.last_run ? (
                        <Badge
                          variant={job.last_run.status === "success" ? "default" : "destructive"}
                        >
                          {job.last_run.status}
                        </Badge>
                      ) : (
                        <Badge variant="secondary">pending</Badge>
                      )}
                    </td>
                    <td className="py-2 px-4 text-xs">
                      {job.last_run?.records_processed ?? "-"}
                    </td>
                    <td className="py-2 px-4 text-xs">
                      {job.next_run ? new Date(job.next_run).toLocaleString() : "N/A"}
                    </td>
                    <td className="py-2 text-right">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => triggerJob.mutate(job.job_id)}
                        disabled={triggerJob.isPending}
                      >
                        {triggerJob.isPending ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Play className="h-3 w-3" />
                        )}
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/pages/Monitoring.tsx
git commit -m "feat: add Monitoring page with health, tokens, API perf, and ETL status"
```

---

## Chunk 8: Wire Frontend — Routes, Navigation, Integration

### Task 18: Update App.tsx with new routes

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Add imports and routes for Regulatory and Monitoring pages**

In `frontend/src/App.tsx`, add these two imports after the existing page imports (after line 10 `import Reports from "@/pages/Reports"`):

```typescript
import Regulatory from "@/pages/Regulatory"
import Monitoring from "@/pages/Monitoring"
```

Then add two new Route elements inside the `<Routes>` block, after the `/reports` route:

```tsx
            <Route path="/regulatory" element={<Regulatory />} />
            <Route path="/monitoring" element={<Monitoring />} />
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "feat: add /regulatory and /monitoring routes to App.tsx"
```

---

### Task 19: Update AppSidebar with new nav items and DataFreshness

**Files:**
- Modify: `frontend/src/components/AppSidebar.tsx`

- [ ] **Step 1: Add Regulatory and Monitoring nav items**

In `frontend/src/components/AppSidebar.tsx`, in the `navItems` array (around line 36-42), add two new entries after `Reports`:

```typescript
  { title: "Regulatory", path: "/regulatory", icon: AlertTriangle },
  { title: "Monitoring", path: "/monitoring", icon: Activity },
```

Also update the lucide-react import at the top to add both `AlertTriangle` and `Activity` (neither is currently imported):

Replace the existing lucide-react import block with:
```typescript
import {
  LayoutDashboard,
  ShieldCheck,
  MessageSquare,
  FileSearch,
  FileText,
  Radar,
  Sun,
  Moon,
  Monitor,
  AlertTriangle,
  Activity,
} from "lucide-react"
```

- [ ] **Step 2: Add DataFreshness widget to sidebar**

In `frontend/src/components/AppSidebar.tsx`, add this import at the top:

```typescript
import { DataFreshness } from "@/components/DataFreshness"
```

Then in the JSX, add `<DataFreshness />` inside the `<SidebarContent>` section, after the `</SidebarGroup>` closing tag and before the closing `</SidebarContent>`:

```tsx
        <SidebarSeparator />
        <div className="px-2 py-1">
          <DataFreshness />
        </div>
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AppSidebar.tsx
git commit -m "feat: add Regulatory + Monitoring nav items and DataFreshness widget to sidebar"
```

---

### Task 20: Docker rebuild and smoke test

- [ ] **Step 1: Rebuild Docker containers**

Run: `cd /d E:\AiGNITE\projects\Beacon_GoM && docker compose down && docker compose up --build -d`

Wait for containers to become healthy.

- [ ] **Step 2: Verify health endpoint includes scheduler**

Run: `curl http://localhost/health | python -m json.tool`

Expected: JSON with `version: "0.4.0"`, `scheduler` array with 5 jobs, `status: "ok"`.

- [ ] **Step 3: Verify new API endpoints**

Run these commands:
```bash
curl http://localhost/api/monitoring/health | python -m json.tool
curl http://localhost/api/monitoring/tokens | python -m json.tool
curl http://localhost/api/scheduler/status | python -m json.tool
curl http://localhost/api/regulatory/alerts | python -m json.tool
curl http://localhost/api/regulatory/stats | python -m json.tool
```

Expected: All return `{ "data": ... }` responses without errors.

- [ ] **Step 4: Verify frontend pages load**

Open `http://localhost` in browser. Check:
1. Sidebar has 7 nav items (Dashboard, Compliance, AI Chat, Documents, Reports, Regulatory, Monitoring)
2. DataFreshness widget visible in sidebar below nav items
3. `/regulatory` page loads and shows "Check for Updates" button
4. `/monitoring` page loads and shows health cards

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: Phase 4 complete — regulatory tracker, scheduled ETL, monitoring dashboard"
```
