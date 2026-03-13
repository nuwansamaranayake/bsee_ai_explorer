"""Input sanitization and prompt injection defense for all AI endpoints.

Provides:
- sanitize_user_input()  — regex-based injection detection, HTML stripping, length enforcement
- validate_generated_sql() — SELECT-only whitelist, forbidden keyword blocking
- sanitize_document_text() — strip HTML/script from PDF chunks before prompting

Security logging: all blocked attempts are logged to a dedicated 'security' logger.
"""

import html
import logging
import re

# Dedicated security logger — can be routed to a separate file / SIEM
security_logger = logging.getLogger("security")

# ---------------------------------------------------------------------------
# Injection pattern library (21 patterns)
# ---------------------------------------------------------------------------

INJECTION_PATTERNS: list[tuple[re.Pattern, str]] = [
    # Direct instruction override attempts
    (re.compile(r"ignore\s+(all\s+)?(previous|above|prior)\s+(instructions|rules|prompts)", re.I),
     "instruction_override"),
    (re.compile(r"disregard\s+(all\s+)?(previous|above|prior|your)\s+(instructions|rules|prompts)", re.I),
     "instruction_override"),
    (re.compile(r"forget\s+(all\s+)?(previous|above|prior|your)\s+(instructions|rules|context)", re.I),
     "instruction_override"),

    # Role hijacking
    (re.compile(r"you\s+are\s+now\s+(a|an|the)\s+", re.I), "role_hijack"),
    (re.compile(r"act\s+as\s+(a|an|the|if)\s+", re.I), "role_hijack"),
    (re.compile(r"pretend\s+(you\s+are|to\s+be)\s+", re.I), "role_hijack"),
    (re.compile(r"switch\s+to\s+.*mode", re.I), "role_hijack"),

    # System prompt extraction
    (re.compile(r"(show|reveal|print|output|display|repeat|tell)\s+(me\s+)?(your|the)\s+(system\s+)?(prompt|instructions|rules)", re.I),
     "prompt_extraction"),
    (re.compile(r"what\s+(are|is)\s+your\s+(system\s+)?(prompt|instructions|rules)", re.I),
     "prompt_extraction"),
    (re.compile(r"(show|reveal|tell)\s+me\s+.{0,30}(prompt|instructions|rules)\s+(you|that)", re.I),
     "prompt_extraction"),

    # Delimiter / context escape attempts
    (re.compile(r"</?system>", re.I), "delimiter_escape"),
    (re.compile(r"\[INST\]|\[/INST\]", re.I), "delimiter_escape"),
    (re.compile(r"<\|im_start\|>|<\|im_end\|>", re.I), "delimiter_escape"),
    (re.compile(r"###\s*(system|user|assistant)\s*:", re.I), "delimiter_escape"),
    (re.compile(r"</?user_query>", re.I), "delimiter_escape"),

    # SQL injection via prompt
    (re.compile(r";\s*(DROP|DELETE|INSERT|UPDATE|ALTER|CREATE|TRUNCATE)\s+", re.I),
     "sql_injection"),
    (re.compile(r"UNION\s+SELECT", re.I), "sql_injection"),
    (re.compile(r"--\s*$", re.MULTILINE), "sql_comment"),

    # Code execution attempts
    (re.compile(r"(exec|eval|import|__import__|subprocess|os\.system)\s*\(", re.I),
     "code_execution"),

    # Encoded / obfuscated payloads (detect \x69 hex sequences)
    (re.compile("\\\\x[0-9a-fA-F]{2}"), "hex_encoding"),
    (re.compile(r"&#x?[0-9a-fA-F]+;", re.I), "html_entity_encoding"),

    # Data exfiltration attempts
    (re.compile(r"(send|post|transmit|exfiltrate)\s+(to|data|this|the|all)\s+", re.I),
     "data_exfiltration"),
    (re.compile(r"(send|post|transmit|forward)\s+.{0,40}(to\s+https?://|to\s+\S+\.com)", re.I),
     "data_exfiltration"),
]

# ---------------------------------------------------------------------------
# SQL validation
# ---------------------------------------------------------------------------

FORBIDDEN_SQL_KEYWORDS: frozenset[str] = frozenset({
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE",
    "TRUNCATE", "REPLACE", "ATTACH", "DETACH", "PRAGMA",
    "GRANT", "REVOKE", "EXEC", "EXECUTE", "VACUUM",
})

FORBIDDEN_SQL_TARGETS: frozenset[str] = frozenset({
    "SQLITE_MASTER", "SQLITE_SCHEMA", "SQLITE_TEMP_MASTER",
    "SQLITE_TEMP_SCHEMA",
})

# ---------------------------------------------------------------------------
# HTML / script stripping pattern
# ---------------------------------------------------------------------------

_HTML_TAG_RE = re.compile(r"<[^>]+>")
_SCRIPT_RE = re.compile(r"<script[\s\S]*?</script>", re.I)
_STYLE_RE = re.compile(r"<style[\s\S]*?</style>", re.I)


# ===========================================================================
# Public API
# ===========================================================================


def sanitize_user_input(
    text: str,
    max_length: int = 500,
    endpoint: str = "unknown",
) -> str:
    """Sanitize and validate user input before it enters any AI prompt.

    1. Enforce maximum length
    2. Decode HTML entities
    3. Detect injection patterns — log and raise ValueError if found
    4. Strip HTML tags from safe content
    5. Return cleaned text

    Args:
        text: Raw user input string.
        max_length: Character limit (default 500).
        endpoint: Name of the calling endpoint (for security logging).

    Returns:
        Cleaned text safe for inclusion in prompts.

    Raises:
        ValueError: If a prompt injection pattern is detected.
    """
    if not text or not text.strip():
        raise ValueError("Input cannot be empty.")

    # 1. Length enforcement
    text = text[:max_length]

    # 2. Decode HTML entities FIRST (so &#105;gnore -> ignore before scanning)
    text = html.unescape(text)

    # 3. Injection pattern scan (run BEFORE stripping HTML so delimiter patterns
    #    like <system> and [INST] are detected before tag removal)
    for pattern, category in INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            security_logger.warning(
                "INJECTION_BLOCKED | endpoint=%s | category=%s | matched=%r | input_preview=%r",
                endpoint,
                category,
                match.group()[:80],
                text[:120],
            )
            raise ValueError(
                "Your message was flagged by our security filter. "
                "Please rephrase your question using plain language."
            )

    # 4. Strip HTML tags (after scanning — safe content only reaches here)
    text = _SCRIPT_RE.sub("", text)
    text = _STYLE_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)

    # 5. Normalize whitespace
    text = " ".join(text.split())

    return text.strip()


def validate_generated_sql(sql: str) -> str:
    """Validate SQL generated by Claude before execution.

    Ensures the query is a read-only SELECT/WITH, contains no forbidden
    keywords, no multi-statement payloads, and no system table access.

    Args:
        sql: SQL string generated by the AI.

    Returns:
        The validated SQL string.

    Raises:
        ValueError: If the SQL fails any safety check.
    """
    if not sql or not sql.strip():
        raise ValueError("Empty SQL query.")

    cleaned = sql.strip()
    upper = cleaned.upper()

    # 1. Must start with SELECT or WITH
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        security_logger.warning(
            "SQL_BLOCKED | reason=not_select | sql_preview=%r", cleaned[:200]
        )
        raise ValueError("Only SELECT queries are permitted.")

    # 2. No semicolons (multi-statement injection)
    if ";" in cleaned:
        security_logger.warning(
            "SQL_BLOCKED | reason=semicolon | sql_preview=%r", cleaned[:200]
        )
        raise ValueError("Multi-statement queries are not allowed.")

    # 3. No SQL comments (-- or /* */)
    if re.search(r"--|\\/\\*", cleaned):
        # More precise check for actual SQL comments
        if "--" in cleaned or "/*" in cleaned:
            security_logger.warning(
                "SQL_BLOCKED | reason=comments | sql_preview=%r", cleaned[:200]
            )
            raise ValueError("SQL comments are not allowed.")

    # 4. Forbidden keyword check (as standalone words)
    for keyword in FORBIDDEN_SQL_KEYWORDS:
        if re.search(rf"\b{keyword}\b", upper):
            security_logger.warning(
                "SQL_BLOCKED | reason=forbidden_keyword_%s | sql_preview=%r",
                keyword,
                cleaned[:200],
            )
            raise ValueError(f"Forbidden SQL keyword detected: {keyword}")

    # 5. System table access (sqlite_master, etc.)
    for target in FORBIDDEN_SQL_TARGETS:
        if target in upper:
            security_logger.warning(
                "SQL_BLOCKED | reason=system_table_%s | sql_preview=%r",
                target,
                cleaned[:200],
            )
            raise ValueError("Access to system tables is not allowed.")

    return cleaned


def sanitize_document_text(text: str, max_length: int = 8000) -> str:
    """Clean PDF-extracted text before injection into AI prompts.

    Strips HTML/script tags and truncates to max_length.
    Does NOT reject on injection patterns — PDF text may legitimately
    contain technical phrases that match patterns (e.g., "exec" in code docs).

    Args:
        text: Raw text extracted from a PDF document.
        max_length: Maximum character length.

    Returns:
        Cleaned text safe for prompt inclusion.
    """
    if not text:
        return ""

    # Strip any embedded HTML/script
    text = _SCRIPT_RE.sub("", text)
    text = _STYLE_RE.sub("", text)
    text = _HTML_TAG_RE.sub("", text)

    # Truncate
    text = text[:max_length]

    return text.strip()
