from skills_mcp.footprint import tool_call_footprint


def test_empty():
    out = tool_call_footprint([])
    assert out["total_calls"] == 0
    assert out["distinct_tools"] == 0
    assert out["errors"] == 0


def test_counts_and_errors():
    calls = [
        {"name": "echo", "arguments": {"value": 7}, "error": False},
        {"name": "echo", "arguments": {"value": 8}},
        {"name": "explode", "arguments": {}, "error": True},
    ]
    out = tool_call_footprint(calls)
    assert out["total_calls"] == 3
    assert out["distinct_tools"] == 2
    assert out["calls_by_tool"] == {"echo": 2, "explode": 1}
    assert out["errors"] == 1
    assert out["argument_bytes"] > 0


def test_rejects_non_list():
    try:
        tool_call_footprint("nope")
    except TypeError:
        pass
    else:
        raise AssertionError("non-list accepted")
