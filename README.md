# Skills MCP Server

[![ci](https://github.com/hari2353/skills-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/hari2353/skills-mcp/actions/workflows/ci.yml)

A [FastMCP](https://github.com/jlowin/fastmcp) server that exposes the
[skills-engine](https://github.com/hari2353/skills-engine) taxonomy as **MCP tools** — so any MCP client
(Claude, Cursor, custom agents) can infer, normalize, and search skills, and inspect lifecycle governance.

## Tools

| Tool | Purpose |
|---|---|
| `infer_skills(text, context_type)` | extract + resolve skills from JDs, resumes, tasks, reflections |
| `normalize_skill(name)` | map a raw label to custom → external → master tiers |
| `search_taxonomy(query, k)` | semantic search across all tiers |
| `taxonomy_stats()` | counts by tier + lifecycle status |
| `lifecycle_report(today?)` | proposed actions with reasons (half-life policy) |
| `health()` | engine connectivity probe — never raises |

## Run

```bash
pip install -r requirements.txt
uvicorn skills_engine.api.app:app --reload   # in the skills-engine repo, port 8000

export SKILLS_ENGINE_URL=http://127.0.0.1:8000
python src/skills_mcp/server.py              # stdio MCP transport
```

Wire it into any MCP client config:

```json
{
  "mcpServers": {
    "skills-engine": {
      "command": "python",
      "args": ["src/skills_mcp/server.py"]
    }
  }
}
```

## Raw JSON-RPC path

FastMCP stays the default transport. `skills_mcp.raw_protocol` is a stdlib-only
JSON-RPC 2.0 dispatcher (`initialize`, `tools/list`, `tools/call`) with the
same tool surface, per-tool scopes and minimal schema validation — useful for
proving protocol behavior without the SDK:

```python
server = RawMCPServer([RawTool("echo", "...", schema, "skills:read", handler)])
server.handle(request, granted_scopes={"skills:read"})
```

## Tests

Tool functions are plain callables registered onto the FastMCP instance, so tests monkeypatch the transport
layer (`_get`/`_post`) and assert routing, payloads, and registration without a live engine.

### Client hygiene (market-steal, 2026-11-18)

- **Structured errors** — `EngineError` carries the engine's `detail` (4xx);
  `EngineUnavailable` names the base URL (connect/timeout, or 5xx after
  retry). Clients never see raw httpx tracebacks.
- **Bounded retries** — idempotent GETs retry once after `BACKOFF_S`; POST
  inference/normalize calls never retry (no double extraction).
- **Tool-boundary validation** — empty inputs rejected before transport;
  infer text capped at 8000 chars (refused, not truncated); `search_taxonomy`
  k clamped to 1..50.
- **`health()`** — returns `{ok, engine_url[, error]}` and never raises.
- **Progress notifications** — `infer_skills` reports 0/1/2 with plain-language
  messages when the client sends a progress token; without a token it adds no
  work (and still runs when there is no MCP context at all).
- **Agent repair contract** — every expected failure carries a stable code, a
  one-line fix, and a docs pointer (`[SKMCP_INPUT_TOO_LARGE] ... (fix: ...)
  (docs: docs/diagnostics.md#...)`). Catalog: `docs/diagnostics.md`.

MIT
