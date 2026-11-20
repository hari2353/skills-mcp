"""MCP progress notifications for the one long tool (inference).

The client sees `notifications/progress` only when it sent a progress token.
Without a token the report is a no-op, so the tool must still work when no
MCP context exists (unit calls, direct use).
"""

import asyncio

from skills_mcp import server


class FakeCtx:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def report_progress(self, progress, total=None, message=None) -> None:
        self.calls.append((progress, total, message))


def test_infer_reports_start_engine_and_finish(monkeypatch):
    monkeypatch.setattr(server, "_post", lambda path, payload: {"skills": ["Python"]})
    ctx = FakeCtx()
    monkeypatch.setattr(server, "get_context", lambda: ctx)

    out = asyncio.run(server.infer_skills_tool("python dev"))

    assert out == {"skills": ["Python"]}
    assert [c[0] for c in ctx.calls] == [0, 1, 2]
    assert all(c[1] == 2 for c in ctx.calls)
    assert "engine" in ctx.calls[1][2].lower()


def test_infer_works_without_an_mcp_context(monkeypatch):
    monkeypatch.setattr(server, "_post", lambda path, payload: {"skills": []})

    def no_context():
        raise RuntimeError("No active context found.")

    monkeypatch.setattr(server, "get_context", no_context)

    assert asyncio.run(server.infer_skills_tool("x")) == {"skills": []}


def test_progress_wrapper_keeps_the_public_tool_set():
    names = {t.name for t in asyncio.run(server.mcp.list_tools())}
    assert names == {
        "infer_skills", "normalize_skill", "search_taxonomy",
        "taxonomy_stats", "lifecycle_report", "health",
    }


def test_real_mcp_client_receives_progress(monkeypatch):
    from fastmcp import Client

    monkeypatch.setattr(server, "_post", lambda path, payload: {"skills": []})
    seen = []

    async def run():
        async with Client(server.mcp) as client:
            async def handler(progress, total, message):
                seen.append((progress, total, message))

            await client.call_tool("infer_skills", {"text": "python"},
                                   progress_handler=handler)

    asyncio.run(run())
    assert [p for p, _, _ in seen] == [0, 1, 2]
