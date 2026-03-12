from fastapi import APIRouter

router = APIRouter()


@router.post("/analyze/trends")
async def analyze_trends():
    return {"data": [], "meta": {"status": "stub"}}


@router.post("/analyze/categorize")
async def analyze_categorize():
    return {"data": [], "meta": {"status": "stub"}}
