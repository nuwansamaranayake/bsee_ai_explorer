class SQLService:
    """Service for text-to-SQL query generation and execution."""

    def __init__(self) -> None:
        raise NotImplementedError("SQLService not yet implemented")

    async def natural_language_query(self, question: str) -> dict:
        raise NotImplementedError

    async def execute_query(self, sql: str) -> list[dict]:
        raise NotImplementedError
