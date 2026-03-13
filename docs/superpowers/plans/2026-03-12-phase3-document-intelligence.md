# Phase 3: Document Intelligence + PDF Reports — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add PDF ingestion pipeline, RAG document search with citations, and PDF report export to Beacon GoM.

**Architecture:** Three-layer addition: (1) ETL pipeline downloads BSEE PDFs and ingests into ChromaDB via PyMuPDF + LangChain chunking, (2) RAG service queries ChromaDB then synthesizes answers via Claude with inline citations, (3) ReportService generates professional PDF briefings with ReportLab + matplotlib charts. All AI calls go through existing ClaudeService (OpenRouter).

**Tech Stack:** PyMuPDF (fitz), LangChain RecursiveCharacterTextSplitter, ChromaDB (ONNX embedder), ReportLab, matplotlib, React + shadcn/ui + TanStack Query

**Spec:** `docs/superpowers/specs/2026-03-12-phase3-document-intelligence-design.md`

---

## File Structure

### New Files
| File | Responsibility |
|---|---|
| `backend/etl/pdf_manifest.json` | Curated list of BSEE PDF URLs with metadata |
| `backend/etl/download_safety_alerts.py` | Downloads PDFs from manifest with retry logic |
| `frontend/src/hooks/useDocuments.ts` | TanStack Query hooks for document search + stats |
| `frontend/src/pages/Documents.tsx` | Full document intelligence search page |
| `frontend/src/pages/Reports.tsx` | Report configuration + PDF download page |
| `frontend/src/components/CitationCard.tsx` | Expandable citation card component |

### Replaced Stubs
| File | Current State | New Responsibility |
|---|---|---|
| `backend/etl/ingest_pdfs.py` | NotImplementedError (9 lines) | PyMuPDF extraction + LangChain chunking + ChromaDB storage |
| `backend/services/rag_service.py` | NotImplementedError (12 lines) | RAG pipeline: query + retrieve + synthesize + cite |
| `backend/services/report_service.py` | NotImplementedError (9 lines) | PDF generation with ReportLab + matplotlib charts |
| `backend/routers/documents.py` | Empty stub (9 lines) | POST /search + GET /stats endpoints |
| `backend/routers/reports.py` | Empty stub (9 lines) | POST /generate endpoint returning PDF bytes |

### Modified Files
| File | Changes |
|---|---|
| `backend/requirements.txt` | Add reportlab>=4.0, matplotlib>=3.8 |
| `backend/services/prompts.py` | Add RAG_SYSTEM, RAG_USER, REPORT_SUMMARY_*, REPORT_RECOMMENDATIONS_* |
| `backend/services/__init__.py` | Export RAGService, ReportService singletons |
| `backend/models/schemas.py` | Add DocumentSearchRequest, Citation, DocumentSearchResponse, DocumentStatsResponse, ReportRequest |
| `backend/main.py` | Add ChromaDB status to health check |
| `backend/start.sh` | Add PDF download + ingest before uvicorn |

---

## Chunk 1: PDF Download & Ingestion Pipeline (Step 3.1)

### Task 1: Add new dependencies to requirements.txt

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: Add reportlab and matplotlib to requirements.txt**

Add these two lines after the existing `tenacity` entry (line 17):

```
reportlab>=4.0
matplotlib>=3.8
```

- [ ] **Step 2: Install locally to verify no conflicts**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\backend && pip install reportlab>=4.0 matplotlib>=3.8`
Expected: Both install successfully

- [ ] **Step 3: Commit**

```bash
git add backend/requirements.txt
git commit -m "deps: add reportlab and matplotlib for Phase 3"
```

---

### Task 2: Create PDF manifest

**Files:**
- Create: `backend/etl/pdf_manifest.json`

- [ ] **Step 1: Create the curated manifest file**

Create `backend/etl/pdf_manifest.json` with real BSEE Safety Alert and Investigation Report PDF URLs. The manifest needs:
- `version` and `last_updated` fields
- `safety_alerts` array (target 30-50 entries) with `url`, `filename`, `alert_number`, `title`
- `investigation_reports` array (target 20-30 entries) with `url`, `filename`, `title`

URLs should point to real PDFs on `bsee.gov`. To find valid URLs:
- Safety Alerts: `https://www.bsee.gov/newsroom/safety-alerts` — PDFs typically at `https://www.bsee.gov/sites/bsee.gov/files/safety-alerts-702/safety-alert-{number}.pdf`
- Investigation Reports: `https://www.bsee.gov/what-we-do/safety-enforcement/incident-investigations`

If live URLs are unavailable or unreliable, use a smaller set of confirmed working URLs and note the rest as placeholders. The download script handles failures gracefully.

- [ ] **Step 2: Validate JSON syntax**

Run: `python -c "import json; json.load(open('backend/etl/pdf_manifest.json')); print('Valid JSON')"`
Expected: `Valid JSON`

- [ ] **Step 3: Commit**

```bash
git add backend/etl/pdf_manifest.json
git commit -m "data: add curated BSEE PDF manifest with safety alerts and investigation reports"
```

---

### Task 3: Build PDF download script

**Files:**
- Create: `backend/etl/download_safety_alerts.py`

- [ ] **Step 1: Create the download script**

Create `backend/etl/download_safety_alerts.py`:

```python
"""
Download BSEE Safety Alerts and Investigation Reports from curated manifest.

Usage:
    python -m etl.download_safety_alerts
"""
import asyncio
import json
import os
from pathlib import Path

import httpx


MANIFEST_PATH = Path(__file__).parent / "pdf_manifest.json"
DEFAULT_PDF_DIR = os.getenv("PDF_PATH", "./data/pdfs")

MAX_RETRIES = 3
BACKOFF_BASE = 1  # seconds


async def download_file(
    client: httpx.AsyncClient,
    url: str,
    dest: Path,
) -> bool:
    """Download a single file with retry logic. Returns True on success."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = await client.get(url, follow_redirects=True)
            resp.raise_for_status()
            dest.write_bytes(resp.content)
            return True
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            if attempt < MAX_RETRIES:
                wait = BACKOFF_BASE * (2 ** (attempt - 1))
                print(f"  Retry {attempt}/{MAX_RETRIES} for {dest.name} "
                      f"({exc.__class__.__name__}), waiting {wait}s...")
                await asyncio.sleep(wait)
            else:
                print(f"  FAILED {dest.name}: {exc}")
                return False


async def download_all() -> dict:
    """Download all PDFs from the manifest. Returns summary stats."""
    manifest = json.loads(MANIFEST_PATH.read_text())

    stats = {"found": 0, "downloaded": 0, "skipped": 0, "failed": 0}

    async with httpx.AsyncClient(timeout=60.0) as client:
        for doc_type in ("safety_alerts", "investigation_reports"):
            entries = manifest.get(doc_type, [])
            out_dir = Path(DEFAULT_PDF_DIR) / doc_type
            out_dir.mkdir(parents=True, exist_ok=True)

            for entry in entries:
                stats["found"] += 1
                dest = out_dir / entry["filename"]

                # Idempotent: skip if file exists and is non-empty
                if dest.exists() and dest.stat().st_size > 0:
                    stats["skipped"] += 1
                    continue

                print(f"  Downloading {entry['filename']}...")
                ok = await download_file(client, entry["url"], dest)
                if ok:
                    stats["downloaded"] += 1
                else:
                    stats["failed"] += 1

    return stats


def main():
    print("=" * 60)
    print("BSEE PDF Downloader")
    print("=" * 60)
    stats = asyncio.run(download_all())
    print(f"\nSummary: {stats['found']} in manifest, "
          f"{stats['downloaded']} downloaded, "
          f"{stats['skipped']} skipped, "
          f"{stats['failed']} failed")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test the download script locally**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\backend && python -m etl.download_safety_alerts`
Expected: Summary line showing downloads/skips. Some may fail if URLs are dead — that's OK. At least a few should succeed.

- [ ] **Step 3: Commit**

```bash
git add backend/etl/download_safety_alerts.py
git commit -m "feat: add BSEE PDF download script with retry and idempotency"
```

---

### Task 4: Build PDF ingestion pipeline

**Files:**
- Replace: `backend/etl/ingest_pdfs.py` (currently 9-line stub)

- [ ] **Step 1: Replace the stub with full ingestion pipeline**

Replace `backend/etl/ingest_pdfs.py` entirely:

```python
"""
Ingest BSEE PDFs into ChromaDB for RAG search.

Three-stage pipeline:
  1. Extract text page-by-page with PyMuPDF (fitz)
  2. Chunk with LangChain RecursiveCharacterTextSplitter
  3. Embed and store in ChromaDB (default ONNX embedder)

Usage:
    python -m etl.ingest_pdfs          # skip already-ingested docs
    python -m etl.ingest_pdfs --force   # re-ingest everything
"""
import argparse
import json
import os
import re
from pathlib import Path

import chromadb
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter


CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")
PDF_PATH = os.getenv("PDF_PATH", "./data/pdfs")
MANIFEST_PATH = Path(__file__).parent / "pdf_manifest.json"
COLLECTION_NAME = "bsee_documents"

CHUNK_SIZE = 512
CHUNK_OVERLAP = 50

# Header/footer patterns to strip
STRIP_PATTERNS = [
    re.compile(r"^U\.S\. Department of the Interior.*$", re.MULTILINE),
    re.compile(r"^Bureau of Safety.*$", re.MULTILINE),
    re.compile(r"^Page \d+ of \d+\s*$", re.MULTILINE),
    re.compile(r"^\s*\d+\s*$", re.MULTILINE),  # standalone page numbers
    re.compile(r"^BSEE\s.*$", re.MULTILINE),
]

# Date patterns for metadata extraction
DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b"),
    re.compile(r"\b(\w+ \d{1,2}, \d{4})\b"),
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
]


def _clean_text(text: str) -> str:
    """Strip known BSEE headers, footers, and page numbers."""
    for pattern in STRIP_PATTERNS:
        text = pattern.sub("", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_date(text: str) -> str | None:
    """Try to extract a date from the first page text."""
    for pattern in DATE_PATTERNS:
        match = pattern.search(text[:500])  # search first 500 chars
        if match:
            return match.group(1)
    return None


def _build_manifest_lookup() -> dict:
    """Build filename -> metadata lookup from manifest."""
    lookup = {}
    if not MANIFEST_PATH.exists():
        return lookup
    manifest = json.loads(MANIFEST_PATH.read_text())
    for doc_type in ("safety_alerts", "investigation_reports"):
        for entry in manifest.get(doc_type, []):
            lookup[entry["filename"]] = {
                "title": entry.get("title", ""),
                "alert_number": entry.get("alert_number", ""),
                "doc_type": doc_type.rstrip("s"),  # safety_alert, investigation_report
            }
    return lookup


def extract_pdf(pdf_path: Path, manifest_meta: dict) -> list[dict]:
    """Extract text and metadata from a PDF, page by page.

    Returns list of {text, page_number, metadata} dicts.
    """
    pages = []
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as exc:
        print(f"  WARNING: Could not open {pdf_path.name}: {exc}")
        return pages

    first_page_text = ""
    for page_num in range(len(doc)):
        page = doc[page_num]
        raw_text = page.get_text()
        text = _clean_text(raw_text)

        if not text.strip():
            continue

        if page_num == 0:
            first_page_text = text

        pages.append({
            "text": text,
            "page_number": page_num + 1,  # 1-indexed
        })

    doc.close()

    # Build metadata from manifest + extracted content
    title = manifest_meta.get("title") or (
        first_page_text.split("\n")[0][:100] if first_page_text else pdf_path.stem
    )
    date = _extract_date(first_page_text)
    doc_type = manifest_meta.get("doc_type", "unknown")
    alert_number = manifest_meta.get("alert_number", "")

    for p in pages:
        p["metadata"] = {
            "source_file": pdf_path.name,
            "page_number": p["page_number"],
            "doc_type": doc_type,
            "alert_number": alert_number,
            "date": date or "",
            "title": title,
        }

    return pages


def chunk_pages(pages: list[dict]) -> list[dict]:
    """Chunk extracted pages using LangChain splitter.

    Returns list of {text, metadata} dicts ready for ChromaDB.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        length_function=len,
    )
    chunks = []
    for page in pages:
        splits = splitter.split_text(page["text"])
        for split_text in splits:
            if len(split_text.strip()) < 20:
                continue  # skip tiny fragments
            chunks.append({
                "text": split_text,
                "metadata": page["metadata"].copy(),
            })
    return chunks


def ingest_pdfs(force: bool = False) -> dict:
    """Main ingestion pipeline. Returns summary stats."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection(COLLECTION_NAME)
    manifest_lookup = _build_manifest_lookup()

    stats = {
        "documents_processed": 0,
        "documents_skipped": 0,
        "total_chunks": 0,
        "errors": 0,
    }

    pdf_dir = Path(PDF_PATH)
    if not pdf_dir.exists():
        print(f"  PDF directory not found: {pdf_dir}")
        return stats

    # Gather all PDFs from subdirectories
    pdf_files = sorted(pdf_dir.rglob("*.pdf"))
    if not pdf_files:
        print("  No PDF files found.")
        return stats

    print(f"  Found {len(pdf_files)} PDF files")

    for pdf_path in pdf_files:
        filename = pdf_path.name

        # Idempotency check: skip if already ingested (unless --force)
        if not force:
            existing = collection.get(
                where={"source_file": filename},
                limit=1,
            )
            if existing and existing["ids"]:
                stats["documents_skipped"] += 1
                continue

        # If force, delete existing chunks first
        if force:
            existing = collection.get(
                where={"source_file": filename},
            )
            if existing and existing["ids"]:
                collection.delete(ids=existing["ids"])

        # Get manifest metadata for this file
        meta = manifest_lookup.get(filename, {
            "title": "",
            "alert_number": "",
            "doc_type": "unknown",
        })

        # Extract
        pages = extract_pdf(pdf_path, meta)
        if not pages:
            stats["errors"] += 1
            continue

        # Chunk
        chunks = chunk_pages(pages)
        if not chunks:
            stats["errors"] += 1
            continue

        # Store in ChromaDB (batch add)
        ids = [f"{filename}_chunk_{i}" for i in range(len(chunks))]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        # ChromaDB has a batch limit, add in groups of 100
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            collection.add(
                ids=ids[i:i + batch_size],
                documents=documents[i:i + batch_size],
                metadatas=metadatas[i:i + batch_size],
            )

        stats["documents_processed"] += 1
        stats["total_chunks"] += len(chunks)
        print(f"  Ingested {filename}: {len(chunks)} chunks")

    stats["collection_size"] = collection.count()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Ingest BSEE PDFs into ChromaDB")
    parser.add_argument("--force", action="store_true",
                        help="Re-ingest all documents, replacing existing chunks")
    args = parser.parse_args()

    print("=" * 60)
    print("BSEE PDF Ingestion Pipeline")
    print("=" * 60)

    stats = ingest_pdfs(force=args.force)

    print(f"\nSummary:")
    print(f"  Documents processed: {stats['documents_processed']}")
    print(f"  Documents skipped:   {stats['documents_skipped']}")
    print(f"  Total chunks:        {stats['total_chunks']}")
    print(f"  Errors:              {stats['errors']}")
    print(f"  Collection size:     {stats.get('collection_size', 'N/A')}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Test the ingestion pipeline locally**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\backend && python -m etl.ingest_pdfs`
Expected: Processes any downloaded PDFs, prints chunk counts per document. If no PDFs were downloaded yet, it prints "No PDF files found."

- [ ] **Step 3: Test idempotency — re-run should skip all**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\backend && python -m etl.ingest_pdfs`
Expected: All documents show as skipped.

- [ ] **Step 4: Test --force flag**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\backend && python -m etl.ingest_pdfs --force`
Expected: All documents re-ingested (deletes + re-adds chunks).

- [ ] **Step 5: Verify ChromaDB query works**

Run:
```bash
cd E:\AiGNITE\projects\Beacon_GoM\backend && python -c "
import chromadb
client = chromadb.PersistentClient(path='./data/chroma')
col = client.get_or_create_collection('bsee_documents')
print(f'Collection size: {col.count()} chunks')
if col.count() > 0:
    results = col.query(query_texts=['safety equipment failure'], n_results=3)
    for doc, meta in zip(results['documents'][0], results['metadatas'][0]):
        print(f'  [{meta[\"source_file\"]}] p{meta[\"page_number\"]}: {doc[:80]}...')
"
```
Expected: Collection has chunks, query returns relevant results with correct metadata.

- [ ] **Step 6: Commit**

```bash
git add backend/etl/ingest_pdfs.py
git commit -m "feat: build PDF ingestion pipeline with PyMuPDF, LangChain, and ChromaDB"
```

---

### Task 5: Update start.sh for Docker auto-ingestion

**Files:**
- Modify: `backend/start.sh`

- [ ] **Step 1: Update start.sh to download PDFs and ingest on first boot**

Replace `backend/start.sh` with:

```sh
#!/bin/sh
set -e

mkdir -p /app/data/chroma /app/data/pdfs

# --- Seed structured database ---
if [ ! -f /app/data/bsee.db ]; then
    echo ">>> No database found — seeding BSEE data..."
    python -m etl.seed_data
    echo ">>> Database seeded successfully."
else
    echo ">>> Database already exists at /app/data/bsee.db"
fi

# --- Download and ingest PDFs for RAG ---
CHROMA_COUNT=$(python -c "
import chromadb
try:
    c = chromadb.PersistentClient(path='/app/data/chroma')
    col = c.get_or_create_collection('bsee_documents')
    print(col.count())
except:
    print(0)
" 2>/dev/null || echo "0")

if [ "$CHROMA_COUNT" = "0" ]; then
    echo ">>> ChromaDB empty — downloading and ingesting PDFs..."
    python -m etl.download_safety_alerts || echo ">>> PDF download had errors (continuing)"
    python -m etl.ingest_pdfs || echo ">>> PDF ingestion had errors (continuing)"
    echo ">>> PDF pipeline complete."
else
    echo ">>> ChromaDB already has $CHROMA_COUNT chunks — skipping PDF pipeline."
fi

echo ">>> Starting Beacon GoM API..."
exec uvicorn main:app --host 0.0.0.0 --port 8000
```

- [ ] **Step 2: Commit**

```bash
git add backend/start.sh
git commit -m "feat: add PDF download and ingestion to Docker startup"
```

---

## Chunk 2: RAG Search Backend (Step 3.2 Backend)

### Task 6: Add prompt templates for RAG and Reports

**Files:**
- Modify: `backend/services/prompts.py` (currently ends at line 172)

- [ ] **Step 1: Add RAG and report prompt templates**

Append to the end of `backend/services/prompts.py`:

```python
# ── RAG Document Search ──────────────────────────────────────────────

RAG_SYSTEM = """You are a BSEE document analyst specializing in Gulf of Mexico offshore safety.
Answer the user's question using ONLY the provided document excerpts.

Rules:
- For every claim in your answer, cite the source using: [Source: {document_title}, Page {page_number}]
- If the documents don't contain enough information to answer, say so clearly
- Do not make up information that isn't in the provided excerpts
- Synthesize information from multiple documents when relevant
- Be specific and reference concrete findings, dates, and recommendations"""

RAG_USER = """Question: {query}

Document Excerpts:
{context}

Provide a thorough answer with citations to the specific documents and pages above."""

# ── PDF Report Generation ────────────────────────────────────────────

REPORT_SUMMARY_SYSTEM = """You are a safety intelligence analyst writing an executive summary
for a Gulf of Mexico safety report. Write professionally and concisely, suitable for
HSE leadership. Focus on data-driven insights."""

REPORT_SUMMARY_USER = """Write a 2-3 paragraph executive summary based on this safety data:

{data_summary}

Focus on key trends, areas of concern, and notable improvements."""

REPORT_RECOMMENDATIONS_SYSTEM = """You are a safety consultant providing actionable
recommendations based on Gulf of Mexico offshore safety data. Be specific and practical."""

REPORT_RECOMMENDATIONS_USER = """Based on this safety data, provide 3-5 specific, actionable
recommendations:

{data_summary}

Format as a numbered list. Each recommendation should be concrete and implementable
by an offshore operator's HSE team."""
```

- [ ] **Step 2: Verify the module still imports cleanly**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\backend && python -c "from services import prompts; print('RAG_SYSTEM' in dir(prompts))"`
Expected: `True`

- [ ] **Step 3: Commit**

```bash
git add backend/services/prompts.py
git commit -m "feat: add RAG and report prompt templates"
```

---

### Task 7: Add Pydantic models for documents and reports

**Files:**
- Modify: `backend/models/schemas.py` (currently ends at line 56)

- [ ] **Step 1: Add document and report schemas**

Append to `backend/models/schemas.py`:

```python
# ── Document Search ──────────────────────────────────────────────────

class DocumentSearchRequest(BaseModel):
    query: str
    top_k: int = 5
    doc_type: str | None = None  # "safety_alert" | "investigation_report" | None


class Citation(BaseModel):
    source_file: str
    title: str
    page_number: int
    relevance_score: float
    excerpt: str


class DocumentSearchResponse(BaseModel):
    answer: str
    citations: list[Citation]
    query: str
    doc_count: int
    generated_at: str


class DocumentStatsResponse(BaseModel):
    total_documents: int
    total_chunks: int
    safety_alerts: int
    investigation_reports: int
    oldest_date: str | None = None
    newest_date: str | None = None


# ── Report Generation ────────────────────────────────────────────────

class ReportRequest(BaseModel):
    operator: str | None = None
    year_start: int | None = None
    year_end: int | None = None
    include_ai: bool = True
```

- [ ] **Step 2: Verify schemas import**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\backend && python -c "from models.schemas import DocumentSearchRequest, Citation, ReportRequest; print('OK')"`
Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add backend/models/schemas.py
git commit -m "feat: add Pydantic schemas for document search and report generation"
```

---

### Task 8: Build RAG service

**Files:**
- Replace: `backend/services/rag_service.py` (currently 12-line stub)

- [ ] **Step 1: Replace the stub with the full RAG service**

Replace `backend/services/rag_service.py` entirely:

```python
"""
RAG (Retrieval-Augmented Generation) service for BSEE document search.

Pipeline: user query -> ChromaDB semantic search -> context assembly ->
          Claude synthesis -> structured response with citations.
"""
import asyncio
import logging
import os
from datetime import datetime, timezone

import chromadb

from services.claude_service import get_claude_service
from services.prompts import RAG_SYSTEM, RAG_USER


logger = logging.getLogger(__name__)

COLLECTION_NAME = "bsee_documents"


class RAGService:
    """Retrieval-Augmented Generation over BSEE document corpus."""

    def __init__(self):
        """Zero-arg constructor — reads config from environment."""
        chroma_path = os.getenv("CHROMA_PATH", "./data/chroma")
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection(COLLECTION_NAME)
        self.claude = get_claude_service()

    async def search(
        self,
        query: str,
        top_k: int = 5,
        doc_type: str | None = None,
    ) -> dict:
        """Full RAG pipeline: query -> retrieve -> synthesize -> cite.

        Args:
            query: Natural language question.
            top_k: Number of chunks to retrieve (default 5).
            doc_type: Optional filter — "safety_alert" or "investigation_report".

        Returns:
            dict with keys: answer, citations, query, doc_count, generated_at
        """
        # 1. Retrieve from ChromaDB (sync call wrapped for async)
        where_filter = {"doc_type": doc_type} if doc_type else None
        results = await asyncio.to_thread(
            self.collection.query,
            query_texts=[query],
            n_results=top_k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not documents:
            return {
                "answer": "No relevant documents found for your query. "
                          "Try rephrasing or broadening your search.",
                "citations": [],
                "query": query,
                "doc_count": self.collection.count(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        # 2. Build context string for Claude
        context_parts = []
        citations = []
        for i, (doc, meta, dist) in enumerate(
            zip(documents, metadatas, distances)
        ):
            title = meta.get("title", "Unknown Document")
            page = meta.get("page_number", 0)
            source = meta.get("source_file", "unknown")

            context_parts.append(
                f"--- Excerpt {i + 1} ---\n"
                f"Document: {title}\n"
                f"Page: {page}\n"
                f"Content:\n{doc}\n"
            )

            # Relevance score: 1 - distance, clamped to 0-1
            relevance = max(0.0, min(1.0, 1.0 - dist))
            citations.append({
                "source_file": source,
                "title": title,
                "page_number": page,
                "relevance_score": round(relevance, 3),
                "excerpt": doc[:300],
            })

        context = "\n".join(context_parts)

        # 3. Synthesize answer with Claude
        user_prompt = RAG_USER.format(query=query, context=context)
        answer = await self.claude.generate(
            system_prompt=RAG_SYSTEM,
            user_prompt=user_prompt,
            max_tokens=2048,
            temperature=0.2,
        )

        return {
            "answer": answer,
            "citations": citations,
            "query": query,
            "doc_count": self.collection.count(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_stats(self) -> dict:
        """Return corpus statistics for the frontend stats bar."""
        count = self.collection.count()

        # Get all metadata to count by type and find date range
        stats = {
            "total_chunks": count,
            "total_documents": 0,
            "safety_alerts": 0,
            "investigation_reports": 0,
            "oldest_date": None,
            "newest_date": None,
        }

        if count == 0:
            return stats

        # Get unique source files and doc types
        all_meta = self.collection.get(
            include=["metadatas"],
            limit=count,
        )

        source_files = set()
        dates = []
        for meta in all_meta.get("metadatas", []):
            source_files.add(meta.get("source_file", ""))
            doc_type = meta.get("doc_type", "")
            date = meta.get("date", "")
            if date:
                dates.append(date)

        stats["total_documents"] = len(source_files)

        # Count by type from unique source files
        all_types = [
            m.get("doc_type", "") for m in all_meta.get("metadatas", [])
        ]
        # Get unique source_file -> doc_type mapping
        file_types = {}
        for m in all_meta.get("metadatas", []):
            sf = m.get("source_file", "")
            dt = m.get("doc_type", "")
            if sf and dt:
                file_types[sf] = dt

        stats["safety_alerts"] = sum(
            1 for t in file_types.values() if t == "safety_alert"
        )
        stats["investigation_reports"] = sum(
            1 for t in file_types.values() if t == "investigation_report"
        )

        if dates:
            stats["oldest_date"] = min(dates)
            stats["newest_date"] = max(dates)

        return stats


# ── Singleton ────────────────────────────────────────────────────────

_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """Get or create the singleton RAGService instance."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
```

- [ ] **Step 2: Update services/__init__.py exports**

Replace `backend/services/__init__.py`:

```python
from .claude_service import ClaudeService, get_claude_service, ClaudeServiceError, token_tracker
from .sql_service import SQLService, get_sql_service
from .rag_service import RAGService, get_rag_service
from .report_service import ReportService, get_report_service
```

Note: `report_service` import will fail until Task 12 creates it. That's fine — we'll fix it then. For now, keep the old `__init__.py` and only add the RAG import:

```python
from .claude_service import ClaudeService, get_claude_service, ClaudeServiceError, token_tracker
from .sql_service import SQLService, get_sql_service
from .rag_service import RAGService, get_rag_service
```

- [ ] **Step 3: Verify RAG service imports cleanly**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\backend && python -c "from services.rag_service import get_rag_service; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/services/rag_service.py backend/services/__init__.py
git commit -m "feat: build RAG service with ChromaDB retrieval and Claude synthesis"
```

---

### Task 9: Build documents router

**Files:**
- Replace: `backend/routers/documents.py` (currently 9-line stub)

- [ ] **Step 1: Replace the stub with the full documents router**

Replace `backend/routers/documents.py` entirely:

```python
"""
Document Intelligence endpoints — RAG search over BSEE Safety Alerts
and Investigation Reports with AI-synthesized answers and citations.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from models.schemas import DocumentSearchRequest
from services.claude_service import get_claude_service, ClaudeServiceError
from services.rag_service import get_rag_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/documents", tags=["documents"])


def _check_ai_available():
    """Raise 503 if Claude is not configured."""
    claude = get_claude_service()
    if not claude.is_available:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "AI service unavailable",
                "detail": "No API key configured. Set OPENROUTER_API_KEY or ANTHROPIC_API_KEY.",
            },
        )


@router.post("/search")
async def search_documents(request: DocumentSearchRequest):
    """Search BSEE documents with AI-synthesized answer and citations."""
    _check_ai_available()

    rag = get_rag_service()

    # Check if corpus is empty
    if rag.collection.count() == 0:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "No documents indexed",
                "detail": "Run the ingestion pipeline first: python -m etl.ingest_pdfs",
            },
        )

    try:
        result = await rag.search(
            query=request.query,
            top_k=request.top_k,
            doc_type=request.doc_type,
        )
    except ClaudeServiceError as exc:
        raise HTTPException(
            status_code=502,
            detail={"error": "AI synthesis failed", "detail": str(exc)},
        )
    except Exception as exc:
        logger.exception("Document search failed")
        raise HTTPException(
            status_code=500,
            detail={"error": "Document search failed", "detail": str(exc)},
        )

    return {"data": result, "meta": {"status": "ok"}}


@router.get("/stats")
async def document_stats():
    """Return corpus statistics for the frontend stats bar."""
    try:
        rag = get_rag_service()
        stats = rag.get_stats()
    except Exception as exc:
        logger.exception("Failed to get document stats")
        raise HTTPException(
            status_code=500,
            detail={"error": "Failed to get document stats", "detail": str(exc)},
        )

    return {"data": stats, "meta": {"status": "ok"}}
```

- [ ] **Step 2: Add ChromaDB status to health check in main.py**

In `backend/main.py`, update the health endpoint (around line 52) to include ChromaDB info. Add this import at the top:

```python
from services.rag_service import get_rag_service
```

Then in the health function, add after the `ai_tokens_used` section:

```python
        # ChromaDB corpus status
        try:
            rag = get_rag_service()
            chroma_count = rag.collection.count()
        except Exception:
            chroma_count = 0
```

And include `"documents_indexed": chroma_count` in the return dict.

- [ ] **Step 3: Verify the router works (requires running backend)**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\backend && python -c "from routers.documents import router; print(f'{len(router.routes)} routes')"`
Expected: `2 routes`

- [ ] **Step 4: Commit**

```bash
git add backend/routers/documents.py backend/main.py
git commit -m "feat: build documents router with RAG search and stats endpoints"
```

---

## Chunk 3: Documents Frontend (Step 3.2 Frontend)

### Task 10: Create useDocuments hook

**Files:**
- Create: `frontend/src/hooks/useDocuments.ts`

- [ ] **Step 1: Create the hooks file**

Create `frontend/src/hooks/useDocuments.ts`:

```typescript
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiClient } from "@/lib/api";

// ── Types ───────────────────────────────────────────────────────────

export interface Citation {
  source_file: string;
  title: string;
  page_number: number;
  relevance_score: number;
  excerpt: string;
}

export interface DocumentSearchResponse {
  answer: string;
  citations: Citation[];
  query: string;
  doc_count: number;
  generated_at: string;
}

export interface DocumentStats {
  total_documents: number;
  total_chunks: number;
  safety_alerts: number;
  investigation_reports: number;
  oldest_date: string | null;
  newest_date: string | null;
}

interface ApiResponse<T> {
  data: T;
  meta?: Record<string, unknown>;
}

// ── Hooks ───────────────────────────────────────────────────────────

export function useDocumentSearch() {
  return useMutation({
    mutationFn: (params: {
      query: string;
      top_k?: number;
      doc_type?: string;
    }) =>
      apiClient<ApiResponse<DocumentSearchResponse>>("/api/documents/search", {
        method: "POST",
        body: JSON.stringify(params),
      }),
  });
}

export function useDocumentStats() {
  return useQuery({
    queryKey: ["document-stats"],
    queryFn: () =>
      apiClient<ApiResponse<DocumentStats>>("/api/documents/stats"),
    staleTime: 5 * 60 * 1000,
  });
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useDocuments.ts
git commit -m "feat: add TanStack Query hooks for document search and stats"
```

---

### Task 11: Build CitationCard component and Documents page

**Files:**
- Replace: `frontend/src/components/CitationCard.tsx` (currently 3-line stub)
- Replace: `frontend/src/pages/Documents.tsx` (currently 10-line stub)

- [ ] **Step 1: Build CitationCard component**

Replace `frontend/src/components/CitationCard.tsx`:

```tsx
import { useState } from "react";
import { FileText, ChevronDown, ChevronUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";

interface CitationCardProps {
  title: string;
  pageNumber: number;
  relevanceScore: number;
  excerpt: string;
  sourceFile: string;
}

function relevanceBadgeColor(score: number): string {
  if (score >= 0.8) return "bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200";
  if (score >= 0.6) return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200";
  return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
}

export function CitationCard({
  title,
  pageNumber,
  relevanceScore,
  excerpt,
  sourceFile,
}: CitationCardProps) {
  const [open, setOpen] = useState(false);
  const pct = Math.round(relevanceScore * 100);
  const preview = excerpt.length > 150 ? excerpt.slice(0, 150) + "..." : excerpt;

  return (
    <Collapsible open={open} onOpenChange={setOpen}>
      <Card className="transition-shadow hover:shadow-md">
        <CollapsibleTrigger asChild>
          <CardContent className="p-4 cursor-pointer">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-start gap-3 min-w-0">
                <FileText className="h-5 w-5 text-muted-foreground mt-0.5 shrink-0" />
                <div className="min-w-0">
                  <p className="font-medium text-sm leading-tight truncate">
                    {title}
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    Page {pageNumber} &middot; {sourceFile}
                  </p>
                  {!open && (
                    <p className="text-xs text-muted-foreground mt-2 line-clamp-2">
                      {preview}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <Badge className={relevanceBadgeColor(relevanceScore)} variant="secondary">
                  {pct}%
                </Badge>
                {open ? (
                  <ChevronUp className="h-4 w-4 text-muted-foreground" />
                ) : (
                  <ChevronDown className="h-4 w-4 text-muted-foreground" />
                )}
              </div>
            </div>
          </CardContent>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="px-4 pb-4 pt-0">
            <div className="rounded-md bg-muted/50 p-3 text-sm whitespace-pre-wrap">
              {excerpt}
            </div>
          </div>
        </CollapsibleContent>
      </Card>
    </Collapsible>
  );
}
```

- [ ] **Step 2: Build Documents page**

Replace `frontend/src/pages/Documents.tsx`:

```tsx
import { useState } from "react";
import { Search, Sparkles, BookOpen, AlertCircle } from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { CitationCard } from "@/components/CitationCard";
import {
  useDocumentSearch,
  useDocumentStats,
  type DocumentSearchResponse,
} from "@/hooks/useDocuments";

const SUGGESTED_QUERIES = [
  "What caused the Deepwater Horizon explosion?",
  "BSEE recommendations for subsea BOP maintenance",
  "Gas release incidents involving production platforms",
  "Crane and lifting safety findings",
  "Well control incident investigation findings",
];

export default function Documents() {
  const [query, setQuery] = useState("");
  const [docType, setDocType] = useState<string>("all");
  const [searchResult, setSearchResult] =
    useState<DocumentSearchResponse | null>(null);

  const search = useDocumentSearch();
  const stats = useDocumentStats();

  const corpusStats = stats.data?.data;
  const isEmpty =
    !corpusStats || (corpusStats.total_chunks === 0);

  const handleSearch = (searchQuery?: string) => {
    const q = searchQuery || query;
    if (!q.trim()) return;

    search.mutate(
      {
        query: q,
        top_k: 5,
        doc_type: docType === "all" ? undefined : docType,
      },
      {
        onSuccess: (data) => {
          setSearchResult(data.data);
        },
      }
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSearch();
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <BookOpen className="h-6 w-6" />
          Document Intelligence
        </h1>
        <p className="text-muted-foreground mt-1">
          Search and analyze BSEE Safety Alerts and Investigation Reports with AI
        </p>
      </div>

      {/* Search bar */}
      <div className="flex gap-2">
        <Input
          placeholder="Search BSEE Safety Alerts and Investigation Reports..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={handleKeyDown}
          className="flex-1"
        />
        <Button
          onClick={() => handleSearch()}
          disabled={!query.trim() || search.isPending}
        >
          <Search className="h-4 w-4 mr-2" />
          Search
        </Button>
      </div>

      {/* Filter row */}
      <div className="flex items-center justify-between">
        <ToggleGroup
          type="single"
          value={docType}
          onValueChange={(v) => v && setDocType(v)}
        >
          <ToggleGroupItem value="all">All</ToggleGroupItem>
          <ToggleGroupItem value="safety_alert">Safety Alerts</ToggleGroupItem>
          <ToggleGroupItem value="investigation_report">
            Investigation Reports
          </ToggleGroupItem>
        </ToggleGroup>

        {/* Stats bar */}
        {corpusStats && !isEmpty && (
          <p className="text-xs text-muted-foreground">
            Searching across {corpusStats.total_documents} documents (
            {corpusStats.total_chunks} indexed passages)
          </p>
        )}
      </div>

      {/* Empty corpus warning */}
      {isEmpty && !stats.isLoading && (
        <Card className="border-yellow-200 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-950">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-yellow-600" />
            <div>
              <p className="font-medium text-sm">No documents indexed yet</p>
              <p className="text-xs text-muted-foreground">
                Run the ingestion pipeline to populate the document corpus.
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Loading state */}
      {search.isPending && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Sparkles className="h-5 w-5 animate-pulse text-primary" />
              <CardTitle className="text-base">Analyzing documents...</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="space-y-3">
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-5/6" />
            <Skeleton className="h-4 w-4/6" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-3/6" />
          </CardContent>
        </Card>
      )}

      {/* Error state */}
      {search.isError && (
        <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <div>
              <p className="font-medium text-sm">Search failed</p>
              <p className="text-xs text-muted-foreground">
                {search.error?.message || "An unexpected error occurred"}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* AI Answer */}
      {searchResult && !search.isPending && (
        <>
          <Card>
            <CardHeader>
              <div className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                <CardTitle className="text-base">AI Analysis</CardTitle>
              </div>
            </CardHeader>
            <CardContent>
              <div className="prose prose-sm dark:prose-invert max-w-none">
                <ReactMarkdown>{searchResult.answer}</ReactMarkdown>
              </div>
              <p className="text-xs text-muted-foreground mt-4">
                Generated at{" "}
                {new Date(searchResult.generated_at).toLocaleString()} &middot;{" "}
                {searchResult.doc_count} documents in corpus
              </p>
            </CardContent>
          </Card>

          {/* Citations */}
          {searchResult.citations.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold text-muted-foreground">
                Sources ({searchResult.citations.length})
              </h3>
              {searchResult.citations.map((citation, i) => (
                <CitationCard
                  key={`${citation.source_file}-${citation.page_number}-${i}`}
                  title={citation.title}
                  pageNumber={citation.page_number}
                  relevanceScore={citation.relevance_score}
                  excerpt={citation.excerpt}
                  sourceFile={citation.source_file}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* Suggested queries — shown when no search has been run */}
      {!searchResult && !search.isPending && !isEmpty && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Suggested Searches</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_QUERIES.map((sq) => (
                <Badge
                  key={sq}
                  variant="outline"
                  className="cursor-pointer hover:bg-primary/10 transition-colors py-1.5 px-3"
                  onClick={() => {
                    setQuery(sq);
                    handleSearch(sq);
                  }}
                >
                  {sq}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify frontend builds**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\frontend && npx tsc -b --noEmit`
Expected: No TypeScript errors

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/CitationCard.tsx frontend/src/pages/Documents.tsx
git commit -m "feat: build Documents page with RAG search, citations, and suggested queries"
```

---

## Chunk 4: PDF Report Export (Step 3.3)

### Task 12: Build report service

**Files:**
- Replace: `backend/services/report_service.py` (currently 9-line stub)

- [ ] **Step 1: Replace the stub with the full report service**

Replace `backend/services/report_service.py` entirely. This is the largest file — it generates charts with matplotlib and assembles a multi-page PDF with ReportLab.

```python
"""
PDF Report generation service.

Generates professional safety briefing PDFs with:
- Cover page with branding
- AI-written executive summary
- Matplotlib charts (incident trends, severity, normalized metrics)
- Data tables
- AI-written recommendations
"""
import io
import logging
import os
import sqlite3
from datetime import datetime, timezone

import matplotlib
matplotlib.use("Agg")  # headless rendering for Docker
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle,
    PageBreak, HRFlowable,
)

from services.claude_service import get_claude_service
from services.prompts import (
    REPORT_SUMMARY_SYSTEM, REPORT_SUMMARY_USER,
    REPORT_RECOMMENDATIONS_SYSTEM, REPORT_RECOMMENDATIONS_USER,
)


logger = logging.getLogger(__name__)

# Chart colors matching the web dashboard palette
COLORS = {
    "primary": "#3b82f6",      # blue-500
    "secondary": "#14b8a6",    # teal-500
    "accent": "#f59e0b",       # amber-500
    "danger": "#ef4444",       # red-500
    "muted": "#94a3b8",        # slate-400
    "bg": "#f8fafc",           # slate-50
}
SEVERITY_COLORS = ["#22c55e", "#f59e0b", "#ef4444", "#7c3aed"]


class ReportService:
    """Generates professional PDF safety briefing reports."""

    def __init__(self):
        """Zero-arg constructor — reads config from environment."""
        self.db_path = os.getenv("DATABASE_PATH", "./data/bsee.db")
        self.claude = get_claude_service()

    def _get_conn(self) -> sqlite3.Connection:
        """Open a read-only SQLite connection."""
        return sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)

    def _query_data(
        self,
        operator: str | None,
        year_start: int | None,
        year_end: int | None,
    ) -> dict:
        """Query all data needed for the report via pandas."""
        conn = self._get_conn()

        # Build WHERE clause
        conditions = []
        params = []
        if operator:
            conditions.append("OPERATOR_NAME = ?")
            params.append(operator)
        if year_start:
            conditions.append("YEAR >= ?")
            params.append(year_start)
        if year_end:
            conditions.append("YEAR <= ?")
            params.append(year_end)

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        # Incidents by year
        incidents_by_year = pd.read_sql(
            f"SELECT YEAR as year, COUNT(*) as count FROM incidents {where} GROUP BY YEAR ORDER BY YEAR",
            conn, params=params,
        )

        # Incidents by type (top 10)
        incidents_by_type = pd.read_sql(
            f"SELECT INCIDENT_TYPE as type, COUNT(*) as count FROM incidents {where} GROUP BY INCIDENT_TYPE ORDER BY count DESC LIMIT 10",
            conn, params=params,
        )

        # INCs by severity
        incs_by_severity = pd.read_sql(
            f"SELECT SEVERITY as severity, COUNT(*) as count FROM incs {where} GROUP BY SEVERITY ORDER BY count DESC",
            conn, params=params,
        )

        # Production data for normalization
        production_by_year = pd.read_sql(
            f"SELECT YEAR as year, SUM(OIL_BBL + GAS_MCF * 0.1781) as boe FROM production {where} GROUP BY YEAR ORDER BY YEAR",
            conn, params=params,
        )

        # Root causes (if available)
        try:
            root_causes = pd.read_sql(
                f"""SELECT rc.primary_cause as cause, COUNT(*) as count
                    FROM incident_root_causes rc
                    JOIN incidents i ON rc.incident_id = i.INCIDENT_ID
                    {where}
                    GROUP BY rc.primary_cause ORDER BY count DESC LIMIT 10""",
                conn, params=params,
            )
        except Exception:
            root_causes = pd.DataFrame()

        # Summary stats
        total_incidents = pd.read_sql(
            f"SELECT COUNT(*) as total, SUM(FATALITY_COUNT) as fatalities, SUM(INJ_COUNT) as injuries FROM incidents {where}",
            conn, params=params,
        )

        total_incs = pd.read_sql(
            f"SELECT COUNT(*) as total FROM incs {where}",
            conn, params=params,
        )

        conn.close()

        return {
            "incidents_by_year": incidents_by_year,
            "incidents_by_type": incidents_by_type,
            "incs_by_severity": incs_by_severity,
            "production_by_year": production_by_year,
            "root_causes": root_causes,
            "total_incidents": int(total_incidents["total"].iloc[0]) if len(total_incidents) else 0,
            "total_fatalities": int(total_incidents["fatalities"].iloc[0] or 0) if len(total_incidents) else 0,
            "total_injuries": int(total_incidents["injuries"].iloc[0] or 0) if len(total_incidents) else 0,
            "total_incs": int(total_incs["total"].iloc[0]) if len(total_incs) else 0,
            "operator": operator or "All GoM Operators",
            "year_start": year_start,
            "year_end": year_end,
        }

    def _build_data_summary_text(self, data: dict) -> str:
        """Build a text summary for AI prompts."""
        lines = [
            f"Operator: {data['operator']}",
            f"Total incidents: {data['total_incidents']}",
            f"Total fatalities: {data['total_fatalities']}",
            f"Total injuries: {data['total_injuries']}",
            f"Total INCs (violations): {data['total_incs']}",
        ]
        if not data["incidents_by_year"].empty:
            lines.append(f"Year range: {data['incidents_by_year']['year'].min()} - {data['incidents_by_year']['year'].max()}")
            lines.append(f"Incidents by year: {dict(zip(data['incidents_by_year']['year'], data['incidents_by_year']['count']))}")
        if not data["incidents_by_type"].empty:
            lines.append(f"Top incident types: {dict(zip(data['incidents_by_type']['type'], data['incidents_by_type']['count']))}")
        if not data["incs_by_severity"].empty:
            lines.append(f"INCs by severity: {dict(zip(data['incs_by_severity']['severity'], data['incs_by_severity']['count']))}")
        return "\n".join(lines)

    def _make_trend_chart(self, data: pd.DataFrame) -> io.BytesIO:
        """Generate incident trend line chart."""
        fig, ax = plt.subplots(figsize=(6.5, 3.5), dpi=150)
        ax.plot(data["year"], data["count"], marker="o", linewidth=2,
                color=COLORS["primary"], markersize=6)
        ax.fill_between(data["year"], data["count"], alpha=0.1, color=COLORS["primary"])
        ax.set_xlabel("Year", fontsize=10)
        ax.set_ylabel("Incident Count", fontsize=10)
        ax.set_title("Incident Trends Over Time", fontsize=12, fontweight="bold")
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        ax.yaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        ax.grid(axis="y", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def _make_severity_chart(self, data: pd.DataFrame) -> io.BytesIO:
        """Generate INC severity bar chart."""
        fig, ax = plt.subplots(figsize=(6.5, 3.5), dpi=150)
        bar_colors = SEVERITY_COLORS[: len(data)]
        ax.barh(data["severity"].astype(str), data["count"], color=bar_colors)
        ax.set_xlabel("Count", fontsize=10)
        ax.set_title("Violations by Severity", fontsize=12, fontweight="bold")
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def _make_normalized_chart(
        self, incidents: pd.DataFrame, production: pd.DataFrame
    ) -> io.BytesIO | None:
        """Generate incidents per million BOE chart."""
        if incidents.empty or production.empty:
            return None
        merged = incidents.merge(production, on="year", how="inner")
        merged = merged[merged["boe"] > 0]
        if merged.empty:
            return None
        merged["rate"] = merged["count"] / (merged["boe"] / 1_000_000)

        fig, ax = plt.subplots(figsize=(6.5, 3.5), dpi=150)
        ax.plot(merged["year"], merged["rate"], marker="s", linewidth=2,
                color=COLORS["secondary"], markersize=6)
        ax.fill_between(merged["year"], merged["rate"], alpha=0.1, color=COLORS["secondary"])
        ax.set_xlabel("Year", fontsize=10)
        ax.set_ylabel("Incidents per Million BOE", fontsize=10)
        ax.set_title("Production-Normalized Incident Rate", fontsize=12, fontweight="bold")
        ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
        ax.grid(axis="y", alpha=0.3)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def _make_root_cause_chart(self, data: pd.DataFrame) -> io.BytesIO | None:
        """Generate root cause pie chart."""
        if data.empty:
            return None
        fig, ax = plt.subplots(figsize=(6.5, 4), dpi=150)
        ax.pie(data["count"], labels=data["cause"], autopct="%1.0f%%",
               startangle=90, textprops={"fontsize": 8})
        ax.set_title("Root Cause Distribution", fontsize=12, fontweight="bold")
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    async def generate_report(
        self,
        operator: str | None = None,
        year_start: int | None = None,
        year_end: int | None = None,
        include_ai: bool = True,
    ) -> bytes:
        """Generate a complete PDF safety briefing. Returns PDF bytes."""
        # 1. Query data
        data = self._query_data(operator, year_start, year_end)

        if data["total_incidents"] == 0 and data["total_incs"] == 0:
            raise ValueError("No data found for the specified filters.")

        # 2. Generate charts
        charts = {}
        if not data["incidents_by_year"].empty:
            charts["trend"] = self._make_trend_chart(data["incidents_by_year"])
        if not data["incs_by_severity"].empty:
            charts["severity"] = self._make_severity_chart(data["incs_by_severity"])
        norm_chart = self._make_normalized_chart(
            data["incidents_by_year"], data["production_by_year"]
        )
        if norm_chart:
            charts["normalized"] = norm_chart
        root_chart = self._make_root_cause_chart(data["root_causes"])
        if root_chart:
            charts["root_cause"] = root_chart

        # 3. AI narrative (optional)
        summary_text = ""
        recommendations_text = ""
        if include_ai and self.claude.is_available:
            data_summary = self._build_data_summary_text(data)
            try:
                import asyncio
                summary_text = await asyncio.wait_for(
                    self.claude.generate(
                        system_prompt=REPORT_SUMMARY_SYSTEM,
                        user_prompt=REPORT_SUMMARY_USER.format(data_summary=data_summary),
                        max_tokens=1024,
                    ),
                    timeout=60,
                )
                recommendations_text = await asyncio.wait_for(
                    self.claude.generate(
                        system_prompt=REPORT_RECOMMENDATIONS_SYSTEM,
                        user_prompt=REPORT_RECOMMENDATIONS_USER.format(data_summary=data_summary),
                        max_tokens=1024,
                    ),
                    timeout=60,
                )
            except Exception as exc:
                logger.warning(f"AI generation failed for report: {exc}")
                summary_text = "AI analysis unavailable — data-only report."
                recommendations_text = ""

        # 4. Assemble PDF
        pdf_bytes = self._build_pdf(data, charts, summary_text, recommendations_text, include_ai)
        return pdf_bytes

    def _build_pdf(
        self,
        data: dict,
        charts: dict,
        summary: str,
        recommendations: str,
        include_ai: bool,
    ) -> bytes:
        """Assemble the final PDF with ReportLab."""
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=letter,
            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
            leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        )
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(
            "CoverTitle", parent=styles["Title"],
            fontSize=24, spaceAfter=12, textColor=colors.HexColor("#1e293b"),
        ))
        styles.add(ParagraphStyle(
            "SectionHead", parent=styles["Heading2"],
            fontSize=14, spaceAfter=8, textColor=colors.HexColor("#1e293b"),
        ))
        styles.add(ParagraphStyle(
            "BodyText2", parent=styles["BodyText"],
            fontSize=10, leading=14, spaceAfter=8,
        ))
        styles.add(ParagraphStyle(
            "SmallText", parent=styles["BodyText"],
            fontSize=8, leading=10, textColor=colors.HexColor("#64748b"),
        ))

        story = []
        now = datetime.now(timezone.utc)

        # --- Cover Page ---
        story.append(Spacer(1, 1.5 * inch))
        story.append(Paragraph("Gulf of Mexico", styles["CoverTitle"]))
        story.append(Paragraph("Safety Intelligence Report", styles["CoverTitle"]))
        story.append(Spacer(1, 0.3 * inch))
        story.append(HRFlowable(width="80%", thickness=2, color=colors.HexColor("#3b82f6")))
        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph(f"<b>Operator:</b> {data['operator']}", styles["BodyText2"]))
        yr_range = f"{data['year_start'] or 'All'} — {data['year_end'] or 'All'}"
        story.append(Paragraph(f"<b>Period:</b> {yr_range}", styles["BodyText2"]))
        story.append(Paragraph(f"<b>Generated:</b> {now.strftime('%B %d, %Y')}", styles["BodyText2"]))
        story.append(Spacer(1, 0.5 * inch))
        story.append(Paragraph("Powered by Beacon GoM — AI Safety &amp; Regulatory Intelligence", styles["SmallText"]))
        story.append(PageBreak())

        # --- Executive Summary ---
        story.append(Paragraph("Executive Summary", styles["SectionHead"]))
        if summary:
            for para in summary.split("\n\n"):
                story.append(Paragraph(para.strip(), styles["BodyText2"]))
        elif not include_ai:
            story.append(Paragraph("<i>AI analysis not included — data-only report.</i>", styles["BodyText2"]))
        story.append(Spacer(1, 0.3 * inch))

        # --- Incident Trends ---
        if "trend" in charts:
            story.append(Paragraph("Incident Trends", styles["SectionHead"]))
            story.append(Image(charts["trend"], width=6 * inch, height=3 * inch))
            story.append(Spacer(1, 0.2 * inch))

            # Summary table
            if not data["incidents_by_year"].empty:
                table_data = [["Year", "Incidents", "YoY Change"]]
                prev = None
                for _, row in data["incidents_by_year"].iterrows():
                    cnt = int(row["count"])
                    yoy = ""
                    if prev is not None and prev > 0:
                        change = ((cnt - prev) / prev) * 100
                        yoy = f"{change:+.1f}%"
                    table_data.append([str(int(row["year"])), str(cnt), yoy])
                    prev = cnt
                t = Table(table_data, colWidths=[1.5 * inch, 1.5 * inch, 1.5 * inch])
                t.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTSIZE", (0, 0), (-1, -1), 9),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("ALIGN", (1, 0), (-1, -1), "CENTER"),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ]))
                story.append(t)
            story.append(Spacer(1, 0.3 * inch))

        # --- Compliance Overview ---
        if "severity" in charts:
            story.append(Paragraph("Compliance Overview", styles["SectionHead"]))
            story.append(Image(charts["severity"], width=6 * inch, height=3 * inch))
            story.append(Spacer(1, 0.3 * inch))

        # --- Normalized Metrics ---
        if "normalized" in charts:
            story.append(Paragraph("Production-Normalized Metrics", styles["SectionHead"]))
            story.append(Image(charts["normalized"], width=6 * inch, height=3 * inch))
            story.append(Spacer(1, 0.3 * inch))

        # --- Root Cause Analysis ---
        if "root_cause" in charts:
            story.append(Paragraph("Root Cause Analysis", styles["SectionHead"]))
            story.append(Image(charts["root_cause"], width=6 * inch, height=3.5 * inch))
            story.append(Spacer(1, 0.3 * inch))

        # --- Recommendations ---
        if recommendations:
            story.append(Paragraph("Key Findings &amp; Recommendations", styles["SectionHead"]))
            for para in recommendations.split("\n"):
                if para.strip():
                    story.append(Paragraph(para.strip(), styles["BodyText2"]))
            story.append(Spacer(1, 0.3 * inch))

        # --- Data Sources ---
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
        story.append(Spacer(1, 0.1 * inch))
        story.append(Paragraph("Data Sources", styles["SmallText"]))
        story.append(Paragraph(
            "All data sourced from the Bureau of Safety and Environmental Enforcement (BSEE) "
            "public records at data.bsee.gov. This report is generated from public government data "
            "and does not constitute regulatory advice.",
            styles["SmallText"],
        ))

        doc.build(story)
        return buf.getvalue()


# ── Singleton ────────────────────────────────────────────────────────

_report_service: ReportService | None = None


def get_report_service() -> ReportService:
    """Get or create the singleton ReportService instance."""
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service
```

- [ ] **Step 2: Update services/__init__.py to include ReportService**

Update `backend/services/__init__.py`:

```python
from .claude_service import ClaudeService, get_claude_service, ClaudeServiceError, token_tracker
from .sql_service import SQLService, get_sql_service
from .rag_service import RAGService, get_rag_service
from .report_service import ReportService, get_report_service
```

- [ ] **Step 3: Verify import**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\backend && python -c "from services.report_service import get_report_service; print('OK')"`
Expected: `OK`

- [ ] **Step 4: Commit**

```bash
git add backend/services/report_service.py backend/services/__init__.py
git commit -m "feat: build PDF report service with ReportLab and matplotlib charts"
```

---

### Task 13: Build reports router

**Files:**
- Replace: `backend/routers/reports.py` (currently 9-line stub)

- [ ] **Step 1: Replace the stub with the full reports router**

Replace `backend/routers/reports.py`:

```python
"""
Report generation endpoint — produces professional PDF safety briefings
with charts, data tables, and optional AI narrative.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import io

from models.schemas import ReportRequest
from services.claude_service import get_claude_service
from services.report_service import get_report_service


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/generate")
async def generate_report(request: ReportRequest):
    """Generate a PDF safety briefing report."""
    # Check AI availability if AI is requested
    if request.include_ai:
        claude = get_claude_service()
        if not claude.is_available:
            raise HTTPException(
                status_code=503,
                detail={
                    "error": "AI service unavailable",
                    "detail": "Set OPENROUTER_API_KEY to enable AI analysis, "
                              "or set include_ai=false for data-only reports.",
                },
            )

    report_svc = get_report_service()

    try:
        pdf_bytes = await report_svc.generate_report(
            operator=request.operator,
            year_start=request.year_start,
            year_end=request.year_end,
            include_ai=request.include_ai,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "No data found", "detail": str(exc)},
        )
    except Exception as exc:
        logger.exception("Report generation failed")
        raise HTTPException(
            status_code=500,
            detail={"error": "Report generation failed", "detail": str(exc)},
        )

    # Build filename
    op_slug = (request.operator or "gom_wide").lower().replace(" ", "_")
    date_str = datetime.now(timezone.utc).strftime("%Y%m%d")
    filename = f"beacon_gom_report_{op_slug}_{date_str}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
```

- [ ] **Step 2: Verify router**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\backend && python -c "from routers.reports import router; print(f'{len(router.routes)} routes')"`
Expected: `1 routes`

- [ ] **Step 3: Commit**

```bash
git add backend/routers/reports.py
git commit -m "feat: build reports router with PDF streaming response"
```

---

### Task 14: Build Reports frontend page

**Files:**
- Replace: `frontend/src/pages/Reports.tsx` (currently 10-line stub)

- [ ] **Step 1: Replace the stub with the full Reports page**

Replace `frontend/src/pages/Reports.tsx`:

```tsx
import { useState } from "react";
import {
  FileText,
  Download,
  ExternalLink,
  Loader2,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { OperatorSelector } from "@/components/OperatorSelector";
import { useOperator } from "@/contexts/OperatorContext";

interface RecentReport {
  operator: string;
  yearStart: string;
  yearEnd: string;
  includeAI: boolean;
  generatedAt: Date;
  blobUrl: string;
  filename: string;
}

const YEARS = Array.from({ length: 11 }, (_, i) => String(2014 + i));

export default function Reports() {
  const { selectedOperator } = useOperator();
  const [yearStart, setYearStart] = useState("");
  const [yearEnd, setYearEnd] = useState("");
  const [includeAI, setIncludeAI] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [recentReports, setRecentReports] = useState<RecentReport[]>([]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);

    try {
      const response = await fetch("/api/reports/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          operator: selectedOperator || null,
          year_start: yearStart ? parseInt(yearStart) : null,
          year_end: yearEnd ? parseInt(yearEnd) : null,
          include_ai: includeAI,
        }),
      });

      if (!response.ok) {
        const errorData = await response
          .json()
          .catch(() => ({ detail: { error: "Report generation failed" } }));
        const detail = errorData.detail;
        throw new Error(
          typeof detail === "string"
            ? detail
            : detail?.detail || detail?.error || "Report generation failed"
        );
      }

      const blob = await response.blob();
      const blobUrl = URL.createObjectURL(blob);
      const opSlug = (selectedOperator || "gom_wide")
        .toLowerCase()
        .replace(/\s+/g, "_");
      const filename = `beacon_gom_report_${opSlug}_${new Date().toISOString().slice(0, 10)}.pdf`;

      // Trigger download
      const a = document.createElement("a");
      a.href = blobUrl;
      a.download = filename;
      a.click();

      // Save for re-download (don't revoke yet — user might want to re-download)
      setRecentReports((prev) => [
        {
          operator: selectedOperator || "All GoM",
          yearStart: yearStart || "All",
          yearEnd: yearEnd || "All",
          includeAI,
          generatedAt: new Date(),
          blobUrl,
          filename,
        },
        ...prev,
      ]);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to generate report"
      );
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <FileText className="h-6 w-6" />
          Safety Report Generator
        </h1>
        <p className="text-muted-foreground mt-1">
          Generate professional PDF safety briefings with charts and AI analysis
        </p>
      </div>

      {/* Configuration form */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Report Configuration</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Operator */}
          <div className="space-y-2">
            <Label>Operator</Label>
            <OperatorSelector />
            <p className="text-xs text-muted-foreground">
              Leave as "All GoM Operators" for a GoM-wide report
            </p>
          </div>

          {/* Year range */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Start Year</Label>
              <Select value={yearStart} onValueChange={setYearStart}>
                <SelectTrigger>
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  {YEARS.map((y) => (
                    <SelectItem key={y} value={y}>
                      {y}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>End Year</Label>
              <Select value={yearEnd} onValueChange={setYearEnd}>
                <SelectTrigger>
                  <SelectValue placeholder="All" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All</SelectItem>
                  {YEARS.map((y) => (
                    <SelectItem key={y} value={y}>
                      {y}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Include AI toggle */}
          <div className="flex items-center space-x-3">
            <Switch
              id="include-ai"
              checked={includeAI}
              onCheckedChange={setIncludeAI}
            />
            <Label htmlFor="include-ai">Include AI Analysis</Label>
            <span className="text-xs text-muted-foreground">
              {includeAI
                ? "Executive summary & recommendations (takes 15-30s)"
                : "Data & charts only (faster)"}
            </span>
          </div>

          {/* Generate button */}
          <Button
            onClick={handleGenerate}
            disabled={generating}
            className="w-full"
            size="lg"
          >
            {generating ? (
              <>
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                Generating report...
              </>
            ) : (
              <>
                <FileText className="h-4 w-4 mr-2" />
                Generate Report
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Generation progress */}
      {generating && (
        <Card className="border-blue-200 bg-blue-50 dark:border-blue-800 dark:bg-blue-950">
          <CardContent className="p-4 flex items-center gap-3">
            <Loader2 className="h-5 w-5 animate-spin text-blue-600" />
            <div>
              <p className="font-medium text-sm">Generating report...</p>
              <p className="text-xs text-muted-foreground">
                {includeAI
                  ? "This may take 15-30 seconds (AI analysis in progress)"
                  : "This should take a few seconds"}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Error */}
      {error && (
        <Card className="border-red-200 bg-red-50 dark:border-red-800 dark:bg-red-950">
          <CardContent className="p-4 flex items-center gap-3">
            <AlertCircle className="h-5 w-5 text-red-600" />
            <div>
              <p className="font-medium text-sm">Generation failed</p>
              <p className="text-xs text-muted-foreground">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Recent reports */}
      {recentReports.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Recent Reports</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {recentReports.map((report, i) => (
              <div
                key={i}
                className="flex items-center justify-between p-3 rounded-md bg-muted/50"
              >
                <div>
                  <p className="text-sm font-medium">{report.operator}</p>
                  <p className="text-xs text-muted-foreground">
                    {report.yearStart} — {report.yearEnd}
                    {report.includeAI && (
                      <Badge variant="secondary" className="ml-2 text-xs">
                        AI
                      </Badge>
                    )}
                    <span className="ml-2">
                      {report.generatedAt.toLocaleTimeString()}
                    </span>
                  </p>
                </div>
                <div className="flex gap-2">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={() => {
                      const a = document.createElement("a");
                      a.href = report.blobUrl;
                      a.download = report.filename;
                      a.click();
                    }}
                  >
                    <Download className="h-3 w-3 mr-1" />
                    Download
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => window.open(report.blobUrl, "_blank")}
                  >
                    <ExternalLink className="h-3 w-3 mr-1" />
                    Preview
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Verify frontend builds**

Run: `cd E:\AiGNITE\projects\Beacon_GoM\frontend && npx tsc -b --noEmit`
Expected: No TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/Reports.tsx
git commit -m "feat: build Reports page with PDF configuration, generation, and download"
```

---

## Chunk 5: Integration & Docker Verification

### Task 15: Docker rebuild and end-to-end test

- [ ] **Step 1: Rebuild Docker images**

Run:
```bash
cd E:\AiGNITE\projects\Beacon_GoM
docker compose down -v
docker compose build --no-cache
docker compose up -d
```
Wait for all 3 containers to be healthy.

- [ ] **Step 2: Verify health endpoint includes ChromaDB**

Run: `curl -s http://localhost/health | python -m json.tool`
Expected: JSON with `"documents_indexed"` field

- [ ] **Step 3: Verify document stats endpoint**

Run: `curl -s http://localhost/api/documents/stats | python -m json.tool`
Expected: JSON with `total_documents`, `total_chunks` > 0 (if PDFs downloaded successfully)

- [ ] **Step 4: Test RAG search**

Run:
```bash
curl -s -X POST http://localhost/api/documents/search \
  -H "Content-Type: application/json" \
  -d '{"query": "What are BSEE safety recommendations?", "top_k": 3}'
```
Expected: JSON with `answer` (AI-written with citations) and `citations` array

- [ ] **Step 5: Test report generation**

Run:
```bash
curl -s -X POST http://localhost/api/reports/generate \
  -H "Content-Type: application/json" \
  -d '{"operator": "CHEVRON USA INC", "include_ai": true}' \
  -o test_report.pdf
```
Expected: `test_report.pdf` created. Open it — should have cover page, charts, AI narrative.

- [ ] **Step 6: Test report without AI**

Run:
```bash
curl -s -X POST http://localhost/api/reports/generate \
  -H "Content-Type: application/json" \
  -d '{"operator": "CHEVRON USA INC", "include_ai": false}' \
  -o test_report_no_ai.pdf
```
Expected: PDF without AI sections, generates faster.

- [ ] **Step 7: Verify frontend pages load**

Open `http://localhost` in browser:
- Navigate to Documents page — should show search bar and suggested queries
- Navigate to Reports page — should show configuration form
- Test a document search
- Test report generation and download

- [ ] **Step 8: Final commit with any fixes**

```bash
git add -A
git commit -m "feat: Phase 3 complete — document intelligence, RAG search, PDF reports"
```
