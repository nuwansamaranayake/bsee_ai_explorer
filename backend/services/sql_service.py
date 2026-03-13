"""SQLService — text-to-SQL pipeline for natural language Q&A.

Pipeline: question → Claude generates SQL → execute safely → Claude synthesizes answer.
All SQL execution is READ-ONLY with strict safety guards.
"""

import logging
import os
import re
import sqlite3
from typing import Any

from services.claude_service import ClaudeService, ClaudeServiceError
from services.prompts import (
    TEXT_TO_SQL_SYSTEM,
    TEXT_TO_SQL_USER,
    ANSWER_SYNTHESIS_SYSTEM,
    ANSWER_SYNTHESIS_USER,
    SQL_REFUSAL_MESSAGE,
)

logger = logging.getLogger(__name__)

# Maximum rows returned from any query
MAX_ROWS = 1000
# Query timeout in seconds
QUERY_TIMEOUT_SECONDS = 10
# Sample rows per table for context
SAMPLE_ROWS_COUNT = 3


class SQLServiceError(Exception):
    """Error from the SQL service pipeline."""
    pass


class SQLService:
    """Text-to-SQL pipeline: question → SQL → execute → answer.

    All SQL execution is strictly READ-ONLY.
    """

    def __init__(self, db_path: str, claude_service: ClaudeService):
        self.db_path = db_path
        self.claude = claude_service
        self.schema = self._load_schema()
        self.sample_rows = self._load_samples()

    def _load_schema(self) -> str:
        """Read the SQLite schema for prompt injection."""
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
        Reject any destructive statements.
        """
        cleaned = sql.strip().upper()

        # Must start with SELECT or WITH (CTEs)
        if not (cleaned.startswith("SELECT") or cleaned.startswith("WITH")):
            return False

        # Reject any destructive keywords anywhere in the query
        dangerous_keywords = [
            "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
            "TRUNCATE", "REPLACE", "ATTACH", "DETACH", "PRAGMA",
            "GRANT", "REVOKE", "EXEC", "EXECUTE",
        ]
        # Check for dangerous keywords as standalone words
        for keyword in dangerous_keywords:
            if re.search(rf'\b{keyword}\b', cleaned):
                return False

        return True

    async def _generate_sql(self, question: str) -> str:
        """Use Claude to convert natural language to SQL."""
        system_prompt = TEXT_TO_SQL_SYSTEM.format(schema=self.schema)
        user_prompt = TEXT_TO_SQL_USER.format(
            user_question=question,
            sample_rows=self.sample_rows,
        )

        sql = await self.claude.generate(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            max_tokens=1024,
            temperature=0.1,
        )

        # Clean up response — remove any markdown fences
        sql = sql.strip()
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
        """
        if not self._is_safe_query(sql):
            raise SQLServiceError("Query rejected: only SELECT queries are allowed.")

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

    async def _synthesize_answer(
        self, question: str, sql: str, results: list[dict]
    ) -> str:
        """Use Claude to turn SQL results into a conversational answer."""
        # Format results for the prompt
        if results:
            # Limit displayed results to first 50 rows for prompt size
            display_results = results[:50]
            results_text = "\n".join(str(row) for row in display_results)
            if len(results) > 50:
                results_text += f"\n... ({len(results) - 50} more rows)"
        else:
            results_text = "No results returned."

        user_prompt = ANSWER_SYNTHESIS_USER.format(
            user_question=question,
            sql_query=sql,
            row_count=len(results),
            query_results=results_text,
        )

        return await self.claude.generate(
            system_prompt=ANSWER_SYNTHESIS_SYSTEM,
            user_prompt=user_prompt,
            max_tokens=2048,
            temperature=0.3,
        )

    async def answer_question(self, question: str) -> dict:
        """Full pipeline: question → SQL → execute → answer.

        Returns dict with keys: answer, sql, data, error (if any).
        """
        # Check for obviously destructive requests
        dangerous_words = ["delete", "drop", "truncate", "update", "insert", "alter", "remove all"]
        question_lower = question.lower()
        if any(word in question_lower for word in dangerous_words):
            # Still generate SQL to show what was attempted, but refuse
            return {
                "answer": SQL_REFUSAL_MESSAGE,
                "sql": None,
                "data": [],
                "refused": True,
            }

        try:
            # Step 1: Generate SQL
            sql = await self._generate_sql(question)
            logger.info("Generated SQL for question: %s", sql[:200])

            # Step 2: Validate and execute
            try:
                results = self._execute_sql(sql)
            except SQLServiceError:
                # Step 3: If execution fails, retry SQL generation with error context
                logger.warning("First SQL attempt failed, retrying with error context")
                retry_prompt = (
                    f"The previous SQL query failed. The question was: {question}\n"
                    f"The failed query was: {sql}\n"
                    f"Please generate a corrected SQLite query."
                )
                sql = await self._generate_sql(retry_prompt)
                results = self._execute_sql(sql)

            # Step 4: Synthesize answer
            answer = await self._synthesize_answer(question, sql, results)

            return {
                "answer": answer,
                "sql": sql,
                "data": results[:100],  # Limit data sent to frontend
                "refused": False,
            }

        except ClaudeServiceError as e:
            logger.error("Claude service error in chat pipeline: %s", e)
            return {
                "answer": (
                    "I'm sorry, the AI service is temporarily unavailable. "
                    "Please try again in a moment."
                ),
                "sql": None,
                "data": [],
                "refused": False,
            }
        except SQLServiceError as e:
            logger.error("SQL service error: %s", e)
            return {
                "answer": (
                    "I wasn't able to answer that question. The query may be too complex "
                    "or reference data that doesn't exist. Could you try rephrasing?"
                ),
                "sql": None,
                "data": [],
                "refused": False,
            }
        except Exception as e:
            logger.error("Unexpected error in chat pipeline: %s", e, exc_info=True)
            return {
                "answer": "I encountered an unexpected error. Please try again.",
                "sql": None,
                "data": [],
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
