from fastapi import APIRouter

router = APIRouter()


@router.post("/documents/search")
async def search_documents():
    return {"data": [], "meta": {"status": "stub"}}
