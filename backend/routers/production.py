from fastapi import APIRouter

router = APIRouter()


@router.get("/production")
async def list_production():
    return {"data": [], "meta": {"status": "stub"}}
