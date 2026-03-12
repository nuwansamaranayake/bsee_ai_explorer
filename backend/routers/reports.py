from fastapi import APIRouter

router = APIRouter()


@router.get("/reports/generate")
async def generate_report():
    return {"data": [], "meta": {"status": "stub"}}
