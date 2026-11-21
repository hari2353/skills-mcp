"""Operational footprint for the MCP tool surface."""

from __future__ import annotations


def tool_call_footprint(calls: list[dict]) -> dict:
    """Summarize a list of recorded tool calls: counts per tool, bytes, errors."""
    if not isinstance(calls, list):
        raise TypeError("calls must be a list")
    by_tool: dict[str, int] = {}
    total_bytes = 0
    errors = 0
    for call in calls:
        name = str(call.get("name", "unknown"))
        by_tool[name] = by_tool.get(name, 0) + 1
        payload = call.get("arguments", {})
        total_bytes += len(str(payload).encode("utf-8"))
        if call.get("error"):
            errors += 1
    return {
        "total_calls": len(calls),
        "distinct_tools": len(by_tool),
        "calls_by_tool": dict(sorted(by_tool.items())),
        "argument_bytes": total_bytes,
        "errors": errors,
    }
