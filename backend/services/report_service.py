class ReportService:
    """Service for generating PDF safety briefings."""

    def __init__(self) -> None:
        raise NotImplementedError("ReportService not yet implemented")

    async def generate_briefing(self, operator: str, date_range: dict) -> bytes:
        raise NotImplementedError
