"""RegulatoryService — BSEE Safety Alert scraper and AI digest generator.

Scrapes the BSEE Safety Alerts listing page, discovers new alerts,
downloads their PDFs, extracts text, and generates AI digests.

BSEE Safety Alerts page: https://www.bsee.gov/resources-tools/safety-alerts
"""

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

from models.database import SessionLocal
from models.phase4_tables import AlertSummary
from services.input_sanitizer import sanitize_document_text

logger = logging.getLogger(__name__)

BSEE_ALERTS_URL = "https://www.bsee.gov/resources-tools/safety-alerts"
USER_AGENT = "BeaconGoM/1.0 (BSEE data research; contact: info@aigniteconsulting.ai)"


class RegulatoryService:
    """Scrapes BSEE Safety Alerts and generates AI digests."""

    def __init__(self):
        logger.info("RegulatoryService initialized")

    async def scrape_new_alerts(self) -> int:
        """Scrape BSEE listing page for new Safety Alerts.

        Returns count of newly discovered alerts.
        """
        try:
            alert_links = await self._fetch_alert_listing()
        except Exception as e:
            logger.error("Failed to fetch BSEE alerts listing: %s", e)
            return 0

        db = SessionLocal()
        new_count = 0
        try:
            for alert_info in alert_links:
                alert_num = alert_info.get("alert_number", "")
                if not alert_num:
                    continue

                # Skip if already in DB
                existing = (
                    db.query(AlertSummary)
                    .filter(AlertSummary.alert_number == alert_num)
                    .first()
                )
                if existing:
                    continue

                # Create new entry
                now = datetime.now(timezone.utc).isoformat()
                entry = AlertSummary(
                    alert_number=alert_num,
                    title=alert_info.get("title", "Unknown"),
                    published_date=alert_info.get("date", ""),
                    source_url=alert_info.get("url", ""),
                    pdf_url=alert_info.get("pdf_url", ""),
                    status="new",
                    created_at=now,
                    updated_at=now,
                )
                db.add(entry)
                new_count += 1
                logger.info("Discovered new BSEE Safety Alert: %s", alert_num)

            db.commit()
        except Exception as e:
            db.rollback()
            logger.error("Failed to save new alerts: %s", e)
            raise
        finally:
            db.close()

        return new_count

    async def _fetch_alert_listing(self) -> list[dict]:
        """Fetch and parse the BSEE Safety Alerts listing page."""
        async with httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT},
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            resp = await client.get(BSEE_ALERTS_URL)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        alerts = []

        # BSEE listing uses table rows or anchor links with alert numbers
        # Parse links that match Safety Alert pattern
        for link in soup.find_all("a", href=True):
            href = link["href"]
            text = link.get_text(strip=True)

            # Match patterns like "Safety Alert 350" or "SA-350"
            alert_match = re.search(r"(?:Safety\s+Alert|SA)[- ]*(\d+)", text, re.IGNORECASE)
            if not alert_match:
                # Also check href for alert number patterns
                alert_match = re.search(r"safety-alert[- ]*(\d+)", href, re.IGNORECASE)

            if alert_match:
                alert_num = alert_match.group(1)
                full_url = href if href.startswith("http") else f"https://www.bsee.gov{href}"

                alerts.append({
                    "alert_number": alert_num,
                    "title": text[:500],
                    "url": full_url,
                    "pdf_url": "",  # Will be resolved from detail page if needed
                    "date": "",
                })

        logger.info("Scraped %d alert links from BSEE listing", len(alerts))
        return alerts

    async def generate_digest(self, alert_id: int) -> dict:
        """Generate an AI digest for a specific alert. Returns the digest dict."""
        db = SessionLocal()
        try:
            alert = db.query(AlertSummary).filter(AlertSummary.id == alert_id).first()
            if not alert:
                return {"error": "Alert not found"}

            if not alert.raw_text:
                return {"error": "No text content available for this alert. PDF may not be ingested yet."}

            from services.claude_service import get_claude_service
            from services.prompts import REGULATORY_DIGEST_SYSTEM, REGULATORY_DIGEST_USER

            claude = get_claude_service()
            # Sanitize PDF-extracted text before injecting into prompt
            clean_text = sanitize_document_text(alert.raw_text, max_length=8000)
            user_prompt = REGULATORY_DIGEST_USER.format(
                alert_number=alert.alert_number,
                title=alert.title,
                published_date=alert.published_date or "Unknown",
                alert_text=clean_text,
            )

            digest = await claude.generate_json(REGULATORY_DIGEST_SYSTEM, user_prompt)

            # Update DB
            now = datetime.now(timezone.utc).isoformat()
            alert.ai_summary = digest.get("summary", "")
            alert.ai_impact = digest.get("impact", "")
            alert.ai_action_items = json.dumps(digest.get("action_items", []))
            alert.updated_at = now
            db.commit()

            return digest

        except Exception as e:
            db.rollback()
            logger.error("Failed to generate digest for alert %d: %s", alert_id, e, exc_info=True)
            return {"error": "Digest generation failed. Please try again."}
        finally:
            db.close()

    def get_alerts(
        self,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """Get alerts with optional status filter. Returns (alerts, total_count)."""
        db = SessionLocal()
        try:
            query = db.query(AlertSummary).order_by(AlertSummary.id.desc())
            if status:
                query = query.filter(AlertSummary.status == status)

            total = query.count()
            entries = query.offset(offset).limit(limit).all()

            alerts = [
                {
                    "id": a.id,
                    "alert_number": a.alert_number,
                    "title": a.title,
                    "published_date": a.published_date,
                    "source_url": a.source_url,
                    "status": a.status,
                    "has_digest": bool(a.ai_summary),
                    "ai_summary": a.ai_summary,
                    "ai_impact": a.ai_impact,
                    "ai_action_items": json.loads(a.ai_action_items) if a.ai_action_items else [],
                    "created_at": a.created_at,
                }
                for a in entries
            ]
            return alerts, total
        finally:
            db.close()

    def get_alert_detail(self, alert_id: int) -> dict | None:
        """Get full detail for a single alert."""
        db = SessionLocal()
        try:
            a = db.query(AlertSummary).filter(AlertSummary.id == alert_id).first()
            if not a:
                return None
            return {
                "id": a.id,
                "alert_number": a.alert_number,
                "title": a.title,
                "published_date": a.published_date,
                "source_url": a.source_url,
                "pdf_url": a.pdf_url,
                "status": a.status,
                "has_digest": bool(a.ai_summary),
                "raw_text": a.raw_text,
                "ai_summary": a.ai_summary,
                "ai_impact": a.ai_impact,
                "ai_action_items": json.loads(a.ai_action_items) if a.ai_action_items else [],
                "created_at": a.created_at,
                "updated_at": a.updated_at,
            }
        finally:
            db.close()

    def update_alert_status(self, alert_id: int, status: str) -> bool:
        """Update an alert's status (new, reviewed, dismissed)."""
        if status not in ("new", "reviewed", "dismissed"):
            return False
        db = SessionLocal()
        try:
            alert = db.query(AlertSummary).filter(AlertSummary.id == alert_id).first()
            if not alert:
                return False
            alert.status = status
            alert.updated_at = datetime.now(timezone.utc).isoformat()
            db.commit()
            return True
        except Exception:
            db.rollback()
            return False
        finally:
            db.close()


# Singleton
_regulatory_service: RegulatoryService | None = None


def get_regulatory_service() -> RegulatoryService:
    """Get or create the singleton RegulatoryService instance."""
    global _regulatory_service
    if _regulatory_service is None:
        _regulatory_service = RegulatoryService()
    return _regulatory_service
