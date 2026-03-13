"""Platforms router — platform/facility data with INC counts and filtering."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.database import get_db
from models.tables import Platform, INC

router = APIRouter()


@router.get("/platforms")
async def list_platforms(
    operator: Optional[str] = Query(None, description="Filter by operator name"),
    status: Optional[str] = Query(None, description="Filter by platform status (Active, Removed, etc.)"),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List platforms with INC (violation) counts attached.

    Each platform record includes the count of INCs matched by
    PLATFORM_NAME and OPERATOR_NAME.
    """

    # Subquery: INC counts per (operator, platform)
    inc_counts = (
        db.query(
            INC.OPERATOR_NAME,
            INC.PLATFORM_NAME,
            func.count(INC.INC_ID).label("inc_count"),
        )
        .group_by(INC.OPERATOR_NAME, INC.PLATFORM_NAME)
        .subquery()
    )

    # Main query with LEFT JOIN to INC counts
    query = (
        db.query(
            Platform,
            func.coalesce(inc_counts.c.inc_count, 0).label("inc_count"),
        )
        .outerjoin(
            inc_counts,
            (Platform.OPERATOR_NAME == inc_counts.c.OPERATOR_NAME)
            & (Platform.PLATFORM_NAME == inc_counts.c.PLATFORM_NAME),
        )
    )

    # Apply filters
    if operator:
        query = query.filter(Platform.OPERATOR_NAME == operator)
    if status:
        query = query.filter(Platform.STATUS == status)

    # Total count before pagination
    count_query = db.query(func.count(Platform.id))
    if operator:
        count_query = count_query.filter(Platform.OPERATOR_NAME == operator)
    if status:
        count_query = count_query.filter(Platform.STATUS == status)
    total = count_query.scalar()

    # Order and paginate
    query = query.order_by(Platform.OPERATOR_NAME, Platform.PLATFORM_NAME)
    query = query.offset(offset).limit(limit)

    rows = query.all()

    data = []
    for platform, inc_count in rows:
        data.append({
            "platform_id": platform.PLATFORM_ID,
            "platform_name": platform.PLATFORM_NAME,
            "operator_name": platform.OPERATOR_NAME,
            "area_name": platform.AREA_NAME,
            "block_number": platform.BLOCK_NUMBER,
            "water_depth": platform.WATER_DEPTH,
            "facility_type": platform.FACILITY_TYPE,
            "status": platform.STATUS,
            "install_date": platform.INSTALL_DATE,
            "removal_date": platform.REMOVAL_DATE,
            "latitude": platform.LATITUDE,
            "longitude": platform.LONGITUDE,
            "inc_count": inc_count,
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
