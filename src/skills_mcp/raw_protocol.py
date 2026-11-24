"""Dependency-free MCP tool surface over JSON-RPC 2.0.

FastMCP remains the transport. This module proves the protocol-level behavior
(handshake, schemas, scopes) without the SDK and is used by the tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

PROTOCOL_VERSION = "2025-06-18"

_TYPES: dict[str, tuple[type, ...]] = {
    "object": (dict,),
    "string": (str,),
    "number": (int, float),
    "integer": (int,),
    "boolean": (bool,),
    "array": (list,),
}


@dataclass(frozen=True)
class RawTool:
    name: str
    description: str
    input_schema: dict
    scope: str
    handler: Callable[[dict], Any]


def _error(request_id, code: int, message: str) -> dict:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _result(request_id, result: dict) -> dict:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _valid_type(value: Any, kind: str) -> bool:
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, _TYPES[kind])


class RawMCPServer:
    def __init__(
        self,
        tools: list[RawTool],
        server_name: str = "skills-engine",
        version: str = "1.0.0",
    ) -> None:
        self.tools = {tool.name: tool for tool in tools}
        self.server_name = server_name
        self.version = version

    def handle(
        self, request: Any, granted_scopes: set[str] | None = None
    ) -> dict | None:
        if not isinstance(request, dict) or request.get("jsonrpc") != "2.0":
            return _error(None, -32600, "invalid request")
        if "id" not in request:
            return None
        request_id = request["id"]
        method = request.get("method")
        params = request.get("params", {})
        if not isinstance(method, str) or not isinstance(params, dict):
            return _error(request_id, -32600, "invalid request")

        if method == "initialize":
            return _result(
                request_id,
                {
                    "protocolVersion": params.get("protocolVersion", PROTOCOL_VERSION),
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": self.server_name, "version": self.version},
                },
            )
        if method == "tools/list":
            visible = [
                t
                for t in self.tools.values()
                if granted_scopes is None or t.scope in granted_scopes
            ]
            return _result(
                request_id,
                {
                    "tools": [
                        {
                            "name": t.name,
                            "description": t.description,
                            "inputSchema": t.input_schema,
                            "scope": t.scope,
                        }
                        for t in visible
                    ]
                },
            )
        if method == "tools/call":
            return self._call(request_id, params, granted_scopes)
        return _error(request_id, -32601, f"method not found: {method}")

    def _call(self, request_id, params: dict, granted_scopes: set[str] | None) -> dict:
        tool = self.tools.get(params.get("name"))
        if tool is None:
            return _error(request_id, -32602, f"unknown tool: {params.get('name')}")
        if granted_scopes is not None and tool.scope not in granted_scopes:
            return _error(request_id, -32001, f"missing scope: {tool.scope}")

        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            return _error(request_id, -32602, "arguments must be an object")
        error = self._validate(tool.input_schema, arguments)
        if error:
            return _error(request_id, -32602, error)

        try:
            value = tool.handler(arguments)
        except Exception as exc:  # tool failure is a result, not a protocol error
            return _result(
                request_id,
                {
                    "content": [{"type": "text", "text": f"error: {exc}"}],
                    "isError": True,
                },
            )
        text = value if isinstance(value, str) else json.dumps(value, default=str)
        return _result(
            request_id,
            {
                "content": [{"type": "text", "text": text}],
                "isError": False,
            },
        )

    @staticmethod
    def _validate(schema: dict, arguments: dict) -> str | None:
        properties = schema.get("properties", {})
        for name in schema.get("required", []):
            if name not in arguments:
                return f"missing required argument: {name}"
        for name, value in arguments.items():
            spec = properties.get(name)
            if (
                spec
                and spec.get("type") in _TYPES
                and not _valid_type(value, spec["type"])
            ):
                return f"argument {name} must be {spec['type']}"
        return None
