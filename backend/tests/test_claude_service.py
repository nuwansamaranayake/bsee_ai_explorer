"""Tests for ClaudeService — mock-based tests that run without an API key."""

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# Ensure no real API key is used during tests
os.environ["OPENROUTER_API_KEY"] = ""
os.environ["ANTHROPIC_API_KEY"] = ""

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from services.claude_service import (
    ClaudeService,
    ClaudeServiceError,
    TokenTracker,
    _classify_error,
)
from openai import RateLimitError, APIConnectionError, APIError


# ---------------------------------------------------------------------------
# TokenTracker
# ---------------------------------------------------------------------------

class TestTokenTracker:
    def test_initial_state(self):
        tracker = TokenTracker()
        assert tracker.total_input_tokens == 0
        assert tracker.total_output_tokens == 0
        assert tracker.total_requests == 0

    def test_record_success(self):
        tracker = TokenTracker()
        tracker.record(100, 200, success=True)
        assert tracker.total_input_tokens == 100
        assert tracker.total_output_tokens == 200
        assert tracker.total_requests == 1
        assert tracker.failed_requests == 0

    def test_record_failure(self):
        tracker = TokenTracker()
        tracker.record(50, 0, success=False)
        assert tracker.failed_requests == 1
        assert tracker.total_requests == 1

    def test_summary(self):
        tracker = TokenTracker()
        tracker.record(100, 200)
        tracker.record(50, 100)
        summary = tracker.summary
        assert summary["total_tokens"] == 450
        assert summary["total_requests"] == 2


# ---------------------------------------------------------------------------
# Error Classification
# ---------------------------------------------------------------------------

class TestErrorClassification:
    def test_rate_limit_error(self):
        # openai.RateLimitError requires response/body args
        err = MagicMock(spec=RateLimitError)
        err.__class__ = RateLimitError
        # Use isinstance check via duck typing
        real_err = RateLimitError.__new__(RateLimitError)
        err_type, msg = _classify_error(real_err)
        assert err_type == "rate_limit"

    def test_connection_error(self):
        real_err = APIConnectionError.__new__(APIConnectionError)
        err_type, msg = _classify_error(real_err)
        assert err_type == "connection"

    def test_unknown_error(self):
        err = ValueError("something unexpected")
        err_type, msg = _classify_error(err)
        assert err_type == "unknown"


# ---------------------------------------------------------------------------
# ClaudeService Initialization
# ---------------------------------------------------------------------------

class TestClaudeServiceInit:
    def test_unavailable_without_key(self):
        """ClaudeService should be unavailable without a valid API key."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "ANTHROPIC_API_KEY": ""}):
            import services.claude_service as cs
            cs._claude_service = None
            service = ClaudeService()
            assert not service.is_available

    def test_unavailable_with_placeholder_key(self):
        """Placeholder key should also be treated as unavailable."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "ANTHROPIC_API_KEY": "sk-ant-your-key-here"}):
            service = ClaudeService()
            assert not service.is_available

    def test_available_with_openrouter_key(self):
        """An OpenRouter key should make the service available."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-real-key", "ANTHROPIC_API_KEY": ""}):
            service = ClaudeService()
            assert service.is_available
            assert service._provider == "openrouter"

    def test_available_with_anthropic_fallback(self):
        """Anthropic key should work as fallback when no OpenRouter key."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "ANTHROPIC_API_KEY": "sk-ant-api03-real-key"}):
            service = ClaudeService()
            assert service.is_available
            assert service._provider == "anthropic"

    def test_openrouter_preferred_over_anthropic(self):
        """OpenRouter should be preferred when both keys are present."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-real-key", "ANTHROPIC_API_KEY": "sk-ant-api03-real-key"}):
            service = ClaudeService()
            assert service.is_available
            assert service._provider == "openrouter"

    def test_ensure_available_raises(self):
        """_ensure_available should raise when service is not available."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "ANTHROPIC_API_KEY": ""}):
            service = ClaudeService()
            with pytest.raises(ClaudeServiceError) as exc_info:
                service._ensure_available()
            assert exc_info.value.error_type == "auth"


# ---------------------------------------------------------------------------
# Generate Method (Mocked)
# ---------------------------------------------------------------------------

class TestGenerate:
    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Test successful generation with mocked OpenAI client."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-test-key", "ANTHROPIC_API_KEY": ""}):
            service = ClaudeService()

            # Mock the client — OpenAI response format
            mock_message = MagicMock()
            mock_message.content = "Hello, world!"
            mock_choice = MagicMock()
            mock_choice.message = mock_message

            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=5)

            service._client = AsyncMock()
            service._client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await service.generate("system", "user")
            assert result == "Hello, world!"

    @pytest.mark.asyncio
    async def test_generate_raises_on_unavailable(self):
        """Test that generate raises when service is unavailable."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "", "ANTHROPIC_API_KEY": ""}):
            service = ClaudeService()
            with pytest.raises(ClaudeServiceError):
                await service.generate("system", "user")


# ---------------------------------------------------------------------------
# Generate JSON (Mocked)
# ---------------------------------------------------------------------------

class TestGenerateJSON:
    @pytest.mark.asyncio
    async def test_json_parse_success(self):
        """Test successful JSON parsing."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-test-key", "ANTHROPIC_API_KEY": ""}):
            service = ClaudeService()

            json_response = '{"key": "value", "count": 42}'
            mock_message = MagicMock()
            mock_message.content = json_response
            mock_choice = MagicMock()
            mock_choice.message = mock_message
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)

            service._client = AsyncMock()
            service._client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await service.generate_json("system", "user")
            assert result == {"key": "value", "count": 42}

    @pytest.mark.asyncio
    async def test_json_strips_markdown_fences(self):
        """Test JSON parsing with markdown code fences."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-test-key", "ANTHROPIC_API_KEY": ""}):
            service = ClaudeService()

            json_response = '```json\n{"key": "value"}\n```'
            mock_message = MagicMock()
            mock_message.content = json_response
            mock_choice = MagicMock()
            mock_choice.message = mock_message
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)

            service._client = AsyncMock()
            service._client.chat.completions.create = AsyncMock(return_value=mock_response)

            result = await service.generate_json("system", "user")
            assert result == {"key": "value"}

    @pytest.mark.asyncio
    async def test_json_retry_on_malformed(self):
        """Test JSON retry when first response is malformed."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-test-key", "ANTHROPIC_API_KEY": ""}):
            service = ClaudeService()

            # First call returns malformed JSON, second returns valid
            bad_message = MagicMock()
            bad_message.content = '{key: broken}'
            bad_choice = MagicMock()
            bad_choice.message = bad_message
            bad_response = MagicMock()
            bad_response.choices = [bad_choice]
            bad_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)

            good_message = MagicMock()
            good_message.content = '{"key": "fixed"}'
            good_choice = MagicMock()
            good_choice.message = good_message
            good_response = MagicMock()
            good_response.choices = [good_choice]
            good_response.usage = MagicMock(prompt_tokens=10, completion_tokens=20)

            service._client = AsyncMock()
            service._client.chat.completions.create = AsyncMock(
                side_effect=[bad_response, good_response]
            )

            result = await service.generate_json("system", "user")
            assert result == {"key": "fixed"}
            assert service._client.chat.completions.create.call_count == 2


# ---------------------------------------------------------------------------
# SQL Service Safety
# ---------------------------------------------------------------------------

class TestSQLSafety:
    """Test SQL validation without needing an API key or database."""

    def test_select_is_safe(self):
        from services.sql_service import SQLService
        assert SQLService._is_safe_query("SELECT * FROM incidents") is True

    def test_with_cte_is_safe(self):
        from services.sql_service import SQLService
        assert SQLService._is_safe_query(
            "WITH cte AS (SELECT * FROM incidents) SELECT * FROM cte"
        ) is True

    def test_delete_is_rejected(self):
        from services.sql_service import SQLService
        assert SQLService._is_safe_query("DELETE FROM incidents") is False

    def test_drop_is_rejected(self):
        from services.sql_service import SQLService
        assert SQLService._is_safe_query("DROP TABLE incidents") is False

    def test_insert_is_rejected(self):
        from services.sql_service import SQLService
        assert SQLService._is_safe_query("INSERT INTO incidents VALUES (1)") is False

    def test_update_is_rejected(self):
        from services.sql_service import SQLService
        assert SQLService._is_safe_query("UPDATE incidents SET x=1") is False

    def test_select_with_subquery_delete_rejected(self):
        from services.sql_service import SQLService
        assert SQLService._is_safe_query(
            "SELECT * FROM incidents; DELETE FROM incidents"
        ) is False
