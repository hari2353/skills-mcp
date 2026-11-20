"""Agent repair contract: every expected failure carries a stable code,
a plain-language fix, and a docs pointer — never a raw transport traceback.
"""

from pathlib import Path

import httpx
import pytest

pytest.importorskip("fastmcp", reason="fastmcp not installed")

import skills_mcp.server as server  # noqa: E402
from skills_mcp.diagnostics import CATALOG  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


class FakeResp:
    def __init__(self, status_code: int = 200, payload=None) -> None:
        self.status_code = status_code
        self._payload = payload if payload is not None else {}
        self.text = ""

    def json(self):
        return self._payload


@pytest.fixture()
def no_sleep(monkeypatch):
    monkeypatch.setattr(server.time, "sleep", lambda s: None)


def test_validation_error_has_code_hint_and_docs() -> None:
    with pytest.raises(server.Diagnostic) as exc:
        server.search_taxonomy("   ")
    diag = exc.value
    assert diag.code == "SKMCP_EMPTY_INPUT"
    assert diag.hint
    assert diag.docs.startswith("docs/diagnostics.md#")
    rendered = str(diag)
    assert rendered.startswith("[SKMCP_EMPTY_INPUT]")
    assert "fix:" in rendered and "docs:" in rendered


def test_oversize_input_has_its_own_code() -> None:
    with pytest.raises(server.Diagnostic) as exc:
        server.infer_skills("x" * (server.MAX_INPUT_CHARS + 1))
    assert exc.value.code == "SKMCP_INPUT_TOO_LARGE"


def test_engine_unreachable_has_code(monkeypatch, no_sleep) -> None:
    def boom(*a, **kw):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(server.httpx, "get", boom)
    with pytest.raises(server.EngineUnavailable) as exc:
        server.taxonomy_stats()
    assert exc.value.code == "SKMCP_ENGINE_UNREACHABLE"


def test_engine_rejection_has_code(monkeypatch) -> None:
    monkeypatch.setattr(server.httpx, "get",
                        lambda *a, **kw: FakeResp(404, {"detail": "unknown skill"}))
    with pytest.raises(server.EngineError) as exc:
        server.taxonomy_stats()
    assert exc.value.code == "SKMCP_ENGINE_REJECTED"


def test_health_down_reports_the_same_diagnostic(monkeypatch, no_sleep) -> None:
    def boom(*a, **kw):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(server.httpx, "get", boom)
    out = server.health()
    assert out["ok"] is False
    assert out["diagnostic"]["code"] == "SKMCP_ENGINE_UNREACHABLE"
    assert out["diagnostic"]["hint"]
    assert out["diagnostic"]["docs"]


def test_catalog_is_documented() -> None:
    docs = (ROOT / "docs" / "diagnostics.md").read_text(encoding="utf-8")
    missing = [code for code in CATALOG if code not in docs]
    assert not missing, f"undocumented diagnostic codes: {missing}"
