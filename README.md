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

## Tests

Tool functions are plain callables registered onto the FastMCP instance, so tests monkeypatch the transport
layer (`_get`/`_post`) and assert routing, payloads, and registration without a live engine.

MIT
