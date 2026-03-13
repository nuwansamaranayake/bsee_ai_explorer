"""AI analysis endpoints — trend analysis and root cause categorization."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, case, distinct
from sqlalchemy.orm import Session

from models.database import get_db
from models.tables import Incident, INC, Production, IncidentRootCause
from services.claude_service import get_claude_service, ClaudeServiceError, token_tracker
from services.prompts import (
    TREND_ANALYSIS_SYSTEM,
    TREND_ANALYSIS_USER,
    ROOT_CAUSE_SYSTEM,
    ROOT_CAUSE_USER,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class TrendAnalysisRequest(BaseModel):
    operator: str | None = Field(default=None, max_length=200)
    year_start: int | None = Field(default=None, ge=1950, le=2100)
    year_end: int | None = Field(default=None, ge=1950, le=2100)
    incident_types: list[str] | None = None
    water_depth_min: int | None = Field(default=None, ge=0, le=50000)
    water_depth_max: int | None = Field(default=None, ge=0, le=50000)


class TrendAnalysisResponse(BaseModel):
    briefing: str  # Markdown narrative
    data_summary: dict
    operator: str
    date_range: str
    generated_at: str


class CategorizeRequest(BaseModel):
    incident_ids: list[int] | None = None
    operator: str | None = Field(default=None, max_length=200)
    year_start: int | None = Field(default=None, ge=1950, le=2100)
    year_end: int | None = Field(default=None, ge=1950, le=2100)
    batch_size: int = Field(default=50, ge=1, le=200)
    force: bool = False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_ai_available():
    """Raise 503 if AI features are not available."""
    service = get_claude_service()
    if not service.is_available:
        raise HTTPException(
            status_code=503,
            detail={"error": "AI features are not currently available. Please try again later."},
        )
    return service


def _build_data_summary(db: Session, req: TrendAnalysisRequest) -> dict:
    """Build aggregated data summary for trend analysis prompt."""
    query = db.query(Incident)

    if req.operator:
        query = query.filter(Incident.OPERATOR_NAME == req.operator)
    if req.year_start:
        query = query.filter(Incident.YEAR >= req.year_start)
    if req.year_end:
        query = query.filter(Incident.YEAR <= req.year_end)
    if req.incident_types:
        query = query.filter(Incident.INCIDENT_TYPE.in_(req.incident_types))
    if req.water_depth_min:
        query = query.filter(Incident.WATER_DEPTH >= req.water_depth_min)
    if req.water_depth_max:
        query = query.filter(Incident.WATER_DEPTH <= req.water_depth_max)

    incidents = query.all()

    if not incidents:
        return {"total_incidents": 0, "message": "No incidents match the filter criteria."}

    # Convert to DataFrame for analysis
    data = [{
        "year": i.YEAR,
        "type": i.INCIDENT_TYPE,
        "cause": i.CAUSE_OF_LOSS,
        "water_depth": i.WATER_DEPTH,
        "injuries": i.INJ_COUNT or 0,
        "fatalities": i.FATALITY_COUNT or 0,
        "fire": i.FIRE_EXPLOSION,
        "pollution": i.POLLUTION,
    } for i in incidents]

    df = pd.DataFrame(data)

    # Aggregate stats
    by_year = df.groupby("year").size().to_dict()
    by_type = df["type"].value_counts().head(10).to_dict()
    by_cause = df["cause"].value_counts().head(10).to_dict()

    # YoY change
    years_sorted = sorted(by_year.keys())
    yoy_changes = {}
    for i in range(1, len(years_sorted)):
        prev = by_year[years_sorted[i - 1]]
        curr = by_year[years_sorted[i]]
        pct = ((curr - prev) / prev * 100) if prev > 0 else 0
        yoy_changes[years_sorted[i]] = round(pct, 1)

    total_injuries = int(df["injuries"].sum())
    total_fatalities = int(df["fatalities"].sum())
    fire_count = int((df["fire"] == "Y").sum())
    pollution_count = int((df["pollution"] == "Y").sum())

    # GoM average for context
    gom_total = db.query(func.count(Incident.id)).scalar()
    gom_operators = db.query(func.count(distinct(Incident.OPERATOR_NAME))).scalar()

    return {
        "total_incidents": len(incidents),
        "incidents_by_year": by_year,
        "incidents_by_type": by_type,
        "incidents_by_cause": by_cause,
        "yoy_changes": yoy_changes,
        "total_injuries": total_injuries,
        "total_fatalities": total_fatalities,
        "fire_explosion_count": fire_count,
        "pollution_count": pollution_count,
        "gom_total_incidents": gom_total,
        "gom_total_operators": gom_operators,
    }


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/analyze/trends")
async def analyze_trends(req: TrendAnalysisRequest, db: Session = Depends(get_db)):
    """AI trend analysis — generates a narrative briefing from safety data."""
    claude = _check_ai_available()

    # Build data summary
    data_summary = _build_data_summary(db, req)

    if data_summary.get("total_incidents", 0) == 0:
        return {
            "data": {
                "briefing": "No incidents found matching the specified filters. Please broaden your search criteria.",
                "data_summary": data_summary,
                "operator": req.operator or "All GoM",
                "date_range": f"{req.year_start or 'All'} – {req.year_end or 'All'}",
                "generated_at": datetime.now(timezone.utc).isoformat(),
            },
            "meta": {"status": "no_data"},
        }

    # Build prompt
    operator_name = req.operator or "All GoM Operators"
    date_range = f"{req.year_start or 'earliest'} – {req.year_end or 'latest'}"
    filter_context = []
    if req.incident_types:
        filter_context.append(f"Incident types: {', '.join(req.incident_types)}")
    if req.water_depth_min or req.water_depth_max:
        depth_str = f"Water depth: {req.water_depth_min or 0}–{req.water_depth_max or '∞'} ft"
        filter_context.append(depth_str)

    user_prompt = TREND_ANALYSIS_USER.format(
        operator_name=operator_name,
        date_range=date_range,
        filter_context="; ".join(filter_context) if filter_context else "None (all data)",
        data_summary=json.dumps(data_summary, indent=2),
    )

    try:
        briefing = await claude.generate(
            system_prompt=TREND_ANALYSIS_SYSTEM,
            user_prompt=user_prompt,
            max_tokens=2048,
            temperature=0.4,
        )
    except ClaudeServiceError as e:
        logger.error("Trend analysis AI error: %s", e)
        raise HTTPException(
            status_code=502,
            detail={"error": "AI analysis temporarily unavailable. Please try again."},
        )

    return {
        "data": TrendAnalysisResponse(
            briefing=briefing,
            data_summary=data_summary,
            operator=operator_name,
            date_range=date_range,
            generated_at=datetime.now(timezone.utc).isoformat(),
        ).model_dump(),
        "meta": {"status": "ok", "tokens_used": token_tracker.summary},
    }


@router.post("/analyze/categorize")
async def analyze_categorize(req: CategorizeRequest, db: Session = Depends(get_db)):
    """AI root cause categorization — batch-classify incidents."""
    claude = _check_ai_available()

    # Build query for incidents to categorize
    query = db.query(Incident)

    if req.incident_ids:
        query = query.filter(Incident.INCIDENT_ID.in_(req.incident_ids))
    else:
        if req.operator:
            query = query.filter(Incident.OPERATOR_NAME == req.operator)
        if req.year_start:
            query = query.filter(Incident.YEAR >= req.year_start)
        if req.year_end:
            query = query.filter(Incident.YEAR <= req.year_end)

    incidents = query.all()

    if not incidents:
        return {"data": {"categorized": 0, "skipped": 0, "summary": {}}, "meta": {"status": "no_data"}}

    # Filter out already-categorized incidents (unless force=True)
    if not req.force:
        existing_ids = set(
            row[0] for row in
            db.query(IncidentRootCause.incident_id).filter(
                IncidentRootCause.incident_id.in_([i.INCIDENT_ID for i in incidents])
            ).all()
        )
        incidents = [i for i in incidents if i.INCIDENT_ID not in existing_ids]
        skipped = len(existing_ids)
    else:
        skipped = 0
        # Delete existing categorizations for force re-run
        if req.incident_ids:
            db.query(IncidentRootCause).filter(
                IncidentRootCause.incident_id.in_([i.INCIDENT_ID for i in incidents])
            ).delete(synchronize_session=False)

    if not incidents:
        return {
            "data": {"categorized": 0, "skipped": skipped, "summary": {}},
            "meta": {"status": "all_categorized"},
        }

    # Batch process
    valid_causes = {
        "equipment_failure", "human_error", "procedural_gap", "weather_event",
        "corrosion", "design_flaw", "maintenance_failure", "communication_failure",
        "third_party", "unknown",
    }

    total_categorized = 0
    cause_counts: dict[str, int] = {}
    confidence_sum = 0.0

    for batch_start in range(0, len(incidents), req.batch_size):
        batch = incidents[batch_start:batch_start + req.batch_size]

        # Format incident descriptions for the prompt
        descriptions = "\n\n".join(
            f"Incident ID: {inc.INCIDENT_ID}\n"
            f"Type: {inc.INCIDENT_TYPE}\n"
            f"Cause: {inc.CAUSE_OF_LOSS}\n"
            f"Description: {inc.DESCRIPTION or 'No description available'}"
            for inc in batch
        )

        user_prompt = ROOT_CAUSE_USER.format(
            count=len(batch),
            incident_descriptions=descriptions,
        )

        try:
            result = await claude.generate_json(
                system_prompt=ROOT_CAUSE_SYSTEM,
                user_prompt=user_prompt,
                max_tokens=4096,
            )
        except ClaudeServiceError as e:
            logger.error("Categorization batch failed: %s", e)
            continue

        # Handle both list and dict responses
        if isinstance(result, dict):
            classifications = result.get("classifications", result.get("incidents", [result]))
        elif isinstance(result, list):
            classifications = result
        else:
            logger.error("Unexpected categorization response type: %s", type(result))
            continue

        # Store results
        now = datetime.now(timezone.utc).isoformat()
        for cls in classifications:
            incident_id = cls.get("incident_id")
            primary = cls.get("primary_cause", "unknown")
            root_causes = cls.get("root_causes", [primary])
            confidence = cls.get("confidence", 0.5)
            reasoning = cls.get("reasoning", "")

            # Validate primary cause
            if primary not in valid_causes:
                primary = "unknown"
            root_causes = [c for c in root_causes if c in valid_causes] or ["unknown"]

            # Upsert categorization
            existing = db.query(IncidentRootCause).filter_by(incident_id=incident_id).first()
            if existing:
                existing.primary_cause = primary
                existing.root_causes = root_causes
                existing.confidence = confidence
                existing.reasoning = reasoning
                existing.categorized_at = now
            else:
                db.add(IncidentRootCause(
                    incident_id=incident_id,
                    primary_cause=primary,
                    root_causes=root_causes,
                    confidence=confidence,
                    reasoning=reasoning,
                    categorized_at=now,
                ))

            total_categorized += 1
            cause_counts[primary] = cause_counts.get(primary, 0) + 1
            confidence_sum += confidence

    db.commit()

    avg_confidence = round(confidence_sum / total_categorized, 2) if total_categorized > 0 else 0

    return {
        "data": {
            "categorized": total_categorized,
            "skipped": skipped,
            "summary": cause_counts,
            "average_confidence": avg_confidence,
        },
        "meta": {"status": "ok", "tokens_used": token_tracker.summary},
    }


@router.get("/analyze/root-causes")
async def get_root_cause_summary(
    operator: Optional[str] = None,
    year_start: Optional[int] = None,
    year_end: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """Get aggregated root cause breakdown for the dashboard chart."""
    query = (
        db.query(
            IncidentRootCause.primary_cause,
            func.count(IncidentRootCause.id).label("count"),
            func.avg(IncidentRootCause.confidence).label("avg_confidence"),
        )
        .join(Incident, Incident.INCIDENT_ID == IncidentRootCause.incident_id)
    )

    if operator:
        query = query.filter(Incident.OPERATOR_NAME == operator)
    if year_start:
        query = query.filter(Incident.YEAR >= year_start)
    if year_end:
        query = query.filter(Incident.YEAR <= year_end)

    query = query.group_by(IncidentRootCause.primary_cause).order_by(
        func.count(IncidentRootCause.id).desc()
    )

    results = query.all()

    return {
        "data": [
            {
                "cause": row.primary_cause,
                "count": row.count,
                "avg_confidence": round(row.avg_confidence, 2) if row.avg_confidence else 0,
            }
            for row in results
        ],
        "meta": {"total": sum(r.count for r in results)},
    }
