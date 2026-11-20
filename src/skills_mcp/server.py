import os
import time

import httpx
from fastmcp import FastMCP

from .diagnostics import Diagnostic

ENGINE_BASE_URL = os.getenv("SKILLS_ENGINE_URL", "http://127.0.0.1:8000")
BACKOFF_S = 0.2          # pause between the one retry of an idempotent read
MAX_INPUT_CHARS = 8000   # infer text beyond this is refused, never truncated
K_MAX = 50               # search result cap exposed to MCP clients


class EngineError(Diagnostic):
    """The engine rejected the request (4xx) — carries the engine's detail."""


class EngineUnavailable(EngineError):
    """The engine could not be reached (connect/timeout, or 5xx after retry)."""


mcp = FastMCP(
    "skills-engine",
    instructions=(
        "Three-tier skill taxonomy tools: infer skills from text (JDs, resumes, tasks), "
        "normalize raw skill labels against custom/external/master tiers, search the taxonomy, "
        "and inspect half-life-driven lifecycle governance."
    ),
)


def _detail(resp: httpx.Response) -> str:
    try:
        payload = resp.json()
        if isinstance(payload, dict) and payload.get("detail"):
            return str(payload["detail"])
    except ValueError:
        pass
    return resp.text[:200] or f"HTTP {resp.status_code}"


def _request(method: str, path: str, *, params: dict | None = None,
             payload: dict | None = None) -> dict | list:
    """One engine call with structured errors; idempotent reads retry once,
    writes never retry (an inference POST must not double-fire)."""
    attempts = 2 if method == "GET" else 1
    url = f"{ENGINE_BASE_URL}{path}"
    for attempt in range(attempts):
        try:
            if method == "GET":
                resp = httpx.get(url, params=params or {}, timeout=30.0)
            else:
                resp = httpx.post(url, json=payload or {}, timeout=60.0)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            if attempt + 1 < attempts:
                time.sleep(BACKOFF_S)
                continue
            msg = f"engine unreachable at {ENGINE_BASE_URL} ({type(exc).__name__})"
            raise EngineUnavailable("SKMCP_ENGINE_UNREACHABLE", msg) from exc
        if resp.status_code >= 500:
            if attempt + 1 < attempts:
                time.sleep(BACKOFF_S)
                continue
            msg = f"engine {method} {path} failed: HTTP {resp.status_code}"
            raise EngineUnavailable("SKMCP_ENGINE_5XX", msg)
        if resp.status_code >= 400:
            msg = f"engine {method} {path} rejected: {_detail(resp)}"
            raise EngineError("SKMCP_ENGINE_REJECTED", msg)
        return resp.json()
    raise AssertionError("unreachable")  # pragma: no cover


def _get(path: str, params: dict | None = None) -> dict | list:
    return _request("GET", path, params=params)


def _post(path: str, payload: dict) -> dict | list:
    return _request("POST", path, payload=payload)


def infer_skills(text: str, context_type: str = "job_description", locale: str = "en") -> dict:
    """Extract and resolve skills from text. Context types: job_description, job_definition,
    resume, task, reflection, user_signal, content. Returns resolved skills with tier,
    confidence and explanation."""
    if not text or not text.strip():
        raise Diagnostic("SKMCP_EMPTY_INPUT", "text must be non-empty")
    if len(text) > MAX_INPUT_CHARS:
        raise Diagnostic(
            "SKMCP_INPUT_TOO_LARGE",
            f"text too long ({len(text)} > {MAX_INPUT_CHARS} chars); "
            "chunk it upstream — truncation would silently lose skills")
    return _post("/v1/skills/infer", {"text": text, "context_type": context_type, "locale": locale})


def normalize_skill(name: str, locale: str = "en") -> dict:
    """Map a raw skill label onto the three-tier taxonomy (custom > external > master)."""
    if not name or not name.strip():
        raise Diagnostic("SKMCP_EMPTY_INPUT", "name must be non-empty")
    return _post("/v1/skills/normalize", {"name": name, "locale": locale})


def search_taxonomy(query: str, k: int = 5) -> list:
    """Semantic search across all taxonomy tiers (k clamped to 1..50)."""
    if not query or not query.strip():
        raise Diagnostic("SKMCP_EMPTY_INPUT", "query must be non-empty")
    k = max(1, min(int(k), K_MAX))
    return _get("/v1/skills/search", {"q": query, "k": k})


def taxonomy_stats() -> dict:
    """Skill counts by tier and lifecycle status."""
    return _get("/v1/taxonomy/stats")


def lifecycle_report(today: str | None = None) -> dict:
    """Proposed lifecycle actions with reasons and health metrics (half-life policy)."""
    params = {"today": today} if today else {}
    return _get("/v1/lifecycle/report", params)


def health() -> dict:
    """Probe the backing skills-engine; never raises — an exploding health
    check is useless to clients."""
    try:
        _get("/health")
        return {"ok": True, "engine_url": ENGINE_BASE_URL}
    except Exception as exc:  # health probes must never raise
        diag = (exc if isinstance(exc, Diagnostic)
                else Diagnostic("SKMCP_ENGINE_BAD_RESPONSE", str(exc) or type(exc).__name__))
        return {"ok": False, "engine_url": ENGINE_BASE_URL,
                "error": str(exc), "diagnostic": diag.to_dict()}


mcp.tool(infer_skills)
mcp.tool(normalize_skill)
mcp.tool(search_taxonomy)
mcp.tool(taxonomy_stats)
mcp.tool(lifecycle_report)
mcp.tool(health)


if __name__ == "__main__":
    mcp.run()
