from typing import Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    data: T
    meta: dict | None = None


class APIError(BaseModel):
    error: str
    detail: str | None = None
    status: int


class Operator(BaseModel):
    id: str
    name: str
    incident_count: int = 0
    inc_count: int = 0


class Incident(BaseModel):
    id: str
    date: str
    operator: str
    description: str = ""
    severity: str = ""


class INC(BaseModel):
    id: str
    date: str
    operator: str
    inc_type: str = ""
    status: str = ""


class Platform(BaseModel):
    id: str
    name: str
    operator: str
    area: str = ""
    block: str = ""
    inc_count: int = 0


class Production(BaseModel):
    operator: str
    year: int
    month: int
    oil_bbl: float = 0.0
    gas_mcf: float = 0.0
    boe: float = 0.0


# ---------------------------------------------------------------------------
# Step 3.2 — Document Search
# ---------------------------------------------------------------------------

class DocumentSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    top_k: int = Field(default=5, ge=1, le=20)
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


# ---------------------------------------------------------------------------
# Step 3.3 — PDF Report
# ---------------------------------------------------------------------------

class ReportRequest(BaseModel):
    operator: str | None = Field(default=None, max_length=200)
    year_start: int | None = Field(default=None, ge=1950, le=2100)
    year_end: int | None = Field(default=None, ge=1950, le=2100)
    include_ai: bool = True
