from fastapi import APIRouter

router = APIRouter()


@router.get("/incs")
async def list_incs():
    return {"data": [], "meta": {"status": "stub"}}
