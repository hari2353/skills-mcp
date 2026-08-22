import os

from fastmcp import FastMCP

ENGINE_BASE_URL = os.getenv("SKILLS_ENGINE_URL", "http://127.0.0.1:8000")

mcp = FastMCP(
    "skills-engine",
    instructions=(
        "Three-tier skill taxonomy tools: infer skills from text (JDs, resumes, tasks), "
        "normalize raw skill labels against custom/external/master tiers, search the taxonomy, "
        "and inspect half-life-driven lifecycle governance."
    ),
)


def _get(path: str, params: dict | None = None) -> dict:
    import httpx

    resp = httpx.get(f"{ENGINE_BASE_URL}{path}", params=params or {}, timeout=30.0)
    resp.raise_for_status()
    return resp.json()


def _post(path: str, payload: dict) -> dict:
    import httpx

    resp = httpx.post(f"{ENGINE_BASE_URL}{path}", json=payload, timeout=60.0)
    resp.raise_for_status()
    return resp.json()


def infer_skills(text: str, context_type: str = "job_description", locale: str = "en") -> dict:
    """Extract and resolve skills from text. Context types: job_description, job_definition,
    resume, task, reflection, user_signal, content. Returns resolved skills with tier,
    confidence and explanation."""
    return _post("/v1/skills/infer", {"text": text, "context_type": context_type, "locale": locale})


def normalize_skill(name: str, locale: str = "en") -> dict:
    """Map a raw skill label onto the three-tier taxonomy (custom > external > master)."""
    return _post("/v1/skills/normalize", {"name": name, "locale": locale})


def search_taxonomy(query: str, k: int = 5) -> list:
    """Semantic search across all taxonomy tiers."""
    return _get("/v1/skills/search", {"q": query, "k": k})


def taxonomy_stats() -> dict:
    """Skill counts by tier and lifecycle status."""
    return _get("/v1/taxonomy/stats")


def lifecycle_report(today: str | None = None) -> dict:
    """Proposed lifecycle actions with reasons and health metrics (half-life policy)."""
    params = {"today": today} if today else {}
    return _get("/v1/lifecycle/report", params)


mcp.tool(infer_skills)
mcp.tool(normalize_skill)
mcp.tool(search_taxonomy)
mcp.tool(taxonomy_stats)
mcp.tool(lifecycle_report)


if __name__ == "__main__":
    mcp.run()
