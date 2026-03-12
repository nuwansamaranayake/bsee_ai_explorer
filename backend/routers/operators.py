from fastapi import APIRouter

router = APIRouter()


@router.get("/operators")
async def list_operators():
    return {"data": [], "meta": {"status": "stub"}}
