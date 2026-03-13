"""INCs (Incidents of Non-Compliance) router — violations data with filtering,
pagination, and summary aggregation endpoint."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from models.database import get_db
from models.tables import INC

router = APIRouter()


@router.get("/incs")
async def list_incs(
    operator: Optional[str] = Query(None, description="Filter by operator name"),
    severity: Optional[str] = Query(None, description="Filter by severity level"),
    component: Optional[str] = Query(None, description="Filter by COMPONENT_CODE"),
    year_start: Optional[int] = Query(None, description="Start year (inclusive)"),
    year_end: Optional[int] = Query(None, description="End year (inclusive)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List INCs (violations) with dynamic filters and pagination."""

    query = db.query(INC)

    # Apply filters
    if operator:
        query = query.filter(INC.OPERATOR_NAME == operator)
    if severity:
        query = query.filter(INC.SEVERITY == severity)
    if component:
        query = query.filter(INC.COMPONENT_CODE == component)
    if year_start is not None:
        query = query.filter(INC.YEAR >= year_start)
    if year_end is not None:
        query = query.filter(INC.YEAR <= year_end)

    # Total count before pagination
    total = query.count()

    # Order and paginate
    query = query.order_by(INC.YEAR.desc(), INC.INC_ID.desc())
    query = query.offset(offset).limit(limit)

    rows = query.all()

    data = []
    for inc in rows:
        data.append({
            "inc_id": inc.INC_ID,
            "inc_date": inc.INC_DATE,
            "operator_name": inc.OPERATOR_NAME,
            "area_name": inc.AREA_NAME,
            "block_number": inc.BLOCK_NUMBER,
            "water_depth": inc.WATER_DEPTH,
            "platform_name": inc.PLATFORM_NAME,
            "component_code": inc.COMPONENT_CODE,
            "component_desc": inc.COMPONENT_DESC,
            "severity": inc.SEVERITY,
            "inc_type": inc.INC_TYPE,
            "description": inc.DESCRIPTION,
            "year": inc.YEAR,
        })

    page = (offset // limit) + 1 if limit > 0 else 1

    return {
        "data": data,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
        },
    }


@router.get("/incs/summary")
async def incs_summary(
    operator: Optional[str] = Query(None, description="Filter by operator (GoM-wide if omitted)"),
    db: Session = Depends(get_db),
):
    """Aggregated INC stats: totals, by severity, by component, by year, and GoM average rate."""

    base_query = db.query(INC)
    if operator:
        base_query = base_query.filter(INC.OPERATOR_NAME == operator)

    # Total violations
    total_violations = base_query.count()

    # By severity
    severity_rows = (
        base_query
        .with_entities(INC.SEVERITY, func.count(INC.INC_ID).label("count"))
        .group_by(INC.SEVERITY)
        .all()
    )
    by_severity = {row.SEVERITY: row.count for row in severity_rows if row.SEVERITY is not None}
    # Ensure all three levels are present
    for level in ["Warning", "Component Shut-in", "Facility Shut-in"]:
        by_severity.setdefault(level, 0)

    # By component (top components)
    component_rows = (
        base_query
        .with_entities(
            INC.COMPONENT_DESC,
            func.count(INC.INC_ID).label("count"),
        )
        .group_by(INC.COMPONENT_DESC)
        .order_by(func.count(INC.INC_ID).desc())
        .all()
    )
    by_component = [
        {"component": row.COMPONENT_DESC or "Unknown", "count": row.count}
        for row in component_rows
    ]

    # By year
    year_rows = (
        base_query
        .with_entities(INC.YEAR, func.count(INC.INC_ID).label("count"))
        .group_by(INC.YEAR)
        .order_by(INC.YEAR)
        .all()
    )
    by_year = [{"year": row.YEAR, "count": row.count} for row in year_rows]

    # GoM average rate: total INCs / total distinct operators (GoM-wide)
    total_incs_gom = db.query(func.count(INC.INC_ID)).scalar() or 0
    total_operators_gom = db.query(func.count(distinct(INC.OPERATOR_NAME))).scalar() or 1
    gom_average_rate = round(total_incs_gom / total_operators_gom, 2) if total_operators_gom > 0 else 0.0

    return {
        "data": {
            "total_violations": total_violations,
            "by_severity": by_severity,
            "by_component": by_component,
            "by_year": by_year,
            "gom_average_rate": gom_average_rate,
        },
        "meta": {
            "operator": operator or "GoM-wide",
        },
    }
