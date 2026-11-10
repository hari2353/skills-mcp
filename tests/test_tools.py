import asyncio

import pytest

import skills_mcp.server as server

pytest.importorskip("fastmcp", reason="fastmcp not installed")


@pytest.fixture()
def fake_transport(monkeypatch):
    calls = []

    def fake_get(path, params=None):
        calls.append(("GET", path, params))
        if path == "/v1/taxonomy/stats":
            return {"total_skills": 34}
        if path == "/v1/skills/search":
            return [{"skill_id": "esco__009"}]
        if path == "/v1/lifecycle/report":
            return {"actions": []}
        raise AssertionError(path)

    def fake_post(path, payload):
        calls.append(("POST", path, payload))
        if path == "/v1/skills/infer":
            return {"skills": [{"skill_id": "esco__007"}]}
        if path == "/v1/skills/normalize":
            return {"skill_id": "cus__3003", "tier": "custom"}
        raise AssertionError(path)

    monkeypatch.setattr(server, "_get", fake_get)
    monkeypatch.setattr(server, "_post", fake_post)
    return calls


def test_infer_tool_posts_context(fake_transport):
    out = server.infer_skills("hiring python devs", context_type="resume")
    assert out["skills"][0]["skill_id"] == "esco__007"
    method, path, payload = fake_transport[-1]
    assert (method, path) == ("POST", "/v1/skills/infer")
    assert payload["context_type"] == "resume"


def test_normalize_and_search_tools(fake_transport):
    assert server.normalize_skill("k8s")["tier"] == "custom"
    assert server.search_taxonomy("kafka")[0]["skill_id"] == "esco__009"
    assert any(m == "GET" for m, _, _ in fake_transport)


def test_lifecycle_tool_passes_optional_date(monkeypatch):
    seen = {}

    def fake_get(path, params=None):
        seen["params"] = params
        return {"actions": []}

    monkeypatch.setattr(server, "_get", fake_get)
    server.lifecycle_report(today="2026-08-23")
    assert seen["params"] == {"today": "2026-08-23"}


def test_all_tools_registered_on_mcp_server():
    try:
        tool_names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    except AttributeError:
        # older fastmcp internal layout fallback; if neither works, fail loudly
        tm = getattr(server.mcp, "_tool_manager", None)
        if tm is None:
            pytest.fail("no way to enumerate registered tools on fastmcp")
        tool_names = {t.name for t in tm._tools.values()}
    assert {"infer_skills", "normalize_skill", "search_taxonomy", "taxonomy_stats", "lifecycle_report"} <= tool_names
