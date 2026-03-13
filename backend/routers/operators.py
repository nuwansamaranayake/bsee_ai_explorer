"""Operators router — list GoM operators with counts, ranking endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case, distinct
from sqlalchemy.orm import Session

from models.database import get_db
from models.tables import Incident, INC, Platform

router = APIRouter()


@router.get("/operators")
async def list_operators(db: Session = Depends(get_db)):
    """List all GoM operators with incident count, INC count, and platform count."""

    # Subquery: incident counts per operator
    incident_counts = (
        db.query(
            Incident.OPERATOR_NAME,
            func.count(Incident.INCIDENT_ID).label("incident_count"),
        )
        .group_by(Incident.OPERATOR_NAME)
        .subquery()
    )

    # Subquery: INC counts per operator
    inc_counts = (
        db.query(
            INC.OPERATOR_NAME,
            func.count(INC.INC_ID).label("inc_count"),
        )
        .group_by(INC.OPERATOR_NAME)
        .subquery()
    )

    # Subquery: platform counts per operator
    platform_counts = (
        db.query(
            Platform.OPERATOR_NAME,
            func.count(Platform.PLATFORM_ID).label("platform_count"),
        )
        .group_by(Platform.OPERATOR_NAME)
        .subquery()
    )

    # Collect all distinct operator names from all tables
    operator_names_q = (
        db.query(Incident.OPERATOR_NAME)
        .union(db.query(INC.OPERATOR_NAME))
        .union(db.query(Platform.OPERATOR_NAME))
    )

    all_operators = [row[0] for row in operator_names_q.all() if row[0] is not None]
    all_operators.sort()

    results = []
    # Build a lookup dict for each subquery for efficiency
    incident_map = {
        row.OPERATOR_NAME: row.incident_count
        for row in db.query(
            incident_counts.c.OPERATOR_NAME,
            incident_counts.c.incident_count,
        ).all()
    }
    inc_map = {
        row.OPERATOR_NAME: row.inc_count
        for row in db.query(
            inc_counts.c.OPERATOR_NAME,
            inc_counts.c.inc_count,
        ).all()
    }
    platform_map = {
        row.OPERATOR_NAME: row.platform_count
        for row in db.query(
            platform_counts.c.OPERATOR_NAME,
            platform_counts.c.platform_count,
        ).all()
    }

    for name in all_operators:
        results.append({
            "operator_name": name,
            "incident_count": incident_map.get(name, 0),
            "inc_count": inc_map.get(name, 0),
            "platform_count": platform_map.get(name, 0),
        })

    return {
        "data": results,
        "meta": {"total": len(results)},
    }


@router.get("/operators/ranking")
async def operator_ranking(
    sort_by: str = Query("total_incs", pattern="^(total_incs|inc_rate|severe_count)$"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    limit: int = Query(20, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Rank operators by INC metrics.

    sort_by options:
      - total_incs: total number of INCs
      - inc_rate: INCs per active platform
      - severe_count: number of Facility Shut-in + Component Shut-in INCs
    """

    # INC counts + severity breakdown per operator
    inc_stats = (
        db.query(
            INC.OPERATOR_NAME,
            func.count(INC.INC_ID).label("total_incs"),
            func.sum(
                case((INC.SEVERITY == "Warning", 1), else_=0)
            ).label("warning"),
            func.sum(
                case((INC.SEVERITY == "Component Shut-in", 1), else_=0)
            ).label("component_shutin"),
            func.sum(
                case((INC.SEVERITY == "Facility Shut-in", 1), else_=0)
            ).label("facility_shutin"),
        )
        .group_by(INC.OPERATOR_NAME)
        .subquery()
    )

    # Active platform counts per operator
    active_platforms = (
        db.query(
            Platform.OPERATOR_NAME,
            func.count(Platform.PLATFORM_ID).label("active_platforms"),
        )
        .filter(Platform.STATUS == "Active")
        .group_by(Platform.OPERATOR_NAME)
        .subquery()
    )

    # Join INC stats with platform counts
    query = db.query(
        inc_stats.c.OPERATOR_NAME,
        inc_stats.c.total_incs,
        inc_stats.c.warning,
        inc_stats.c.component_shutin,
        inc_stats.c.facility_shutin,
        func.coalesce(active_platforms.c.active_platforms, 0).label("active_platforms"),
    ).outerjoin(
        active_platforms,
        inc_stats.c.OPERATOR_NAME == active_platforms.c.OPERATOR_NAME,
    )

    rows = query.all()

    # Build result list with computed fields
    results = []
    for row in rows:
        total_incs = row.total_incs or 0
        active_plats = row.active_platforms or 0
        inc_rate = round(total_incs / active_plats, 4) if active_plats > 0 else 0.0
        severe_count = (row.component_shutin or 0) + (row.facility_shutin or 0)

        results.append({
            "operator_name": row.OPERATOR_NAME,
            "total_incs": total_incs,
            "inc_rate": inc_rate,
            "severe_count": severe_count,
            "active_platforms": active_plats,
            "severity_breakdown": {
                "warning": row.warning or 0,
                "component_shutin": row.component_shutin or 0,
                "facility_shutin": row.facility_shutin or 0,
            },
        })

    # Sort
    reverse = order == "desc"
    results.sort(key=lambda r: r.get(sort_by, 0), reverse=reverse)

    # Limit
    results = results[:limit]

    return {
        "data": results,
        "meta": {
            "total": len(results),
            "sort_by": sort_by,
            "order": order,
        },
    }
