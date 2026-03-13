"""INCs (Incidents of Non-Compliance) router — violations data with filtering,
pagination, summary aggregation, and operator ranking endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, distinct, case, literal
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
    """Aggregated INC stats matching frontend INCSummaryData interface.

    Returns: total_incs, gom_average, percentile_rank, severity_breakdown,
    by_year, gom_by_year, top_components.
    """

    base_query = db.query(INC)
    if operator:
        base_query = base_query.filter(INC.OPERATOR_NAME == operator)

    # Total INCs for this operator (or GoM-wide)
    total_incs = base_query.count()

    # --- GoM-wide averages ---
    total_incs_gom = db.query(func.count(INC.INC_ID)).scalar() or 0
    total_operators_gom = db.query(func.count(distinct(INC.OPERATOR_NAME))).scalar() or 1
    gom_average = round(total_incs_gom / total_operators_gom, 2)

    # --- Percentile rank ---
    # Count how many operators have MORE INCs than the current selection
    if operator:
        # Subquery: INC count per operator
        op_counts = (
            db.query(
                INC.OPERATOR_NAME,
                func.count(INC.INC_ID).label("cnt"),
            )
            .group_by(INC.OPERATOR_NAME)
            .subquery()
        )
        operators_with_more = (
            db.query(func.count())
            .select_from(op_counts)
            .filter(op_counts.c.cnt > total_incs)
            .scalar()
        ) or 0
        percentile_rank = round((operators_with_more / total_operators_gom) * 100, 1)
    else:
        percentile_rank = 50.0  # GoM-wide is the median by definition

    # --- Severity breakdown (array of {severity, count}) ---
    severity_rows = (
        base_query
        .with_entities(INC.SEVERITY, func.count(INC.INC_ID).label("count"))
        .group_by(INC.SEVERITY)
        .all()
    )
    severity_map = {row.SEVERITY: row.count for row in severity_rows if row.SEVERITY}
    for level in ["Warning", "Component Shut-in", "Facility Shut-in"]:
        severity_map.setdefault(level, 0)
    severity_breakdown = [
        {"severity": sev, "count": cnt}
        for sev, cnt in severity_map.items()
    ]

    # --- By year (operator or GoM-wide) ---
    year_rows = (
        base_query
        .with_entities(INC.YEAR, func.count(INC.INC_ID).label("count"))
        .group_by(INC.YEAR)
        .order_by(INC.YEAR)
        .all()
    )
    by_year = [{"year": row.YEAR, "count": row.count} for row in year_rows]

    # --- GoM-wide by year (average per operator per year) ---
    gom_year_rows = (
        db.query(INC.YEAR, func.count(INC.INC_ID).label("total"))
        .group_by(INC.YEAR)
        .order_by(INC.YEAR)
        .all()
    )
    gom_by_year = [
        {"year": row.YEAR, "count": round(row.total / total_operators_gom, 1)}
        for row in gom_year_rows
    ]

    # --- Top components (array of {component, count}) ---
    component_rows = (
        base_query
        .with_entities(
            INC.COMPONENT_DESC,
            func.count(INC.INC_ID).label("count"),
        )
        .group_by(INC.COMPONENT_DESC)
        .order_by(func.count(INC.INC_ID).desc())
        .limit(10)
        .all()
    )
    top_components = [
        {"component": row.COMPONENT_DESC or "Unknown", "count": row.count}
        for row in component_rows
    ]

    return {
        "data": {
            "total_incs": total_incs,
            "gom_average": gom_average,
            "percentile_rank": percentile_rank,
            "severity_breakdown": severity_breakdown,
            "by_year": by_year,
            "gom_by_year": gom_by_year,
            "top_components": top_components,
        },
        "meta": {
            "operator": operator or "GoM-wide",
        },
    }


@router.get("/incs/operator-ranking")
async def operator_ranking(
    sort_by: str = Query("total_incs", description="Sort column: operator, total_incs, inc_rate, severe_count"),
    order: str = Query("desc", description="Sort order: asc or desc"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Results per page"),
    db: Session = Depends(get_db),
):
    """Ranked list of operators by violation metrics with pagination."""

    # Compute per-operator metrics
    severe_case = case(
        (INC.SEVERITY == "Facility Shut-in", literal(1)),
        else_=literal(0),
    )

    op_stats = (
        db.query(
            INC.OPERATOR_NAME.label("operator"),
            func.count(INC.INC_ID).label("total_incs"),
            func.sum(severe_case).label("severe_count"),
        )
        .group_by(INC.OPERATOR_NAME)
        .subquery()
    )

    # Count distinct years per operator to compute INC rate (INCs per year)
    op_years = (
        db.query(
            INC.OPERATOR_NAME.label("operator"),
            func.count(distinct(INC.YEAR)).label("active_years"),
        )
        .group_by(INC.OPERATOR_NAME)
        .subquery()
    )

    # Join stats with years
    from sqlalchemy import cast, Float
    query = (
        db.query(
            op_stats.c.operator,
            op_stats.c.total_incs,
            op_stats.c.severe_count,
            (cast(op_stats.c.total_incs, Float) / func.coalesce(op_years.c.active_years, literal(1))).label("inc_rate"),
        )
        .outerjoin(op_years, op_stats.c.operator == op_years.c.operator)
    )

    # Total count for pagination
    total = query.count()

    # Sort
    sort_column_map = {
        "operator": op_stats.c.operator,
        "total_incs": op_stats.c.total_incs,
        "inc_rate": "inc_rate",
        "severe_count": op_stats.c.severe_count,
    }
    sort_col = sort_column_map.get(sort_by, op_stats.c.total_incs)

    if sort_col == "inc_rate":
        # Can't use label directly in ORDER BY with SQLAlchemy easily,
        # so use the expression
        sort_expr = cast(op_stats.c.total_incs, Float) / func.coalesce(op_years.c.active_years, literal(1))
    else:
        sort_expr = sort_col

    if order == "asc":
        query = query.order_by(sort_expr.asc())
    else:
        query = query.order_by(sort_expr.desc())

    # Paginate
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)

    rows = query.all()

    data = [
        {
            "operator": row.operator,
            "total_incs": row.total_incs,
            "inc_rate": round(float(row.inc_rate), 2) if row.inc_rate else 0.0,
            "severe_count": row.severe_count or 0,
        }
        for row in rows
    ]

    total_pages = max(1, (total + page_size - 1) // page_size)

    return {
        "data": data,
        "meta": {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        },
    }
