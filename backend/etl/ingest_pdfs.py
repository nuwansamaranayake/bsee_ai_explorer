"""Ingest BSEE PDF documents into ChromaDB for RAG search.

Three-stage pipeline: Extract (PyMuPDF) → Chunk (LangChain) → Store (ChromaDB).

Usage:
    python -m etl.ingest_pdfs           # Idempotent — skips already-ingested docs
    python -m etl.ingest_pdfs --force   # Re-ingest all documents
"""

import json
import logging
import os
import re
import sys
from pathlib import Path

import chromadb
import fitz  # PyMuPDF
from langchain.text_splitter import RecursiveCharacterTextSplitter

logger = logging.getLogger(__name__)

PDF_BASE_PATH = Path(os.getenv("PDF_PATH", "./data/pdfs"))
CHROMA_PATH = os.getenv("CHROMA_PATH", "./data/chroma")
MANIFEST_PATH = Path(__file__).parent / "pdf_manifest.json"

# Patterns to strip from extracted text
STRIP_PATTERNS = [
    re.compile(r"^U\.S\. Department of the Interior.*$", re.MULTILINE),
    re.compile(r"^Bureau of Safety.*$", re.MULTILINE),
    re.compile(r"^Page \d+ of \d+$", re.MULTILINE),
    re.compile(r"^\d+$", re.MULTILINE),  # Standalone page numbers
    re.compile(r"^BSEE\s.*$", re.MULTILINE),
]

# Date extraction patterns
DATE_PATTERNS = [
    re.compile(r"\b(\d{1,2}/\d{1,2}/\d{4})\b"),
    re.compile(r"\b(\w+ \d{1,2}, \d{4})\b"),
    re.compile(r"\b(\d{4}-\d{2}-\d{2})\b"),
]


def _clean_text(text: str) -> str:
    """Strip headers, footers, and page numbers."""
    for pattern in STRIP_PATTERNS:
        text = pattern.sub("", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_date(text: str) -> str | None:
    """Try to extract a date from the first page of text."""
    # Only search first 500 chars
    snippet = text[:500]
    for pattern in DATE_PATTERNS:
        match = pattern.search(snippet)
        if match:
            return match.group(1)
    return None


def _build_manifest_lookup() -> dict[str, dict]:
    """Build filename → manifest entry lookup."""
    if not MANIFEST_PATH.exists():
        return {}
    manifest = json.loads(MANIFEST_PATH.read_text())
    lookup = {}
    for doc_type in ("safety_alerts", "investigation_reports"):
        for entry in manifest.get(doc_type, []):
            lookup[entry["filename"]] = entry
    return lookup


def extract_pdf(pdf_path: Path, manifest_entry: dict | None) -> dict | None:
    """Extract text and metadata from a single PDF."""
    try:
        doc = fitz.open(str(pdf_path))
    except Exception as e:
        logger.warning("Failed to open PDF %s: %s", pdf_path.name, e)
        return None

    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        cleaned = _clean_text(text)
        if cleaned:
            pages.append({"page_number": page_num + 1, "text": cleaned})

    doc.close()

    if not pages:
        logger.warning("No text extracted from %s", pdf_path.name)
        return None

    full_text = "\n\n".join(p["text"] for p in pages)

    # Determine doc_type from parent directory
    doc_type = "safety_alert" if "safety_alert" in str(pdf_path) else "investigation_report"

    # Get metadata from manifest or extract from content
    title = (manifest_entry or {}).get("title", pdf_path.stem.replace("_", " ").title())
    alert_number = (manifest_entry or {}).get("alert_number", "")
    date = _extract_date(full_text)

    return {
        "source_file": pdf_path.name,
        "doc_type": doc_type,
        "title": title,
        "alert_number": alert_number,
        "date": date or "",
        "pages": pages,
        "full_text": full_text,
    }


def chunk_document(doc: dict) -> list[dict]:
    """Split document into chunks with metadata."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=512,
        chunk_overlap=50,
        length_function=len,
    )

    chunks = []
    for page in doc["pages"]:
        page_chunks = splitter.split_text(page["text"])
        for chunk_text in page_chunks:
            chunks.append({
                "text": chunk_text,
                "metadata": {
                    "source_file": doc["source_file"],
                    "page_number": page["page_number"],
                    "doc_type": doc["doc_type"],
                    "title": doc["title"],
                    "alert_number": doc["alert_number"],
                    "date": doc["date"],
                },
            })

    return chunks


def ingest_all(force: bool = False):
    """Run the full ingestion pipeline."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collection = client.get_or_create_collection("bsee_documents")
    manifest_lookup = _build_manifest_lookup()

    stats = {"processed": 0, "skipped": 0, "chunks_created": 0, "errors": 0}

    # Gather all PDFs
    pdf_files: list[Path] = []
    for doc_type_dir in ("safety_alerts", "investigation_reports"):
        dir_path = PDF_BASE_PATH / doc_type_dir
        if dir_path.exists():
            pdf_files.extend(sorted(dir_path.glob("*.pdf")))

    if not pdf_files:
        print("No PDF files found in", PDF_BASE_PATH)
        return

    print(f"Found {len(pdf_files)} PDF files to process...")

    for pdf_path in pdf_files:
        # Idempotency check: skip if chunks already exist for this file
        if not force:
            existing = collection.get(
                where={"source_file": pdf_path.name},
                limit=1,
            )
            if existing and existing["ids"]:
                stats["skipped"] += 1
                continue

        # If force, delete existing chunks first
        if force:
            try:
                existing = collection.get(
                    where={"source_file": pdf_path.name},
                )
                if existing and existing["ids"]:
                    collection.delete(ids=existing["ids"])
            except Exception:
                pass  # Collection might not have this doc

        # Extract
        manifest_entry = manifest_lookup.get(pdf_path.name)
        doc = extract_pdf(pdf_path, manifest_entry)
        if doc is None:
            stats["errors"] += 1
            continue

        # Chunk
        chunks = chunk_document(doc)
        if not chunks:
            stats["errors"] += 1
            logger.warning("No chunks produced from %s", pdf_path.name)
            continue

        # Store in ChromaDB
        ids = [f"{pdf_path.name}_chunk_{i}" for i in range(len(chunks))]
        documents = [c["text"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        try:
            collection.add(ids=ids, documents=documents, metadatas=metadatas)
            stats["processed"] += 1
            stats["chunks_created"] += len(chunks)
            logger.info(
                "Ingested %s: %d chunks", pdf_path.name, len(chunks)
            )
        except Exception as e:
            stats["errors"] += 1
            logger.error("Failed to store chunks for %s: %s", pdf_path.name, e)

    print(f"\n=== Ingestion Summary ===")
    print(f"  Documents processed : {stats['processed']}")
    print(f"  Documents skipped   : {stats['skipped']}")
    print(f"  Total chunks created: {stats['chunks_created']}")
    print(f"  Errors              : {stats['errors']}")
    print(f"  Collection size     : {collection.count()} chunks")


if __name__ == "__main__":
    force = "--force" in sys.argv
    ingest_all(force=force)
