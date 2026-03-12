from fastapi import APIRouter

router = APIRouter()


@router.get("/incidents")
async def list_incidents():
    return {"data": [], "meta": {"status": "stub"}}
