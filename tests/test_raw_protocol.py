import pytest

from skills_mcp.raw_protocol import RawMCPServer, RawTool


def echo(args):
    return {"echo": args["value"]}


def explode(args):
    raise RuntimeError("boom")


@pytest.fixture()
def server():
    return RawMCPServer(
        [
            RawTool(
                name="echo",
                description="Echo an integer.",
                input_schema={
                    "type": "object",
                    "required": ["value"],
                    "properties": {"value": {"type": "integer"}},
                },
                scope="skills:read",
                handler=echo,
            ),
            RawTool(
                name="explode",
                description="Always fails.",
                input_schema={"type": "object", "properties": {}},
                scope="skills:write",
                handler=explode,
            ),
        ]
    )


def call(server, name, arguments, scopes=None, request_id=1):
    return server.handle(
        {
            "jsonrpc": "2.0",
            "id": request_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        scopes,
    )


def test_initialize_handshake(server):
    response = server.handle(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        }
    )
    assert response["id"] == 1
    assert response["result"]["protocolVersion"] == "2024-11-05"
    assert response["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert response["result"]["serverInfo"] == {
        "name": "skills-engine",
        "version": "1.0.0",
    }


def test_initialize_defaults_protocol_version(server):
    response = server.handle({"jsonrpc": "2.0", "id": 2, "method": "initialize"})
    assert response["result"]["protocolVersion"] == "2025-06-18"


def test_notifications_return_none(server):
    assert (
        server.handle({"jsonrpc": "2.0", "method": "notifications/initialized"}) is None
    )
    assert server.handle({"jsonrpc": "2.0", "method": "tools/list"}) is None


def test_tools_list_filters_by_scope(server):
    everything = server.handle({"jsonrpc": "2.0", "id": 3, "method": "tools/list"})
    assert {t["name"] for t in everything["result"]["tools"]} == {"echo", "explode"}

    read_only = server.handle(
        {"jsonrpc": "2.0", "id": 4, "method": "tools/list"}, {"skills:read"}
    )
    assert [t["name"] for t in read_only["result"]["tools"]] == ["echo"]
    assert read_only["result"]["tools"][0]["inputSchema"]["required"] == ["value"]


def test_tools_call_success(server):
    response = call(server, "echo", {"value": 7}, {"skills:read"})
    result = response["result"]
    assert response["id"] == 1
    assert result["isError"] is False
    assert result["content"][0]["type"] == "text"
    assert "7" in result["content"][0]["text"]


def test_unknown_tool_is_invalid_params(server):
    response = call(server, "nope", {})
    assert response["error"]["code"] == -32602


def test_missing_required_argument_is_invalid_params(server):
    response = call(server, "echo", {}, {"skills:read"})
    assert response["error"]["code"] == -32602


def test_wrong_argument_type_is_invalid_params(server):
    response = call(server, "echo", {"value": "seven"}, {"skills:read"})
    assert response["error"]["code"] == -32602


def test_missing_scope_is_denied(server):
    response = call(server, "explode", {}, {"skills:read"})
    assert response["error"]["code"] == -32001


def test_unknown_method(server):
    response = server.handle({"jsonrpc": "2.0", "id": 5, "method": "resources/list"})
    assert response["error"]["code"] == -32601


def test_handler_error_becomes_tool_result(server):
    response = call(server, "explode", {}, {"skills:write"})
    assert "error" not in response
    assert response["result"]["isError"] is True
    assert "boom" in response["result"]["content"][0]["text"]


def test_malformed_request(server):
    assert server.handle({})["error"]["code"] == -32600
    assert server.handle("not a request")["error"]["code"] == -32600
    assert (
        server.handle(
            {"jsonrpc": "2.0", "id": 6, "method": "tools/list", "params": []}
        )["error"]["code"]
        == -32600
    )


def test_id_is_echoed(server):
    response = server.handle(
        {"jsonrpc": "2.0", "id": "abc-123", "method": "tools/list"}
    )
    assert response["id"] == "abc-123"
