"""PDF report generation endpoint."""

import io
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from models.schemas import ReportRequest
from services.claude_service import get_claude_service, token_tracker
from services.report_service import get_report_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/reports/generate")
async def generate_report(req: ReportRequest):
    """Generate a PDF safety intelligence report."""
    # Check AI if requested
    if req.include_ai:
        claude = get_claude_service()
        if not claude.is_available:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "AI features unavailable",
                    "detail": "No API key configured. Set include_ai=false for data-only report.",
                },
            )

    report_svc = get_report_service()

    try:
        pdf_bytes = await report_svc.generate_report(
            operator=req.operator,
            year_start=req.year_start,
            year_end=req.year_end,
            include_ai=req.include_ai,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail={"error": str(e)})
    except Exception as e:
        logger.error("Report generation failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Report generation failed", "detail": str(e)},
        )

    op_label = (req.operator or "gom_wide").lower().replace(" ", "_")
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"beacon_gom_report_{op_label}_{date_str}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )
