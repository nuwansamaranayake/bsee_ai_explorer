"""Download BSEE Safety Alerts and Investigation Reports from curated manifest.

Usage: python -m etl.download_safety_alerts
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

MANIFEST_PATH = Path(__file__).parent / "pdf_manifest.json"
PDF_BASE_PATH = Path(os.getenv("PDF_PATH", "./data/pdfs"))


async def download_pdf(
    client: httpx.AsyncClient,
    url: str,
    dest: Path,
    retries: int = 3,
) -> bool:
    """Download a single PDF with retry logic. Returns True on success."""
    for attempt in range(retries):
        try:
            resp = await client.get(url, follow_redirects=True, timeout=30.0)
            resp.raise_for_status()
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(resp.content)
            return True
        except (httpx.HTTPError, httpx.TimeoutException) as e:
            wait = 2 ** attempt
            logger.warning(
                "Download attempt %d/%d failed for %s: %s. Retrying in %ds...",
                attempt + 1, retries, url, e, wait,
            )
            if attempt < retries - 1:
                await asyncio.sleep(wait)
    return False


async def download_all() -> dict:
    """Download all PDFs from the manifest. Idempotent — skips existing files."""
    manifest = json.loads(MANIFEST_PATH.read_text())

    stats = {"found": 0, "downloaded": 0, "skipped": 0, "failed": 0}

    async with httpx.AsyncClient(
        headers={"User-Agent": "BeaconGoM/1.0 (BSEE data research)"}
    ) as client:
        for doc_type in ("safety_alerts", "investigation_reports"):
            entries = manifest.get(doc_type, [])
            dest_dir = PDF_BASE_PATH / doc_type

            for entry in entries:
                stats["found"] += 1
                dest = dest_dir / entry["filename"]

                # Idempotent: skip if file exists and is non-empty
                if dest.exists() and dest.stat().st_size > 0:
                    stats["skipped"] += 1
                    continue

                ok = await download_pdf(client, entry["url"], dest)
                if ok:
                    stats["downloaded"] += 1
                    logger.info("Downloaded: %s", entry["filename"])
                else:
                    stats["failed"] += 1
                    logger.error("FAILED: %s from %s", entry["filename"], entry["url"])

    return stats


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    stats = asyncio.run(download_all())
    print(f"\n=== PDF Download Summary ===")
    print(f"  Found in manifest : {stats['found']}")
    print(f"  Downloaded (new)  : {stats['downloaded']}")
    print(f"  Skipped (exists)  : {stats['skipped']}")
    print(f"  Failed            : {stats['failed']}")


if __name__ == "__main__":
    main()
