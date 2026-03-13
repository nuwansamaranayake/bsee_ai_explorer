# Phase 3: Document Intelligence + PDF Reports — Design Spec

**Date:** 2026-03-12
**Scope:** Steps 3.1, 3.2, 3.3 (PDF ingestion, RAG search, PDF report export)
**Status:** Approved
**Review:** Passed spec review (all Critical/Important issues resolved)

---

## 1. Overview

Add three major features to Beacon GoM:

1. **PDF Download & Ingestion** — Download BSEE Safety Alerts and Investigation Reports via curated manifest, extract text with PyMuPDF, chunk with LangChain, store in ChromaDB for semantic search.
2. **RAG Document Search** — Full-stack document intelligence: user queries ChromaDB via semantic search, Claude synthesizes an answer with inline citations, frontend displays answer + citation cards.
3. **PDF Report Export** — Generate professional multi-page PDF safety briefings with matplotlib charts and AI-written narrative, downloadable from the browser.

## 2. Constraints & Decisions

| Decision | Choice | Rationale |
|---|---|---|
| PDF sourcing | Curated `pdf_manifest.json` | Reliable, deterministic, testable. No fragile web scraping. |
| Embedding model | ChromaDB default (all-MiniLM-L6-v2 via ONNX) | Already bundled — onnxruntime is in requirements.txt. Zero new deps. |
| PDF generation | ReportLab + matplotlib | Battle-tested, no system deps (unlike WeasyPrint). |
| AI provider | OpenRouter via `openai.AsyncOpenAI` | Existing pattern. All AI calls go through `ClaudeService`. |
| Embedding provider | Local ONNX (NOT OpenRouter) | Spec requirement. No cost per ingestion run. |
| ChromaDB sync queries | Wrapped in `asyncio.to_thread()` | ChromaDB's `collection.query()` is synchronous — must not block the event loop. |
| Report endpoint verb | POST (not GET) | Report generation has side effects (AI calls, resource consumption). Consistent with `/api/analyze/trends`. |
| DB access in ReportService | Raw `sqlite3`/`pandas.read_sql` | Chart data needs aggregate queries easier in raw SQL than ORM. Explicit departure from ORM pattern. |

## 3. Step 3.1 — PDF Download & Ingestion Pipeline

### 3.1.1 New Files

| File | Purpose |
|---|---|
| `backend/etl/pdf_manifest.json` | Curated list of BSEE PDF URLs with version field |
| `backend/etl/download_safety_alerts.py` | Downloads PDFs from manifest |
| `backend/etl/ingest_pdfs.py` | Replaces stub. Full ingestion pipeline. |

### 3.1.2 PDF Manifest Structure

```json
{
  "version": "1.0",
  "last_updated": "2026-03-12",
  "safety_alerts": [
    {
      "url": "https://www.bsee.gov/sites/bsee.gov/files/safety-alert/...",
      "filename": "safety_alert_458.pdf",
      "alert_number": "458",
      "title": "Safety Alert No. 458 - Crane Operations"
    }
  ],
  "investigation_reports": [
    {
      "url": "https://www.bsee.gov/sites/bsee.gov/files/...",
      "filename": "investigation_report_deepwater_2023.pdf",
      "title": "District Investigation Report - Deepwater Incident 2023"
    }
  ]
}
```

**Target corpus:** 30-50 Safety Alerts + 20-30 Investigation Reports.

### 3.1.3 Download Pipeline (`download_safety_alerts.py`)

- Reads `pdf_manifest.json` from same directory
- Creates output dirs: `backend/data/pdfs/safety_alerts/`, `backend/data/pdfs/investigation_reports/`
- Uses `httpx.AsyncClient` with 3 retries, exponential backoff (1s, 2s, 4s)
- **Idempotent:** Skips download if file exists and size > 0
- Prints summary: `{found} PDFs in manifest, {downloaded} downloaded, {skipped} already exist, {failed} failed`
- Runnable as: `python -m etl.download_safety_alerts`

### 3.1.4 Ingestion Pipeline (`ingest_pdfs.py`)

**Three-stage pipeline:**

1. **Extract** (PyMuPDF/fitz):
   - Opens each PDF, extracts text page-by-page via `page.get_text()`
   - Extracts metadata: `title` (from manifest or first line), `date` (regex `\d{1,2}/\d{1,2}/\d{4}` or `\w+ \d{1,2}, \d{4}`), `doc_type` (safety_alert | investigation_report), `alert_number`, `source_file`
   - Handles malformed PDFs: log warning, skip, continue
   - Strips common headers/footers using patterns:
     - Lines matching `r"^U\.S\. Department of the Interior"` or `r"^Bureau of Safety"`
     - Lines matching `r"^Page \d+ of \d+$"` or `r"^\d+$"` (standalone page numbers)
     - Lines matching `r"^BSEE\s"`

2. **Chunk** (LangChain):
   - `RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50, length_function=len)`
   - Each chunk carries metadata dict: `{source_file, page_number, doc_type, alert_number, date, title}`

3. **Embed & Store** (ChromaDB):
   - `chromadb.PersistentClient(path=CHROMA_PATH)`
   - Collection: `bsee_documents` (get_or_create)
   - Uses ChromaDB default embedding function (ONNX all-MiniLM-L6-v2)
   - Chunk IDs: `{source_file}_chunk_{i}` for deterministic deduplication
   - **Idempotent:** Checks if any chunk with matching `source_file` exists. Skips if present.
   - **`--force` flag:** Deletes existing chunks for the document before re-ingesting

**Runnable as:** `python -m etl.ingest_pdfs` or `python -m etl.ingest_pdfs --force`

### 3.1.5 Docker Integration

- `start.sh` updated: after DB seed, run `python -m etl.download_safety_alerts` then `python -m etl.ingest_pdfs` (only if ChromaDB collection doesn't exist or is empty)
- **Important:** Ingestion runs and completes BEFORE uvicorn starts. Only one process holds the ChromaDB client at a time — no concurrent access conflicts.
- ChromaDB data persists in the `chroma_data` Docker volume

### 3.1.6 Exit Criteria

- 30+ PDFs downloaded to `data/pdfs/`
- ChromaDB `bsee_documents` collection has 500+ chunks
- `col.query(query_texts=["subsea equipment failure"], n_results=3)` returns relevant results with correct metadata
- Pipeline is idempotent (re-run downloads 0, ingests 0)

---

## 4. Step 3.2 — RAG Search Endpoint & Documents Page

### 4.1 Backend

#### 4.1.1 `services/rag_service.py` (replace stub)

```python
import asyncio
import os
import chromadb
from services.claude_service import ClaudeService, get_claude_service

class RAGService:
    def __init__(self):
        """Zero-arg constructor matching existing singleton pattern."""
        chroma_path = os.getenv("CHROMA_PATH", "./data/chroma")
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection("bsee_documents")
        self.claude = get_claude_service()

    async def search(self, query: str, top_k: int = 5,
                     doc_type: str | None = None) -> dict:
        """Full RAG pipeline: query -> retrieve -> synthesize -> cite"""
        # 1. Query ChromaDB (wrap sync call to avoid blocking event loop)
        where_filter = {"doc_type": doc_type} if doc_type else None
        results = await asyncio.to_thread(
            self.collection.query,
            query_texts=[query], n_results=top_k, where=where_filter,
            include=["documents", "metadatas", "distances"]
        )
        # 2. Build context string from chunks + metadata
        # 3. Call claude_service.generate() with RAG prompt
        # 4. Build citation objects from metadata
        # 5. Return {answer, citations, query, doc_count, generated_at}

    def get_stats(self) -> dict:
        """Corpus statistics for the frontend stats bar."""
        # Returns: total_documents, total_chunks, by_type counts,
        #          oldest_document_date, newest_document_date

# Singleton
_rag_service: RAGService | None = None

def get_rag_service() -> RAGService:
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
```

**Key design notes:**
- Zero-arg constructor reads `CHROMA_PATH` from env (matching `ClaudeService` pattern)
- `get_rag_service()` factory following existing `get_claude_service()` pattern
- `search()` wraps `collection.query()` in `asyncio.to_thread()` to prevent event loop blocking
- `get_stats()` includes `oldest_document_date` and `newest_document_date`

#### 4.1.2 Prompt Templates (add to `services/prompts.py`)

```python
RAG_SYSTEM = """You are a BSEE document analyst. Answer the user's question
using ONLY the provided document excerpts. For every claim, cite the source
using: [Source: {document_title}, Page {page_number}]. If the documents don't
contain enough information, say so clearly. Do not make up information."""

RAG_USER = """Question: {query}

Document Excerpts:
{context}

Provide a thorough answer with citations to the specific documents and pages above."""
```

#### 4.1.3 `routers/documents.py` (replace stub)

Two endpoints:

**`POST /api/documents/search`**
- Request: `DocumentSearchRequest(query: str, top_k: int = 5, doc_type: str | None = None)`
- Response envelope: `{ data: DocumentSearchResponse, meta: {} }`
- `DocumentSearchResponse`: `{ answer: str, citations: list[Citation], query: str, doc_count: int, generated_at: str }`
- `Citation`: `{ source_file: str, title: str, page_number: int, relevance_score: float, excerpt: str }`
- Relevance score: normalized from ChromaDB distance (1 - distance, clamped to 0-1)
- **AI availability check:** If `claude_service` is not available, return 503 with `{"error": "AI service unavailable", "detail": "No API key configured"}` (matching analyze.py pattern)
- **Empty corpus check:** If ChromaDB collection is empty, return 404 with `{"error": "No documents indexed", "detail": "Run the ingestion pipeline first"}`

**`GET /api/documents/stats`**
- Response: `{ data: { total_documents: int, total_chunks: int, safety_alerts: int, investigation_reports: int, oldest_date: str | null, newest_date: str | null } }`

#### 4.1.4 Pydantic Models

Add to `models/schemas.py`:
- `DocumentSearchRequest`
- `Citation`
- `DocumentSearchResponse`
- `DocumentStatsResponse`

#### 4.1.5 Service Registration

Update `backend/services/__init__.py` to export:
```python
from .claude_service import ClaudeService, get_claude_service
from .sql_service import SQLService, get_sql_service
from .rag_service import RAGService, get_rag_service
from .report_service import ReportService, get_report_service
```

### 4.2 Frontend

#### 4.2.1 `hooks/useDocuments.ts` (new file)

```typescript
import { useMutation, useQuery } from "@tanstack/react-query";
import { apiClient, type ApiResponse } from "@/lib/api";

interface Citation {
  source_file: string;
  title: string;
  page_number: number;
  relevance_score: number;
  excerpt: string;
}

interface DocumentSearchResponse {
  answer: string;
  citations: Citation[];
  query: string;
  doc_count: number;
  generated_at: string;
}

interface DocumentStats {
  total_documents: number;
  total_chunks: number;
  safety_alerts: number;
  investigation_reports: number;
  oldest_date: string | null;
  newest_date: string | null;
}

// Mutation hook for document search
export function useDocumentSearch() {
  return useMutation({
    mutationFn: (params: { query: string; top_k?: number; doc_type?: string }) =>
      apiClient<ApiResponse<DocumentSearchResponse>>("/api/documents/search", {
        method: "POST",
        body: JSON.stringify(params),
      }),
  });
}

// Query hook for corpus stats
export function useDocumentStats() {
  return useQuery({
    queryKey: ["document-stats"],
    queryFn: () => apiClient<ApiResponse<DocumentStats>>("/api/documents/stats"),
    staleTime: 5 * 60 * 1000,
  });
}
```

**Note:** Uses `apiClient` from `@/lib/api` (existing pattern), NOT `api.post`/`api.get`.

#### 4.2.2 `pages/Documents.tsx` (replace stub)

Layout (top to bottom):
1. **Page header:** "Document Intelligence" with description
2. **Search bar:** shadcn/ui Input + Button. Placeholder: "Search BSEE Safety Alerts and Investigation Reports..."
3. **Filter row:** ToggleGroup with "All" | "Safety Alerts" | "Investigation Reports"
4. **Stats bar:** Small text: "Searching across {doc_count} documents ({chunk_count} indexed passages)"
5. **AI Answer panel:** Card with react-markdown rendered answer. Skeleton while loading. (`react-markdown` already in `package.json`, used by Chat.tsx)
6. **Citations list:** Array of CitationCard components below the answer
7. **Empty state:** When no search run, show 5 suggested query chips:
   - "What caused the Deepwater Horizon explosion?"
   - "BSEE recommendations for subsea BOP maintenance"
   - "Gas release incidents involving production platforms"
   - "Crane and lifting safety findings"
   - "Well control incident investigation findings"

#### 4.2.3 `components/CitationCard.tsx` (replace stub)

Props: `{ title, pageNumber, relevanceScore, excerpt, sourceFile }`

- shadcn/ui Card with Badge for relevance percentage
- Document icon + title + "Page {n}"
- 2-3 line excerpt preview (truncated)
- Click to expand: shows full chunk text in a Collapsible
- Relevance score shown as colored badge (green > 80%, yellow > 60%, red < 60%)

### 4.3 Exit Criteria

- Documents page renders with search bar, filter, and empty state
- Typing a query returns AI answer with inline citations
- Citations show document name, page number, relevance score, excerpt
- Document type filter restricts results to selected type
- Suggested query chips are clickable and trigger search
- Error state shown if ChromaDB is empty or search fails

---

## 5. Step 3.3 — PDF Report Export

### 5.1 New Dependencies

**Backend** (`requirements.txt`):
- `reportlab>=4.0`
- `matplotlib>=3.8`

**Frontend:** No new dependencies needed. `react-markdown` already present.

### 5.2 Backend

#### 5.2.1 `services/report_service.py` (replace stub)

```python
import os
from services.claude_service import ClaudeService, get_claude_service

class ReportService:
    def __init__(self):
        """Zero-arg constructor matching singleton pattern."""
        self.db_path = os.getenv("DATABASE_PATH", "./data/bsee.db")
        self.claude = get_claude_service()

    async def generate_report(
        self, operator: str | None, year_start: int | None,
        year_end: int | None, include_ai: bool = True
    ) -> bytes:
        """Generate a complete PDF safety briefing.
        Uses raw sqlite3/pandas for aggregate chart queries
        (easier than ORM for chart data aggregations).
        """
        # 1. Query SQLite via pandas.read_sql for filtered data
        # 2. Generate matplotlib charts as PNG BytesIO
        # 3. If include_ai: call Claude for executive summary + recommendations
        # 4. Assemble PDF with ReportLab
        # 5. Return PDF bytes

# Singleton
_report_service: ReportService | None = None

def get_report_service() -> ReportService:
    global _report_service
    if _report_service is None:
        _report_service = ReportService()
    return _report_service
```

**Key design note:** Uses `pandas.read_sql` with `sqlite3` connection directly (not SQLAlchemy ORM). This is an intentional departure from the ORM pattern because chart data queries involve GROUP BY, COUNT, and pivoting that are much cleaner in raw SQL + pandas than through the ORM.

#### 5.2.2 PDF Structure (ReportLab)

8 sections in order:

1. **Cover page:** Title "Gulf of Mexico Safety Intelligence Report", operator name (or "GoM-Wide"), date range, generation timestamp, "Powered by Beacon GoM" branding, horizontal rule
2. **Executive Summary:** AI-written 2-3 paragraph overview (or "AI analysis not included — data-only report" if `include_ai=false`)
3. **Incident Trends:** Matplotlib line chart (incidents by year). Summary table: year, count, YoY change
4. **Compliance Overview:** Bar chart of INCs by severity. Text comparison to GoM average
5. **Production-Normalized Metrics:** Line chart of incidents/million BOE. Trend direction text
6. **Root Cause Analysis:** Pie chart of root cause distribution (if categorization data exists). Top 3 root causes listed
7. **Key Findings & Recommendations:** AI-written 3-5 actionable recommendations (or skipped if `include_ai=false`)
8. **Data Sources:** Footnote listing BSEE sources. Disclaimer about public government records

#### 5.2.3 Matplotlib Chart Style

- Professional, clean (seaborn-v0_8 or custom style)
- Color palette matching web dashboard: blues, teals, grays
- Charts rendered to `BytesIO` as PNG, embedded in PDF via ReportLab `Image()`
- Figure size: 6.5" x 3.5" (fits letter-width PDF with margins)
- DPI: 150 (good quality without huge file size)
- `matplotlib.use('Agg')` for headless rendering in Docker

#### 5.2.4 `routers/reports.py` (replace stub)

**`POST /api/reports/generate`** (POST, not GET — has side effects: AI calls, resource consumption)
- Request body:
  ```python
  class ReportRequest(BaseModel):
      operator: str | None = None
      year_start: int | None = None
      year_end: int | None = None
      include_ai: bool = True
  ```
- Returns: `StreamingResponse(content=pdf_bytes, media_type="application/pdf")`
- `Content-Disposition: attachment; filename="beacon_gom_report_{operator}_{date}.pdf"`
- **AI availability check:** If `include_ai=true` and claude is not available, return 503
- **Empty data check:** If no data matches filters, return 404 with error message
- **Timeout:** Claude calls wrapped with `asyncio.wait_for(coro, timeout=60)` to prevent indefinite hangs

#### 5.2.5 AI Prompts for Report

Add to `services/prompts.py`:

```python
REPORT_SUMMARY_SYSTEM = """You are a safety intelligence analyst writing an
executive summary for a Gulf of Mexico safety report. Write professionally
and concisely, suitable for HSE leadership."""

REPORT_SUMMARY_USER = """Write a 2-3 paragraph executive summary based on this data:
{data_summary}
Focus on key trends, areas of concern, and notable improvements."""

REPORT_RECOMMENDATIONS_SYSTEM = """You are a safety consultant providing
actionable recommendations based on Gulf of Mexico safety data."""

REPORT_RECOMMENDATIONS_USER = """Based on this safety data, provide 3-5
specific, actionable recommendations:
{data_summary}
Format as a numbered list. Each recommendation should be concrete and implementable."""
```

### 5.3 Frontend

#### 5.3.1 `pages/Reports.tsx` (replace stub)

Layout:
1. **Page header:** "Safety Report Generator" with description
2. **Configuration form** (shadcn/ui Card):
   - Operator selector (reuse `OperatorSelector`, default "GoM-Wide")
   - Year range: two Select dropdowns (start year, end year) populated from 2014-2024
   - "Include AI Analysis" Switch toggle (default on)
   - "Generate Report" Button with FileText icon
3. **Generation state:** When generating, show a Card with Loader2 spinner and text "Generating report... This may take 15-30 seconds"
4. **Download:** When ready, show "Download Report" button + "Open in New Tab" link
5. **Recent reports:** List of reports generated in this session (React state array) with re-download links
6. **Error handling:** Toast notification if generation fails

#### 5.3.2 Download Logic

```typescript
const handleGenerate = async () => {
  setGenerating(true);
  setError(null);
  try {
    const response = await fetch("/api/reports/generate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        operator: operator || null,
        year_start: yearStart || null,
        year_end: yearEnd || null,
        include_ai: includeAI,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({
        error: "Report generation failed",
      }));
      throw new Error(errorData.detail || errorData.error);
    }

    const blob = await response.blob();
    const downloadUrl = URL.createObjectURL(blob);

    // Trigger download via hidden anchor
    const a = document.createElement("a");
    a.href = downloadUrl;
    a.download = `beacon_gom_report_${operator || "gom_wide"}_${new Date().toISOString().slice(0, 10)}.pdf`;
    a.click();

    // Cleanup
    URL.revokeObjectURL(downloadUrl);

    // Add to recent reports list
    setRecentReports((prev) => [
      { operator, yearStart, yearEnd, includeAI, generatedAt: new Date() },
      ...prev,
    ]);
  } catch (err) {
    setError(err instanceof Error ? err.message : "Failed to generate report");
  } finally {
    setGenerating(false);
  }
};
```

**Note:** Uses raw `fetch` (not `apiClient`) because `apiClient` calls `response.json()` which fails on binary PDF responses. Includes full error handling, Object URL cleanup, and loading state management.

### 5.4 Exit Criteria

- Clicking "Generate Report" produces a multi-page PDF
- PDF includes cover page, charts, data tables, and AI narrative
- Charts are professionally styled and readable
- `include_ai=false` mode works (faster, no API cost)
- Browser download triggers correctly
- Report looks professional enough to email to leadership

---

## 6. File Change Summary

### New Files
| File | Description |
|---|---|
| `backend/etl/pdf_manifest.json` | Curated BSEE PDF URLs with version tracking |
| `backend/etl/download_safety_alerts.py` | PDF download script |
| `frontend/src/hooks/useDocuments.ts` | Document search + stats hooks |

### Replaced Stubs
| File | From | To |
|---|---|---|
| `backend/etl/ingest_pdfs.py` | NotImplementedError | Full ingestion pipeline |
| `backend/services/rag_service.py` | NotImplementedError | Full RAG service with singleton |
| `backend/services/report_service.py` | NotImplementedError | Full PDF generation with singleton |
| `backend/routers/documents.py` | Empty stub | Two endpoints (search + stats) |
| `backend/routers/reports.py` | Empty stub | One endpoint (POST generate) |
| `frontend/src/pages/Documents.tsx` | Placeholder text | Full search UI |
| `frontend/src/pages/Reports.tsx` | Placeholder text | Full report config + download UI |
| `frontend/src/components/CitationCard.tsx` | Empty stub | Expandable citation card |

### Modified Files
| File | Change |
|---|---|
| `backend/requirements.txt` | Add reportlab, matplotlib |
| `backend/services/prompts.py` | Add RAG + report prompt templates |
| `backend/services/__init__.py` | Export RAGService, ReportService singletons |
| `backend/models/schemas.py` | Add document/report Pydantic models |
| `backend/main.py` | Wire RAGService and ReportService, add ChromaDB to health check |
| `backend/start.sh` | Add PDF download + ingest on first boot (before uvicorn) |

---

## 7. Dependencies Between Steps

```
Step 3.1 (PDF Download + Ingest) <- Independent, start first
         |
Step 3.2 (RAG Search + Documents Page) <- Depends on 3.1 (needs ChromaDB data)
         |
Step 3.3 (PDF Report Export) <- Can run parallel with 3.2 (uses SQLite, not ChromaDB)
```

Step 3.3 only depends on the existing Phase 2 data (SQLite incidents/INCs/production), NOT on ChromaDB. It can be built in parallel with Step 3.2 after 3.1 is done.

---

## 8. Testing Strategy

Each step has its own verification:

- **3.1:** Run download + ingest scripts, verify ChromaDB collection size and query results
- **3.2:** curl POST to `/api/documents/search`, verify AI answer + citations structure. Verify 503 when AI unavailable. Verify empty corpus 404.
- **3.3:** curl POST to `/api/reports/generate`, verify PDF downloads and contains expected sections. Test `include_ai=false` mode.

Comprehensive test suite (Step 3.5) is deferred to the next session per scope agreement.
