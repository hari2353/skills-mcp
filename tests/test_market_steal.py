"""Market-steal additions (2026-11-18): structured engine errors with bounded
retries, tool-boundary validation, health tool.

Compared products treat these as baseline: MCP servers return actionable,
structured tool errors (never raw transport tracebacks); read calls retry
transient failures while writes do not; and the server exposes a health
probe the client can call.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fastmcp", reason="fastmcp not installed")

import httpx  # noqa: E402

import skills_mcp.server as server  # noqa: E402


class FakeResp:
    def __init__(self, status_code: int = 200, payload=None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = text

    def json(self):
        return self._payload


@pytest.fixture()
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(server.time, "sleep", lambda s: slept.append(s))
    return slept


# ── structured errors + retries ─────────────────────────────────────────────
class TestEngineErrors:
    def test_connect_failure_is_structured_and_retried_once(self, monkeypatch, no_sleep) -> None:
        calls = []

        def boom(*a, **kw):
            calls.append(1)
            raise httpx.ConnectError("connection refused")

        monkeypatch.setattr(server.httpx, "get", boom)
        with pytest.raises(server.EngineUnavailable, match="127.0.0.1:8000"):
            server.taxonomy_stats()
        assert len(calls) == 2  # idempotent GET retried once
        assert no_sleep == [server.BACKOFF_S]

    def test_engine_4xx_carries_detail_without_retry(self, monkeypatch, no_sleep) -> None:
        calls = []

        def not_found(*a, **kw):
            calls.append(1)
            return FakeResp(404, {"detail": "unknown skill id"})

        monkeypatch.setattr(server.httpx, "get", not_found)
        with pytest.raises(server.EngineError, match="unknown skill id") as exc:
            server.taxonomy_stats()
        assert not isinstance(exc.value, server.EngineUnavailable)
        assert len(calls) == 1

    def test_5xx_retried_then_unavailable(self, monkeypatch, no_sleep) -> None:
        calls = []

        def broken(*a, **kw):
            calls.append(1)
            return FakeResp(502, {}, text="bad gateway")

        monkeypatch.setattr(server.httpx, "get", broken)
        with pytest.raises(server.EngineUnavailable, match="502"):
            server.taxonomy_stats()
        assert len(calls) == 2

    def test_transient_failure_recovers(self, monkeypatch, no_sleep) -> None:
        calls = []

        def flaky(*a, **kw):
            calls.append(1)
            if len(calls) == 1:
                raise httpx.ConnectTimeout("slow")
            return FakeResp(200, {"total_skills": 34})

        monkeypatch.setattr(server.httpx, "get", flaky)
        assert server.taxonomy_stats() == {"total_skills": 34}
        assert len(calls) == 2

    def test_post_never_retried(self, monkeypatch, no_sleep) -> None:
        calls = []

        def boom(*a, **kw):
            calls.append(1)
            raise httpx.ConnectError("down")

        monkeypatch.setattr(server.httpx, "post", boom)
        with pytest.raises(server.EngineUnavailable):
            server.infer_skills("python and sql")
        assert len(calls) == 1  # never double-fire an inference POST


# ── tool-boundary validation ────────────────────────────────────────────────
class TestToolValidation:
    def test_search_k_is_clamped(self, monkeypatch) -> None:
        seen = {}

        def fake_get(url, params=None, **kw):
            seen["k"] = params["k"]
            return FakeResp(200, [{"skill_id": "esco__009"}])

        monkeypatch.setattr(server.httpx, "get", fake_get)
        server.search_taxonomy("kafka", k=100_000)
        assert seen["k"] == 50
        server.search_taxonomy("kafka", k=-5)
        assert seen["k"] == 1

    def test_empty_inputs_rejected_before_transport(self, monkeypatch) -> None:
        def no_call(*a, **kw):
            raise AssertionError("transport must not be called for invalid input")

        monkeypatch.setattr(server.httpx, "get", no_call)
        monkeypatch.setattr(server.httpx, "post", no_call)
        with pytest.raises(ValueError, match="query"):
            server.search_taxonomy("   ")
        with pytest.raises(ValueError, match="text"):
            server.infer_skills("  ")
        with pytest.raises(ValueError, match="name"):
            server.normalize_skill("")

    def test_oversize_text_refused_not_truncated(self, monkeypatch) -> None:
        def no_call(*a, **kw):
            raise AssertionError("transport must not be called for invalid input")

        monkeypatch.setattr(server.httpx, "post", no_call)
        with pytest.raises(ValueError, match="too long"):
            server.infer_skills("x" * (server.MAX_INPUT_CHARS + 1))


# ── health tool ─────────────────────────────────────────────────────────────
class TestHealthTool:
    def test_health_ok(self, monkeypatch) -> None:
        monkeypatch.setattr(server.httpx, "get", lambda *a, **kw: FakeResp(200, {"status": "ok"}))
        result = server.health()
        assert result["ok"] is True and result["engine_url"] == server.ENGINE_BASE_URL

    def test_health_down_never_raises(self, monkeypatch, no_sleep) -> None:
        def boom(*a, **kw):
            raise httpx.ConnectError("refused")

        monkeypatch.setattr(server.httpx, "get", boom)
        result = server.health()
        assert result["ok"] is False and "unreachable" in result["error"]

    def test_health_covers_invalid_json(self, monkeypatch) -> None:
        class BadJson(FakeResp):
            def json(self):
                raise ValueError("not json")

        monkeypatch.setattr(server.httpx, "get", lambda *a, **kw: BadJson(200))
        result = server.health()
        assert result["ok"] is False and "not json" in result["error"]

    def test_health_registered(self) -> None:
        tool_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
        assert "health" in tool_names
