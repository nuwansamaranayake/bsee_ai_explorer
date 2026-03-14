"""SQLService — intelligent multi-query chat engine for natural language Q&A.

Three-phase pipeline: PLAN → EXECUTE → ANALYZE.
Phase 1: Claude creates a query plan (simple, analytical, or comparative).
Phase 2: Generate and execute SQL for each query in the plan.
Phase 3: Claude analyzes the combined results to produce an insightful answer.

All SQL execution is READ-ONLY with strict safety guards.
"""

import logging
import os
import re
import sqlite3
from typing import Any, Callable

from services.claude_service import ClaudeService, ClaudeServiceError
from services.input_sanitizer import validate_generated_sql, sanitize_user_input
from services.prompts import (
    QUERY_PLANNER_SYSTEM,
    QUERY_PLANNER_USER,
    SQL_GENERATOR_SYSTEM,
    SQL_GENERATOR_USER,
    ANALYSIS_SYSTEM,
    ANALYSIS_USER,
    FALLBACK_SQL_SYSTEM,
    FALLBACK_SQL_USER,
    SQL_REFUSAL_MESSAGE,
)

logger = logging.getLogger(__name__)

# Maximum rows returned from any single query
MAX_ROWS = 500
# Query timeout in seconds
QUERY_TIMEOUT_SECONDS = 10
# Sample rows per table for context
SAMPLE_ROWS_COUNT = 3
# Maximum queries in a plan
MAX_PLAN_QUERIES = 3


class SQLServiceError(Exception):
    """Error from the SQL service pipeline."""
    pass


class SQLService:
    """Intelligent multi-query chat engine: PLAN → EXECUTE → ANALYZE.

    All SQL execution is strictly READ-ONLY.
    """

    def __init__(self, db_path: str, claude_service: ClaudeService):
        self.db_path = db_path
        self.claude = claude_service
        self.schema = self._load_schema()
        self.sample_rows = self._load_samples()

    def _load_schema(self) -> str:
        """Read the SQLite schema for prompt context."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL"
            )
            schemas = [row[0] for row in cursor.fetchall()]
            conn.close()
            return "\n\n".join(schemas)
        except Exception as e:
            logger.error("Failed to load DB schema: %s", e)
            return "Schema unavailable"

    # Whitelist of allowed table names — prevents any injection via table names.
    ALLOWED_TABLES = frozenset({"incidents", "incs", "platforms", "production"})

    def _load_samples(self) -> str:
        """Load sample rows from each table for Claude context."""
        samples = []

        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            for table in self.ALLOWED_TABLES:
                try:
                    # Table names cannot be parameterized in SQL, so we
                    # validate against the ALLOWED_TABLES whitelist above.
                    cursor.execute(
                        f"SELECT * FROM [{table}] LIMIT ?", (SAMPLE_ROWS_COUNT,)
                    )
                    rows = cursor.fetchall()
                    if rows:
                        cols = rows[0].keys()
                        sample_text = f"Table: {table}\nColumns: {', '.join(cols)}\n"
                        for row in rows:
                            vals = [
                                str(row[c])[:50] if row[c] is not None else "NULL"
                                for c in cols
                            ]
                            sample_text += f"  {dict(zip(cols, vals))}\n"
                        samples.append(sample_text)
                except Exception as e:
                    logger.warning("Failed to sample table %s: %s", table, e)

            conn.close()
        except Exception as e:
            logger.error("Failed to load sample rows: %s", e)

        return "\n".join(samples) if samples else "No sample data available"

    @staticmethod
    def _is_safe_query(sql: str) -> bool:
        """Validate that the SQL is a read-only SELECT or WITH statement.

        Whitelist approach: only allow queries starting with SELECT or WITH.
        Reject any destructive statements and system table access.
        """
        cleaned = sql.strip().upper()

        # Must start with SELECT or WITH (CTEs)
        if not (cleaned.startswith("SELECT") or cleaned.startswith("WITH")):
            return False

        # Reject any destructive keywords anywhere in the query
        dangerous_keywords = [
            "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
            "TRUNCATE", "REPLACE", "ATTACH", "DETACH", "PRAGMA",
            "GRANT", "REVOKE", "EXEC", "EXECUTE", "VACUUM",
        ]
        # Check for dangerous keywords as standalone words
        for keyword in dangerous_keywords:
            if re.search(rf'\b{keyword}\b', cleaned):
                return False

        # Reject system table access (schema enumeration)
        system_tables = [
            "SQLITE_MASTER", "SQLITE_SCHEMA",
            "SQLITE_TEMP_MASTER", "SQLITE_TEMP_SCHEMA",
        ]
        for table in system_tables:
            if table in cleaned:
                return False

        # Reject multi-statement queries (semicolons)
        if ";" in sql.strip():
            return False

        return True

    @staticmethod
    def _clean_sql_response(text: str) -> str:
        """Strip markdown fences and whitespace from a SQL response."""
        sql = text.strip()
        if sql.startswith("```"):
            lines = sql.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            sql = "\n".join(lines).strip()
        return sql

    def _execute_sql(self, sql: str) -> list[dict]:
        """Execute SQL safely against SQLite (READ-ONLY).

        Uses a read-only connection with timeout and row limit.
        Double-validated: _is_safe_query (legacy) + validate_generated_sql (new).
        """
        if not self._is_safe_query(sql):
            raise SQLServiceError("Query rejected: only SELECT queries are allowed.")

        # Additional validation from input_sanitizer
        try:
            validate_generated_sql(sql)
        except ValueError as e:
            raise SQLServiceError(f"Query rejected: {e}") from e

        try:
            # Open in read-only mode using URI
            uri = f"file:{self.db_path}?mode=ro"
            conn = sqlite3.connect(uri, uri=True, timeout=QUERY_TIMEOUT_SECONDS)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Execute with a statement timeout
            cursor.execute(sql)
            rows = cursor.fetchmany(MAX_ROWS)

            results = []
            for row in rows:
                results.append(dict(row))

            conn.close()
            return results

        except sqlite3.OperationalError as e:
            error_msg = str(e)
            logger.error("SQL execution error: %s | Query: %s", error_msg, sql[:200])
            raise SQLServiceError(
                f"Query execution failed. The question may be too complex or reference non-existent data."
            ) from e
        except Exception as e:
            logger.error("Unexpected SQL error: %s", e)
            raise SQLServiceError("An unexpected error occurred while querying the database.") from e

    # ------------------------------------------------------------------
    # Phase 1: PLAN — Claude decides how to answer the question
    # ------------------------------------------------------------------

    async def _create_query_plan(self, question: str) -> dict:
        """Phase 1: Ask Claude to create a structured query plan."""
        system_prompt = QUERY_PLANNER_SYSTEM.format(schema=self.schema)
        user_prompt = QUERY_PLANNER_USER.format(question=question)

        try:
            plan = await self.claude.generate_json(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=1024,
            )
        except ClaudeServiceError:
            logger.warning("Query planning failed, falling back to simple mode")
            return self._default_plan(question)

        # Validate plan structure
        if not isinstance(plan, dict):
            return self._default_plan(question)

        queries = plan.get("queries", [])
        if not queries or not isinstance(queries, list) or len(queries) > MAX_PLAN_QUERIES:
            return self._default_plan(question)

        # Validate each query has required fields
        valid_queries = []
        for q in queries:
            if isinstance(q, dict) and q.get("purpose") and q.get("description"):
                valid_queries.append(q)

        if not valid_queries:
            return self._default_plan(question)

        complexity = plan.get("complexity", "simple")
        if complexity not in ("simple", "analytical", "comparative"):
            complexity = "analytical" if len(valid_queries) > 1 else "simple"

        return {
            "complexity": complexity,
            "queries": valid_queries,
            "analysis_needed": plan.get("analysis_needed", "Provide a direct answer"),
        }

    @staticmethod
    def _default_plan(question: str) -> dict:
        """Fallback plan: single query, simple complexity."""
        return {
            "complexity": "simple",
            "queries": [{"purpose": "Answer the question directly", "description": question}],
            "analysis_needed": "Provide a direct answer based on the data.",
        }

    # ------------------------------------------------------------------
    # Phase 2: EXECUTE — Generate and run SQL for each query in the plan
    # ------------------------------------------------------------------

    async def _generate_planned_sql(
        self,
        question: str,
        query_spec: dict,
        query_number: int = 1,
        total_queries: int = 1,
    ) -> str:
        """Phase 2: Generate SQL for one query in the plan."""
        system_prompt = SQL_GENERATOR_SYSTEM.format(
            schema=self.schema,
            query_purpose=query_spec["purpose"],
            query_description=query_spec["description"],
            original_question=question,
            query_number=query_number,
            total_queries=total_queries,
        )
        user_prompt = SQL_GENERATOR_USER.format(
            query_purpose=query_spec["purpose"],
            query_description=query_spec["description"],
            sample_rows=self.sample_rows,
        )

        text = await self.claude.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1024,
            temperature=0.1,
        )
        return self._clean_sql_response(text)

    async def _generate_fallback_sql(self, question: str, original_sql: str) -> str:
        """Generate a simpler, broader SQL query when the first query returns no rows."""
        system_prompt = FALLBACK_SQL_SYSTEM.format(schema=self.schema)
        user_prompt = FALLBACK_SQL_USER.format(
            user_question=question,
            original_sql=original_sql,
        )

        text = await self.claude.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1024,
            temperature=0.1,
        )
        return self._clean_sql_response(text)

    # ------------------------------------------------------------------
    # Phase 3: ANALYZE — Claude reasons over the combined results
    # ------------------------------------------------------------------

    async def _analyze_results(
        self, question: str, all_results: list[dict], plan: dict
    ) -> str:
        """Phase 3: Claude analyzes combined results from all queries."""
        formatted = self._format_results_for_analysis(all_results)

        if not formatted.strip() or formatted == "No data retrieved.":
            return (
                "I couldn't find enough data to answer that question. "
                "Try asking about a specific operator or time period."
            )

        system_prompt = ANALYSIS_SYSTEM.format(original_question=question)
        user_prompt = ANALYSIS_USER.format(
            original_question=question,
            formatted_results=formatted,
        )

        return await self.claude.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=2048,
            temperature=0.3,
        )

    @staticmethod
    def _format_results_for_analysis(all_results: list[dict]) -> str:
        """Format query results into a readable text block for Claude."""
        parts = []
        for result_set in all_results:
            purpose = result_set.get("purpose", "Query")
            sql = result_set.get("sql", "")
            data = result_set.get("data", [])

            if not data:
                parts.append(f"[{purpose}]: No results returned.")
                continue

            parts.append(f"[{purpose}] ({len(data)} rows):")

            if data and isinstance(data[0], dict):
                headers = list(data[0].keys())
                parts.append(" | ".join(headers))
                parts.append("-" * 60)

                # Show data rows (limit to 100 for prompt size)
                for row in data[:100]:
                    parts.append(" | ".join(str(row.get(h, "")) for h in headers))

                if len(data) > 100:
                    parts.append(f"... and {len(data) - 100} more rows")

            parts.append("")

        return "\n".join(parts) if parts else "No data retrieved."

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def answer_question(
        self,
        question: str,
        on_progress: Callable[[str, dict], None] | None = None,
    ) -> dict:
        """Three-phase intelligent query engine: PLAN → EXECUTE → ANALYZE.

        Args:
            question: Natural language question from the user.
            on_progress: Optional callback for phase progress updates.
                Called with (phase_name, details_dict).

        Returns dict with keys: answer, queries, data, complexity, refused.
        """
        # Sanitize user input (injection detection + length enforcement)
        try:
            question = sanitize_user_input(question, max_length=500, endpoint="chat")
        except ValueError as e:
            return {
                "answer": str(e),
                "queries": [],
                "data": [],
                "complexity": "simple",
                "refused": True,
            }

        # Check for obviously destructive requests
        dangerous_words = ["delete", "drop", "truncate", "update", "insert", "alter", "remove all"]
        question_lower = question.lower()
        if any(word in question_lower for word in dangerous_words):
            return {
                "answer": SQL_REFUSAL_MESSAGE,
                "queries": [],
                "data": [],
                "complexity": "simple",
                "refused": True,
            }

        def _emit(phase: str, details: dict):
            if on_progress:
                on_progress(phase, details)

        try:
            # ── PHASE 1: PLAN ────────────────────────────────────
            _emit("planning", {"message": "Planning analysis approach..."})
            plan = await self._create_query_plan(question)
            complexity = plan["complexity"]
            logger.info(
                "Query plan: complexity=%s, queries=%d",
                complexity, len(plan["queries"]),
            )
            _emit("planned", {
                "complexity": complexity,
                "query_count": len(plan["queries"]),
                "message": (
                    f"Running {'multi-query ' if len(plan['queries']) > 1 else ''}"
                    f"{complexity} analysis..."
                ),
            })

            # ── PHASE 2: EXECUTE ─────────────────────────────────
            all_results: list[dict] = []
            all_queries: list[str] = []
            total = len(plan["queries"])

            for i, query_spec in enumerate(plan["queries"]):
                _emit("executing", {
                    "query_number": i + 1,
                    "total_queries": total,
                    "purpose": query_spec["purpose"],
                    "message": f"Running query {i + 1} of {total}: {query_spec['purpose']}",
                })

                try:
                    sql = await self._generate_planned_sql(
                        question, query_spec,
                        query_number=i + 1,
                        total_queries=total,
                    )
                    logger.info("Generated SQL [%d/%d]: %s", i + 1, total, sql[:200])

                    # Execute with retry
                    try:
                        results = self._execute_sql(sql)
                    except SQLServiceError as exec_err:
                        logger.warning(
                            "SQL execution failed for query %d, retrying: %s",
                            i + 1, exec_err,
                        )
                        retry_desc = (
                            f"The previous query failed with: {exec_err}. "
                            f"Please generate a corrected query for: {query_spec['description']}"
                        )
                        retry_spec = {
                            "purpose": query_spec["purpose"],
                            "description": retry_desc,
                        }
                        sql = await self._generate_planned_sql(
                            question, retry_spec,
                            query_number=i + 1,
                            total_queries=total,
                        )
                        results = self._execute_sql(sql)

                    # Fallback for empty results on the first (or only) query
                    if not results and i == 0:
                        logger.info("Query %d returned 0 rows, attempting fallback", i + 1)
                        try:
                            fallback_sql = await self._generate_fallback_sql(question, sql)
                            fallback_results = self._execute_sql(fallback_sql)
                            if fallback_results:
                                sql = fallback_sql
                                results = fallback_results
                                logger.info("Fallback query returned %d rows", len(results))
                        except (SQLServiceError, ClaudeServiceError) as fb_err:
                            logger.warning("Fallback query failed: %s", fb_err)

                    all_queries.append(sql)
                    all_results.append({
                        "purpose": query_spec["purpose"],
                        "sql": sql,
                        "data": results,
                    })

                except (SQLServiceError, ClaudeServiceError) as query_err:
                    logger.error("Query %d failed completely: %s", i + 1, query_err)
                    # Skip failed queries — analyze with whatever data we have
                    continue

            # If ALL queries failed, return error
            if not all_results or all(not r.get("data") for r in all_results):
                # If we have queries but no data, let the analysis handle it
                if all_results:
                    pass  # Let Phase 3 explain the empty results
                else:
                    return {
                        "answer": (
                            "I wasn't able to retrieve data for that question. "
                            "Could you try rephrasing?"
                        ),
                        "queries": all_queries,
                        "data": [],
                        "complexity": complexity,
                        "refused": False,
                    }

            # ── PHASE 3: ANALYZE ─────────────────────────────────
            _emit("analyzing", {
                "message": "Analyzing results...",
                "rows_total": sum(len(r.get("data", [])) for r in all_results),
            })

            answer = await self._analyze_results(question, all_results, plan)

            # Flatten data for frontend (combine all query results)
            combined_data = []
            for r in all_results:
                combined_data.extend(r.get("data", [])[:50])

            return {
                "answer": answer,
                "queries": all_queries,
                "data": combined_data[:100],
                "complexity": complexity,
                "refused": False,
            }

        except ClaudeServiceError as e:
            logger.error("Claude service error in chat pipeline: %s", e)
            return {
                "answer": (
                    "I'm sorry, the AI service is temporarily unavailable. "
                    "Please try again in a moment."
                ),
                "queries": [],
                "data": [],
                "complexity": "simple",
                "refused": False,
            }
        except SQLServiceError as e:
            logger.error("SQL service error: %s", e)
            return {
                "answer": (
                    "I wasn't able to answer that question. The query may be too complex "
                    "or reference data that doesn't exist. Could you try rephrasing?"
                ),
                "queries": [],
                "data": [],
                "complexity": "simple",
                "refused": False,
            }
        except Exception as e:
            logger.error("Unexpected error in chat pipeline: %s", e, exc_info=True)
            return {
                "answer": "I encountered an unexpected error. Please try again.",
                "queries": [],
                "data": [],
                "complexity": "simple",
                "refused": False,
            }


# Singleton instance
_sql_service: SQLService | None = None


def get_sql_service() -> SQLService:
    """Get or create the singleton SQLService instance."""
    global _sql_service
    if _sql_service is None:
        from services.claude_service import get_claude_service
        db_path = os.getenv("DATABASE_PATH", "./data/bsee.db")
        _sql_service = SQLService(db_path, get_claude_service())
    return _sql_service
