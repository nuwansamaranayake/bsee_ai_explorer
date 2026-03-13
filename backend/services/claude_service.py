"""ClaudeService — shared LLM service for all AI features.

Uses OpenRouter (OpenAI-compatible API) as the primary backend,
with optional fallback to direct Anthropic API.

Provides single-turn generation, streaming generation, and JSON generation
with retry logic, structured error handling, and token tracking.
"""

import json
import logging
import os
import time
from typing import AsyncGenerator

from openai import AsyncOpenAI, RateLimitError, APIConnectionError, APIError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)


class ClaudeServiceError(Exception):
    """Structured error for AI API failures."""

    def __init__(self, error_type: str, message: str, original: Exception | None = None):
        self.error_type = error_type  # rate_limit, auth, context_length, unknown
        self.message = message
        self.original = original
        super().__init__(f"[{error_type}] {message}")


class TokenTracker:
    """In-memory token usage tracker for cost monitoring."""

    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_requests = 0
        self.failed_requests = 0

    def record(self, input_tokens: int, output_tokens: int, success: bool = True):
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.total_requests += 1
        if not success:
            self.failed_requests += 1

    @property
    def summary(self) -> dict:
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_requests": self.total_requests,
            "failed_requests": self.failed_requests,
        }


# Global token tracker (shared across requests within a process)
token_tracker = TokenTracker()


def _classify_error(e: Exception) -> tuple[str, str]:
    """Classify an API error into a structured type."""
    if isinstance(e, RateLimitError):
        return "rate_limit", "Rate limit exceeded. Please try again shortly."
    if isinstance(e, APIConnectionError):
        return "connection", "Unable to connect to AI service."
    if isinstance(e, APIError):
        msg = str(e)
        if "authentication" in msg.lower() or "api key" in msg.lower():
            return "auth", "Invalid or missing API key."
        if "context" in msg.lower() or "token" in msg.lower():
            return "context_length", "Input too long for the model's context window."
        return "unknown", f"AI service error: {msg}"
    return "unknown", f"Unexpected error: {str(e)}"


class ClaudeService:
    """Service for interacting with Claude via OpenRouter (OpenAI-compatible).

    Provides three generation methods:
    - generate(): Single-turn text generation
    - generate_stream(): Streaming text generation (yields chunks for SSE)
    - generate_json(): Generation with automatic JSON parsing
    """

    def __init__(self):
        # Prefer OpenRouter, fall back to Anthropic
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")

        if openrouter_key and not openrouter_key.startswith("sk-or-v1-your"):
            self._available = True
            self._client = AsyncOpenAI(
                api_key=openrouter_key,
                base_url=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            )
            self.model = os.getenv("OPENROUTER_MODEL", "anthropic/claude-sonnet-4")
            self._provider = "openrouter"
            logger.info("AI service initialized via OpenRouter (model=%s)", self.model)
        elif anthropic_key and not anthropic_key.startswith("sk-ant-your-key"):
            self._available = True
            self._client = AsyncOpenAI(
                api_key=anthropic_key,
                base_url="https://api.anthropic.com/v1",
            )
            self.model = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250514")
            self._provider = "anthropic"
            logger.info("AI service initialized via direct Anthropic (model=%s)", self.model)
        else:
            self._available = False
            self._client = None
            self._provider = None
            logger.warning("No AI API key configured — AI features disabled")

        self.default_max_tokens = 4096
        self.default_temperature = 0.3

    @property
    def is_available(self) -> bool:
        return self._available

    def _ensure_available(self):
        if not self._available:
            raise ClaudeServiceError(
                "auth",
                "AI features unavailable — no API key configured"
            )

    def _extra_headers(self) -> dict:
        """OpenRouter-recommended headers for app identification."""
        if self._provider == "openrouter":
            return {
                "HTTP-Referer": "https://gomsafety.aigniteconsulting.ai",
                "X-Title": "Beacon GoM",
            }
        return {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        reraise=True,
    )
    async def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> str:
        """Single-turn generation. Returns text response."""
        self._ensure_available()
        start_time = time.time()

        try:
            response = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                extra_headers=self._extra_headers(),
            )

            latency_ms = int((time.time() - start_time) * 1000)
            input_tokens = response.usage.prompt_tokens if response.usage else 0
            output_tokens = response.usage.completion_tokens if response.usage else 0
            token_tracker.record(input_tokens, output_tokens)

            logger.info(
                "AI API call | provider=%s | model=%s | input_tokens=%d | output_tokens=%d | latency_ms=%d | status=success",
                self._provider, self.model, input_tokens, output_tokens, latency_ms,
            )

            return response.choices[0].message.content

        except (RateLimitError, APIConnectionError):
            # Let tenacity retry handle these
            raise
        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            token_tracker.record(0, 0, success=False)
            error_type, error_msg = _classify_error(e)
            logger.error(
                "AI API call | provider=%s | model=%s | latency_ms=%d | status=failed | error=%s",
                self._provider, self.model, latency_ms, error_msg,
            )
            raise ClaudeServiceError(error_type, error_msg, original=e) from e

    async def generate_stream(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
        temperature: float = 0.3,
    ) -> AsyncGenerator[str, None]:
        """Streaming generation. Yields text chunks for SSE.

        Each yielded chunk is formatted as: data: {chunk}\\n\\n
        """
        self._ensure_available()
        start_time = time.time()
        total_chunks = 0

        try:
            stream = await self._client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=True,
                extra_headers=self._extra_headers(),
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    total_chunks += 1
                    yield f"data: {json.dumps({'type': 'chunk', 'content': chunk.choices[0].delta.content})}\n\n"

            latency_ms = int((time.time() - start_time) * 1000)
            # OpenRouter streaming doesn't always return usage; estimate
            token_tracker.record(0, total_chunks, success=True)
            logger.info(
                "AI API stream | provider=%s | model=%s | chunks=%d | latency_ms=%d | status=success",
                self._provider, self.model, total_chunks, latency_ms,
            )

        except Exception as e:
            token_tracker.record(0, 0, success=False)
            error_type, error_msg = _classify_error(e)
            logger.error("AI API stream | status=failed | error=%s", error_msg)
            yield f"data: {json.dumps({'type': 'error', 'content': error_msg})}\n\n"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=4),
        retry=retry_if_exception_type((RateLimitError, APIConnectionError)),
        reraise=True,
    )
    async def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        max_tokens: int = 4096,
    ) -> dict:
        """Generation with JSON parsing. Returns parsed dict.

        Appends a JSON-only instruction to the system prompt, then parses
        the response. On malformed JSON, retries once with a correction prompt.
        """
        self._ensure_available()

        json_system = (
            system_prompt
            + "\n\nIMPORTANT: Respond ONLY with valid JSON. "
            "No markdown, no code fences, no explanation — just the JSON object."
        )

        text = await self.generate(json_system, user_prompt, max_tokens, temperature=0.1)

        # Strip potential markdown fences
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as first_error:
            logger.warning(
                "JSON parse failed on first attempt: %s. Retrying with correction prompt.",
                str(first_error)[:100],
            )

            # Retry with correction prompt
            correction_prompt = (
                f"The following text was supposed to be valid JSON but has a syntax error:\n\n"
                f"{cleaned[:2000]}\n\n"
                f"Error: {str(first_error)}\n\n"
                f"Please fix it and return ONLY the corrected valid JSON."
            )
            retry_text = await self.generate(json_system, correction_prompt, max_tokens, temperature=0.0)

            retry_cleaned = retry_text.strip()
            if retry_cleaned.startswith("```"):
                lines = retry_cleaned.split("\n")
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                retry_cleaned = "\n".join(lines)

            try:
                return json.loads(retry_cleaned)
            except json.JSONDecodeError as second_error:
                raise ClaudeServiceError(
                    "unknown",
                    f"Failed to parse JSON after retry: {str(second_error)[:200]}",
                ) from second_error


# Singleton instance
_claude_service: ClaudeService | None = None


def get_claude_service() -> ClaudeService:
    """Get or create the singleton ClaudeService instance."""
    global _claude_service
    if _claude_service is None:
        _claude_service = ClaudeService()
    return _claude_service
