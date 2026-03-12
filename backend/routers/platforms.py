from fastapi import APIRouter

router = APIRouter()


@router.get("/platforms")
async def list_platforms():
    return {"data": [], "meta": {"status": "stub"}}
