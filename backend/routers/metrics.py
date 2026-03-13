"""Metrics router — production-normalized safety metrics and headline KPIs."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, distinct
from sqlalchemy.orm import Session

from models.database import get_db
from models.tables import Incident, INC, Production

# BOE conversion factor: 1 MCF gas = 0.1781 barrels oil equivalent
GAS_MCF_TO_BOE = 0.1781

router = APIRouter()


def _compute_boe_by_operator_year(db: Session, operator: Optional[str] = None,
                                   year_start: Optional[int] = None,
                                   year_end: Optional[int] = None) -> dict:
    """Return dict of {(operator, year): boe} for production data."""
    query = db.query(
        Production.OPERATOR_NAME,
        Production.YEAR,
        func.sum(Production.OIL_BBL).label("total_oil"),
        func.sum(Production.GAS_MCF).label("total_gas"),
    )
    if operator:
        query = query.filter(Production.OPERATOR_NAME == operator)
    if year_start is not None:
        query = query.filter(Production.YEAR >= year_start)
    if year_end is not None:
        query = query.filter(Production.YEAR <= year_end)

    query = query.group_by(Production.OPERATOR_NAME, Production.YEAR)
    rows = query.all()

    result = {}
    for row in rows:
        oil = row.total_oil or 0.0
        gas = row.total_gas or 0.0
        boe = oil + (gas * GAS_MCF_TO_BOE)
        result[(row.OPERATOR_NAME, row.YEAR)] = boe
    return result


def _incident_counts_by_operator_year(db: Session, operator: Optional[str] = None,
                                       year_start: Optional[int] = None,
                                       year_end: Optional[int] = None) -> dict:
    """Return dict of {(operator, year): {incidents, fatalities}}."""
    query = db.query(
        Incident.OPERATOR_NAME,
        Incident.YEAR,
        func.count(Incident.INCIDENT_ID).label("incidents"),
        func.coalesce(func.sum(Incident.FATALITY_COUNT), 0).label("fatalities"),
    )
    if operator:
        query = query.filter(Incident.OPERATOR_NAME == operator)
    if year_start is not None:
        query = query.filter(Incident.YEAR >= year_start)
    if year_end is not None:
        query = query.filter(Incident.YEAR <= year_end)

    query = query.group_by(Incident.OPERATOR_NAME, Incident.YEAR)
    rows = query.all()

    result = {}
    for row in rows:
        result[(row.OPERATOR_NAME, row.YEAR)] = {
            "incidents": row.incidents or 0,
            "fatalities": row.fatalities or 0,
        }
    return result


def _inc_counts_by_operator_year(db: Session, operator: Optional[str] = None,
                                  year_start: Optional[int] = None,
                                  year_end: Optional[int] = None) -> dict:
    """Return dict of {(operator, year): inc_count}."""
    query = db.query(
        INC.OPERATOR_NAME,
        INC.YEAR,
        func.count(INC.INC_ID).label("incs"),
    )
    if operator:
        query = query.filter(INC.OPERATOR_NAME == operator)
    if year_start is not None:
        query = query.filter(INC.YEAR >= year_start)
    if year_end is not None:
        query = query.filter(INC.YEAR <= year_end)

    query = query.group_by(INC.OPERATOR_NAME, INC.YEAR)
    rows = query.all()

    result = {}
    for row in rows:
        result[(row.OPERATOR_NAME, row.YEAR)] = row.incs or 0
    return result


@router.get("/metrics/normalized")
async def normalized_metrics(
    operator: Optional[str] = Query(None, description="Filter by operator (GoM-wide if omitted)"),
    year_start: Optional[int] = Query(None, description="Start year (inclusive)"),
    year_end: Optional[int] = Query(None, description="End year (inclusive)"),
    db: Session = Depends(get_db),
):
    """Production-normalized safety metrics per operator per year.

    Returns incidents_per_million_boe, incs_per_million_boe, and
    fatalities_per_million_boe. Also returns GoM-wide averages for benchmarking.
    """

    boe_data = _compute_boe_by_operator_year(db, operator, year_start, year_end)
    incident_data = _incident_counts_by_operator_year(db, operator, year_start, year_end)
    inc_data = _inc_counts_by_operator_year(db, operator, year_start, year_end)

    # Collect all (operator, year) keys across all datasets
    all_keys = set(boe_data.keys()) | set(incident_data.keys()) | set(inc_data.keys())

    # Build per-operator-year records
    records = []
    for key in sorted(all_keys):
        op_name, year = key
        boe = boe_data.get(key, 0.0)
        inc_info = incident_data.get(key, {"incidents": 0, "fatalities": 0})
        incs = inc_data.get(key, 0)
        million_boe = boe / 1_000_000 if boe > 0 else 0.0

        records.append({
            "operator_name": op_name,
            "year": year,
            "total_boe": round(boe, 2),
            "incidents": inc_info["incidents"],
            "fatalities": inc_info["fatalities"],
            "incs": incs,
            "incidents_per_million_boe": round(inc_info["incidents"] / million_boe, 4) if million_boe > 0 else 0.0,
            "incs_per_million_boe": round(incs / million_boe, 4) if million_boe > 0 else 0.0,
            "fatalities_per_million_boe": round(inc_info["fatalities"] / million_boe, 4) if million_boe > 0 else 0.0,
        })

    # GoM-wide averages (always computed unfiltered by operator for benchmarking)
    gom_boe = _compute_boe_by_operator_year(db, None, year_start, year_end)
    gom_incidents = _incident_counts_by_operator_year(db, None, year_start, year_end)
    gom_incs = _inc_counts_by_operator_year(db, None, year_start, year_end)

    total_gom_boe = sum(gom_boe.values())
    total_gom_incidents = sum(v["incidents"] for v in gom_incidents.values())
    total_gom_fatalities = sum(v["fatalities"] for v in gom_incidents.values())
    total_gom_incs = sum(gom_incs.values())
    gom_million_boe = total_gom_boe / 1_000_000 if total_gom_boe > 0 else 0.0

    gom_averages = {
        "total_boe": round(total_gom_boe, 2),
        "total_incidents": total_gom_incidents,
        "total_incs": total_gom_incs,
        "total_fatalities": total_gom_fatalities,
        "incidents_per_million_boe": round(total_gom_incidents / gom_million_boe, 4) if gom_million_boe > 0 else 0.0,
        "incs_per_million_boe": round(total_gom_incs / gom_million_boe, 4) if gom_million_boe > 0 else 0.0,
        "fatalities_per_million_boe": round(total_gom_fatalities / gom_million_boe, 4) if gom_million_boe > 0 else 0.0,
    }

    return {
        "data": records,
        "meta": {
            "total": len(records),
            "gom_averages": gom_averages,
            "operator": operator or "all",
        },
    }


@router.get("/metrics/summary")
async def metrics_summary(
    operator: Optional[str] = Query(None, description="Filter by operator (GoM-wide if omitted)"),
    db: Session = Depends(get_db),
):
    """Four headline KPIs with year-over-year change.

    Returns total_incidents, total_incs, total_production_boe, and
    incidents_per_million_boe, each with yoy_change percentage and direction.
    """

    # Determine the latest two years present in the data
    latest_year_q = db.query(func.max(Incident.YEAR)).scalar()
    if latest_year_q is None:
        return {
            "data": {
                "total_incidents": _empty_kpi(0),
                "total_incs": _empty_kpi(0),
                "total_production_boe": _empty_kpi(0.0),
                "incidents_per_million_boe": _empty_kpi(0.0),
            },
            "meta": {"operator": operator or "GoM-wide", "latest_year": None},
        }

    latest_year = latest_year_q
    prev_year = latest_year - 1

    # --- Current year totals ---
    current_incidents = _count_incidents_for_year(db, latest_year, operator)
    current_incs = _count_incs_for_year(db, latest_year, operator)
    current_boe = _total_boe_for_year(db, latest_year, operator)
    current_fatalities = _count_fatalities_for_year(db, latest_year, operator)

    # --- Previous year totals ---
    prev_incidents = _count_incidents_for_year(db, prev_year, operator)
    prev_incs = _count_incs_for_year(db, prev_year, operator)
    prev_boe = _total_boe_for_year(db, prev_year, operator)

    # --- Rates ---
    current_million_boe = current_boe / 1_000_000 if current_boe > 0 else 0.0
    prev_million_boe = prev_boe / 1_000_000 if prev_boe > 0 else 0.0

    current_rate = round(current_incidents / current_million_boe, 4) if current_million_boe > 0 else 0.0
    prev_rate = round(prev_incidents / prev_million_boe, 4) if prev_million_boe > 0 else 0.0

    return {
        "data": {
            "total_incidents": _build_kpi(current_incidents, prev_incidents),
            "total_incs": _build_kpi(current_incs, prev_incs),
            "total_production_boe": _build_kpi(round(current_boe, 2), round(prev_boe, 2)),
            "incidents_per_million_boe": _build_kpi(current_rate, prev_rate),
        },
        "meta": {
            "operator": operator or "GoM-wide",
            "latest_year": latest_year,
            "compared_to": prev_year,
        },
    }


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _count_incidents_for_year(db: Session, year: int, operator: Optional[str]) -> int:
    query = db.query(func.count(Incident.INCIDENT_ID)).filter(Incident.YEAR == year)
    if operator:
        query = query.filter(Incident.OPERATOR_NAME == operator)
    return query.scalar() or 0


def _count_fatalities_for_year(db: Session, year: int, operator: Optional[str]) -> int:
    query = db.query(func.coalesce(func.sum(Incident.FATALITY_COUNT), 0)).filter(Incident.YEAR == year)
    if operator:
        query = query.filter(Incident.OPERATOR_NAME == operator)
    return query.scalar() or 0


def _count_incs_for_year(db: Session, year: int, operator: Optional[str]) -> int:
    query = db.query(func.count(INC.INC_ID)).filter(INC.YEAR == year)
    if operator:
        query = query.filter(INC.OPERATOR_NAME == operator)
    return query.scalar() or 0


def _total_boe_for_year(db: Session, year: int, operator: Optional[str]) -> float:
    query = db.query(
        func.sum(Production.OIL_BBL).label("oil"),
        func.sum(Production.GAS_MCF).label("gas"),
    ).filter(Production.YEAR == year)
    if operator:
        query = query.filter(Production.OPERATOR_NAME == operator)
    row = query.first()
    if row is None:
        return 0.0
    oil = row.oil or 0.0
    gas = row.gas or 0.0
    return oil + (gas * GAS_MCF_TO_BOE)


def _build_kpi(current_value, prev_value) -> dict:
    """Build a KPI dict with yoy_change and direction."""
    if prev_value and prev_value != 0:
        yoy_change = round(((current_value - prev_value) / abs(prev_value)) * 100, 2)
    else:
        yoy_change = 0.0

    if yoy_change > 0:
        direction = "up"
    elif yoy_change < 0:
        direction = "down"
    else:
        direction = "flat"

    return {
        "value": current_value,
        "yoy_change": yoy_change,
        "direction": direction,
    }


def _empty_kpi(value) -> dict:
    """Return a KPI dict with no change data."""
    return {
        "value": value,
        "yoy_change": 0.0,
        "direction": "flat",
    }
