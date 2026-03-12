class RAGService:
    """Service for document retrieval-augmented generation."""

    def __init__(self) -> None:
        raise NotImplementedError("RAGService not yet implemented")

    async def search(self, query: str, top_k: int = 5) -> list[dict]:
        raise NotImplementedError

    async def ingest_document(self, file_path: str) -> dict:
        raise NotImplementedError
