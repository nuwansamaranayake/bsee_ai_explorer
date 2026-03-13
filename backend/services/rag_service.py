"""RAG (Retrieval-Augmented Generation) service for BSEE document search.

Queries ChromaDB for semantically similar document chunks, then uses
ClaudeService to synthesize an answer with inline citations.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

import chromadb

from services.claude_service import get_claude_service
from services.prompts import RAG_SYSTEM, RAG_USER

logger = logging.getLogger(__name__)


class RAGService:
    """Semantic search over BSEE documents with AI-synthesized answers."""

    def __init__(self):
        chroma_path = os.getenv("CHROMA_PATH", "./data/chroma")
        self.client = chromadb.PersistentClient(path=chroma_path)
        self.collection = self.client.get_or_create_collection("bsee_documents")
        self.claude = get_claude_service()
        logger.info(
            "RAGService initialized. Collection size: %d chunks", self.collection.count()
        )

    async def search(
        self,
        query: str,
        top_k: int = 5,
        doc_type: str | None = None,
    ) -> dict:
        """Full RAG pipeline: query → retrieve → synthesize → cite."""
        # 1. Query ChromaDB (sync call — wrap in thread)
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
                "answer": "No relevant documents found for your query. Try rephrasing or broadening your search.",
                "citations": [],
                "query": query,
                "doc_count": self.collection.count(),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }

        # 2. Build context string
        context_parts = []
        for i, (doc, meta) in enumerate(zip(documents, metadatas)):
            title = meta.get("title", meta.get("source_file", "Unknown"))
            page = meta.get("page_number", "?")
            context_parts.append(
                f"[Document {i+1}] {title}, Page {page}:\n{doc}"
            )
        context = "\n\n---\n\n".join(context_parts)

        # 3. Call Claude for synthesis
        user_prompt = RAG_USER.format(query=query, context=context)
        answer = await self.claude.generate(
            system_prompt=RAG_SYSTEM,
            user_prompt=user_prompt,
            max_tokens=2048,
            temperature=0.3,
        )

        # 4. Build citation objects
        citations = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            # ChromaDB distances are L2 — convert to 0-1 relevance score
            # Lower distance = more relevant. Typical range 0.5-2.0.
            relevance = max(0.0, min(1.0, 1.0 - (dist / 2.0)))
            citations.append({
                "source_file": meta.get("source_file", ""),
                "title": meta.get("title", meta.get("source_file", "Unknown")),
                "page_number": meta.get("page_number", 0),
                "relevance_score": round(relevance, 3),
                "excerpt": doc[:300],
            })

        return {
            "answer": answer,
            "citations": citations,
            "query": query,
            "doc_count": self.collection.count(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    def get_stats(self) -> dict:
        """Corpus statistics for the frontend stats bar."""
        count = self.collection.count()

        # Get unique source files and doc types
        if count == 0:
            return {
                "total_documents": 0,
                "total_chunks": 0,
                "safety_alerts": 0,
                "investigation_reports": 0,
                "oldest_date": None,
                "newest_date": None,
            }

        # Sample metadata to count doc types
        all_meta = self.collection.get(
            include=["metadatas"],
            limit=count,
        )
        metadatas = all_meta.get("metadatas", [])

        source_files = set()
        sa_files = set()
        ir_files = set()
        dates = []

        for meta in metadatas:
            sf = meta.get("source_file", "")
            source_files.add(sf)
            if meta.get("doc_type") == "safety_alert":
                sa_files.add(sf)
            else:
                ir_files.add(sf)
            d = meta.get("date")
            if d:
                dates.append(d)

        return {
            "total_documents": len(source_files),
            "total_chunks": count,
            "safety_alerts": len(sa_files),
            "investigation_reports": len(ir_files),
            "oldest_date": min(dates) if dates else None,
            "newest_date": max(dates) if dates else None,
        }


# Singleton
_rag_service: RAGService | None = None


def get_rag_service() -> RAGService:
    """Get or create the singleton RAGService instance."""
    global _rag_service
    if _rag_service is None:
        _rag_service = RAGService()
    return _rag_service
