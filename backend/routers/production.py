"""Production router — yearly BOE totals per operator with filtering."""

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.database import get_db
from models.tables import Production

# BOE conversion factor: 1 MCF gas = 0.1781 barrels oil equivalent
GAS_MCF_TO_BOE = 0.1781

router = APIRouter()


@router.get("/production")
async def list_production(
    operator: Optional[str] = Query(None, description="Filter by operator name"),
    year_start: Optional[int] = Query(None, description="Start year (inclusive)"),
    year_end: Optional[int] = Query(None, description="End year (inclusive)"),
    db: Session = Depends(get_db),
):
    """Return yearly BOE totals per operator.

    BOE = OIL_BBL + (GAS_MCF * 0.1781)
    Groups production by operator and year, summing OIL_BBL and GAS_MCF
    before converting to BOE.
    """

    query = db.query(
        Production.OPERATOR_NAME,
        Production.YEAR,
        func.sum(Production.OIL_BBL).label("total_oil_bbl"),
        func.sum(Production.GAS_MCF).label("total_gas_mcf"),
        func.sum(Production.WATER_BBL).label("total_water_bbl"),
        func.sum(Production.DAYS_ON).label("total_days_on"),
    )

    # Apply filters
    if operator:
        query = query.filter(Production.OPERATOR_NAME == operator)
    if year_start is not None:
        query = query.filter(Production.YEAR >= year_start)
    if year_end is not None:
        query = query.filter(Production.YEAR <= year_end)

    query = query.group_by(Production.OPERATOR_NAME, Production.YEAR)
    query = query.order_by(Production.OPERATOR_NAME, Production.YEAR)

    rows = query.all()

    data = []
    for row in rows:
        oil = row.total_oil_bbl or 0.0
        gas = row.total_gas_mcf or 0.0
        boe = round(oil + (gas * GAS_MCF_TO_BOE), 2)
        data.append({
            "operator_name": row.OPERATOR_NAME,
            "year": row.YEAR,
            "oil_bbl": round(oil, 2),
            "gas_mcf": round(gas, 2),
            "water_bbl": round(row.total_water_bbl or 0.0, 2),
            "boe": boe,
            "days_on": row.total_days_on or 0,
        })

    return {
        "data": data,
        "meta": {
            "total": len(data),
            "boe_formula": "OIL_BBL + (GAS_MCF * 0.1781)",
        },
    }
