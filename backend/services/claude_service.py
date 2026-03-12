class ClaudeService:
    """Service for interacting with the Claude API for AI analysis."""

    def __init__(self) -> None:
        raise NotImplementedError("ClaudeService not yet implemented")

    async def analyze_trends(self, data: dict) -> dict:
        raise NotImplementedError

    async def categorize_incidents(self, data: dict) -> dict:
        raise NotImplementedError

    async def chat(self, question: str, context: str) -> str:
        raise NotImplementedError
