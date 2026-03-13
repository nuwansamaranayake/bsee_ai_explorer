"""Integration tests for Beacon GoM API endpoints.

Tests run against the actual seeded database (no mocks).
Validates all data endpoints, filter behavior, and error handling.
AI endpoints (analyze, chat) are tested for structure but skip AI calls.
"""

import os
import sys

import pytest

# Ensure backend root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set test environment
os.environ.setdefault("DATABASE_PATH", os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "bsee.db"
))
os.environ.setdefault("ANTHROPIC_API_KEY", "")

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _get_first_operator_name() -> str:
    """Retrieve the first operator name from the operators endpoint."""
    ops = client.get("/api/operators").json()["data"]
    return ops[0]["operator_name"]


# ---------------------------------------------------------------------------
# Health Check
# ---------------------------------------------------------------------------

class TestHealth:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["version"] == "0.2.0"
        assert "ai_available" in data

    def test_health_has_token_usage(self):
        resp = client.get("/health")
        data = resp.json()
        assert "ai_tokens_used" in data
        assert "total_tokens" in data["ai_tokens_used"]


# ---------------------------------------------------------------------------
# Operators
# ---------------------------------------------------------------------------

class TestOperators:
    def test_list_operators(self):
        resp = client.get("/api/operators")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0
        first = data["data"][0]
        assert "operator_name" in first
        assert "incident_count" in first
        assert "inc_count" in first

    def test_operator_ranking(self):
        resp = client.get("/api/operators/ranking")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

class TestIncidents:
    def test_list_incidents_unfiltered(self):
        resp = client.get("/api/incidents")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0
        assert "meta" in data

    def test_filter_by_operator(self):
        op_name = _get_first_operator_name()
        resp = client.get("/api/incidents", params={"operator": op_name})
        assert resp.status_code == 200
        data = resp.json()
        for inc in data["data"]:
            assert inc["operator_name"] == op_name

    def test_filter_by_year_range(self):
        resp = client.get("/api/incidents", params={"year_start": 2020, "year_end": 2022})
        assert resp.status_code == 200
        data = resp.json()
        for inc in data["data"]:
            assert 2020 <= inc["year"] <= 2022

    def test_pagination(self):
        page1 = client.get("/api/incidents", params={"limit": 5, "offset": 0}).json()
        page2 = client.get("/api/incidents", params={"limit": 5, "offset": 5}).json()
        assert len(page1["data"]) == 5
        if len(page2["data"]) > 0:
            assert page1["data"][0]["incident_id"] != page2["data"][0]["incident_id"]


# ---------------------------------------------------------------------------
# INCs (Violations)
# ---------------------------------------------------------------------------

class TestINCs:
    def test_list_incs(self):
        resp = client.get("/api/incs")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0

    def test_inc_summary(self):
        resp = client.get("/api/incs/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data

    def test_filter_by_severity(self):
        resp = client.get("/api/incs", params={"severity": "Warning"})
        assert resp.status_code == 200
        data = resp.json()
        for inc in data["data"]:
            assert inc["severity"] == "Warning"


# ---------------------------------------------------------------------------
# Platforms
# ---------------------------------------------------------------------------

class TestPlatforms:
    def test_list_platforms(self):
        resp = client.get("/api/platforms")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0

    def test_filter_platforms_by_operator(self):
        op_name = _get_first_operator_name()
        resp = client.get("/api/platforms", params={"operator": op_name})
        assert resp.status_code == 200
        data = resp.json()
        for plat in data["data"]:
            assert plat["operator_name"] == op_name


# ---------------------------------------------------------------------------
# Production
# ---------------------------------------------------------------------------

class TestProduction:
    def test_list_production(self):
        resp = client.get("/api/production")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0

    def test_production_fields(self):
        """Production data should include expected fields."""
        resp = client.get("/api/production")
        data = resp.json()
        first = data["data"][0]
        assert "year" in first or "YEAR" in first


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class TestMetrics:
    def test_metrics_summary(self):
        resp = client.get("/api/metrics/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        summary = data["data"]
        assert "total_incidents" in summary
        assert "total_incs" in summary
        assert "incidents_per_million_boe" in summary
        # Each KPI has value, yoy_change, direction
        ti = summary["total_incidents"]
        assert "value" in ti
        assert "yoy_change" in ti
        assert "direction" in ti

    def test_metrics_summary_by_operator(self):
        op_name = _get_first_operator_name()
        resp = client.get("/api/metrics/summary", params={"operator": op_name})
        assert resp.status_code == 200
        data = resp.json()
        assert data["data"]["total_incidents"]["value"] >= 0

    def test_normalized_metrics(self):
        resp = client.get("/api/metrics/normalized")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert len(data["data"]) > 0
        first = data["data"][0]
        assert "year" in first
        assert "incidents_per_million_boe" in first
        assert "operator_name" in first
        # Meta should include gom_averages
        assert "gom_averages" in data["meta"]

    def test_normalized_by_operator(self):
        op_name = _get_first_operator_name()
        resp = client.get("/api/metrics/normalized", params={"operator": op_name})
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        for entry in data["data"]:
            assert entry["operator_name"] == op_name


# ---------------------------------------------------------------------------
# Analyze — AI endpoints (structure only, no real AI calls)
# ---------------------------------------------------------------------------

class TestAnalyze:
    def test_trends_requires_ai(self):
        """Without API key, trends endpoint should return 503."""
        resp = client.post("/api/analyze/trends", json={})
        assert resp.status_code == 503

    def test_categorize_requires_ai(self):
        """Without API key, categorize endpoint should return 503."""
        resp = client.post("/api/analyze/categorize", json={})
        assert resp.status_code == 503

    def test_root_causes_endpoint(self):
        """Root causes GET endpoint should work even without AI."""
        resp = client.get("/api/analyze/root-causes")
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert isinstance(data["data"], list)


# ---------------------------------------------------------------------------
# Chat — SSE endpoint (structure only)
# ---------------------------------------------------------------------------

class TestChat:
    def test_chat_requires_ai(self):
        """Without API key, chat should handle gracefully."""
        resp = client.post("/api/chat", json={"message": "test question"})
        assert resp.status_code in [200, 503]

    def test_chat_missing_message(self):
        """Chat with empty body should fail validation."""
        resp = client.post("/api/chat", json={})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Cross-Operator Consistency
# ---------------------------------------------------------------------------

class TestCrossOperator:
    """Test that data is consistent across multiple operators."""

    def test_five_operator_stress(self):
        """Verify data loads for 5 different operators."""
        ops = client.get("/api/operators").json()["data"]
        assert len(ops) >= 5, "Need at least 5 operators for stress test"

        for op in ops[:5]:
            op_name = op["operator_name"]

            incidents_resp = client.get("/api/incidents", params={"operator": op_name, "limit": 10})
            assert incidents_resp.status_code == 200, f"Incidents failed for {op_name}"

            incs_resp = client.get("/api/incs", params={"operator": op_name, "limit": 10})
            assert incs_resp.status_code == 200, f"INCs failed for {op_name}"

            metrics_resp = client.get("/api/metrics/summary", params={"operator": op_name})
            assert metrics_resp.status_code == 200, f"Metrics failed for {op_name}"

            norm_resp = client.get("/api/metrics/normalized", params={"operator": op_name})
            assert norm_resp.status_code == 200, f"Normalized failed for {op_name}"

    def test_gom_wide_vs_operator(self):
        """GoM-wide metrics should be >= any single operator."""
        gom = client.get("/api/metrics/summary").json()["data"]
        op_name = _get_first_operator_name()
        op_metrics = client.get("/api/metrics/summary", params={"operator": op_name}).json()["data"]

        assert gom["total_incidents"]["value"] >= op_metrics["total_incidents"]["value"]
        assert gom["total_incs"]["value"] >= op_metrics["total_incs"]["value"]


# ---------------------------------------------------------------------------
# Response Format Consistency
# ---------------------------------------------------------------------------

class TestResponseFormat:
    """All API responses should follow the { data: T, meta?: {} } envelope."""

    def test_operators_envelope(self):
        data = client.get("/api/operators").json()
        assert "data" in data

    def test_incidents_envelope(self):
        data = client.get("/api/incidents").json()
        assert "data" in data
        assert "meta" in data

    def test_incs_envelope(self):
        data = client.get("/api/incs").json()
        assert "data" in data

    def test_platforms_envelope(self):
        data = client.get("/api/platforms").json()
        assert "data" in data

    def test_production_envelope(self):
        data = client.get("/api/production").json()
        assert "data" in data

    def test_metrics_summary_envelope(self):
        data = client.get("/api/metrics/summary").json()
        assert "data" in data

    def test_normalized_envelope(self):
        data = client.get("/api/metrics/normalized").json()
        assert "data" in data
        assert "meta" in data
