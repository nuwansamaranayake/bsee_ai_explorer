"""Incidents router — filtered incident data with pagination and root cause join."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.database import get_db
from models.tables import Incident, IncidentRootCause

router = APIRouter()


@router.get("/incidents")
async def list_incidents(
    operator: Optional[str] = Query(None, description="Filter by operator name"),
    year_start: Optional[int] = Query(None, description="Start year (inclusive)"),
    year_end: Optional[int] = Query(None, description="End year (inclusive)"),
    incident_type: Optional[str] = Query(None, description="Filter by INCIDENT_TYPE"),
    cause: Optional[str] = Query(None, description="Filter by CAUSE_OF_LOSS"),
    water_depth_min: Optional[float] = Query(None, description="Min water depth (ft)"),
    water_depth_max: Optional[float] = Query(None, description="Max water depth (ft)"),
    root_cause: Optional[str] = Query(None, description="Filter by AI-assigned primary root cause"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List incidents with dynamic filters and pagination.

    When `root_cause` is provided, performs a LEFT JOIN with the
    incident_root_causes table and filters on primary_cause.
    """

    # Base query — always select incident fields
    need_root_cause_join = root_cause is not None

    if need_root_cause_join:
        query = (
            db.query(Incident, IncidentRootCause)
            .outerjoin(
                IncidentRootCause,
                Incident.INCIDENT_ID == IncidentRootCause.incident_id,
            )
        )
    else:
        query = db.query(Incident)

    # Apply filters
    if operator:
        query = query.filter(Incident.OPERATOR_NAME == operator)
    if year_start is not None:
        query = query.filter(Incident.YEAR >= year_start)
    if year_end is not None:
        query = query.filter(Incident.YEAR <= year_end)
    if incident_type:
        query = query.filter(Incident.INCIDENT_TYPE == incident_type)
    if cause:
        query = query.filter(Incident.CAUSE_OF_LOSS == cause)
    if water_depth_min is not None:
        query = query.filter(Incident.WATER_DEPTH >= water_depth_min)
    if water_depth_max is not None:
        query = query.filter(Incident.WATER_DEPTH <= water_depth_max)
    if root_cause:
        query = query.filter(IncidentRootCause.primary_cause == root_cause)

    # Total count (before pagination)
    if need_root_cause_join:
        count_query = (
            db.query(func.count(Incident.id))
            .outerjoin(
                IncidentRootCause,
                Incident.INCIDENT_ID == IncidentRootCause.incident_id,
            )
        )
        # Re-apply filters to count query
        if operator:
            count_query = count_query.filter(Incident.OPERATOR_NAME == operator)
        if year_start is not None:
            count_query = count_query.filter(Incident.YEAR >= year_start)
        if year_end is not None:
            count_query = count_query.filter(Incident.YEAR <= year_end)
        if incident_type:
            count_query = count_query.filter(Incident.INCIDENT_TYPE == incident_type)
        if cause:
            count_query = count_query.filter(Incident.CAUSE_OF_LOSS == cause)
        if water_depth_min is not None:
            count_query = count_query.filter(Incident.WATER_DEPTH >= water_depth_min)
        if water_depth_max is not None:
            count_query = count_query.filter(Incident.WATER_DEPTH <= water_depth_max)
        if root_cause:
            count_query = count_query.filter(IncidentRootCause.primary_cause == root_cause)
        total = count_query.scalar()
    else:
        total = query.count()

    # Order, paginate
    query = query.order_by(Incident.YEAR.desc(), Incident.INCIDENT_ID.desc())
    query = query.offset(offset).limit(limit)

    rows = query.all()

    # Serialize
    data = []
    for row in rows:
        if need_root_cause_join:
            incident, rc = row
        else:
            incident = row
            rc = None

        record = {
            "incident_id": incident.INCIDENT_ID,
            "incident_date": incident.INCIDENT_DATE,
            "operator_name": incident.OPERATOR_NAME,
            "operator_num": incident.OPERATOR_NUM,
            "area_name": incident.AREA_NAME,
            "block_number": incident.BLOCK_NUMBER,
            "water_depth": incident.WATER_DEPTH,
            "facility_type": incident.FACILITY_TYPE,
            "platform_name": incident.PLATFORM_NAME,
            "inj_type": incident.INJ_TYPE,
            "inj_count": incident.INJ_COUNT,
            "fatality_count": incident.FATALITY_COUNT,
            "fire_explosion": incident.FIRE_EXPLOSION,
            "pollution": incident.POLLUTION,
            "loss_well_control": incident.LOSS_WELL_CONTROL,
            "incident_type": incident.INCIDENT_TYPE,
            "cause_of_loss": incident.CAUSE_OF_LOSS,
            "description": incident.DESCRIPTION,
            "district": incident.DISTRICT,
            "year": incident.YEAR,
        }

        if rc is not None:
            record["root_cause"] = {
                "primary_cause": rc.primary_cause,
                "root_causes": rc.root_causes,
                "confidence": rc.confidence,
                "reasoning": rc.reasoning,
            }
        elif need_root_cause_join:
            record["root_cause"] = None

        data.append(record)

    page = (offset // limit) + 1 if limit > 0 else 1

    return {
        "data": data,
        "meta": {
            "total": total,
            "page": page,
            "limit": limit,
        },
    }
