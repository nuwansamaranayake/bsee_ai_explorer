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
        import psutil

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
