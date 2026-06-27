"""End-to-end StdioBackend round-trip against a real subprocess MCP server.

The proxy engine was previously tested only with MockBackend; this spawns an
actual JSON-RPC-over-stdio server and exercises initialize -> tools/list ->
tools/call through StdioBackend, validating the subprocess transport, env
allowlist, and JSON-RPC framing for real.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

from kater.proxy.stdio_backend import StdioBackend

_ECHO_SERVER = textwrap.dedent("""
    import json, sys

    def send(msg):
        sys.stdout.write(json.dumps(msg) + "\\n")
        sys.stdout.flush()

    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            req = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "method" not in req:
            continue
        method = req["method"]
        rid = req.get("id")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "protocolVersion": "2024-11-05",
                "serverInfo": {"name": "echo", "version": "1.0"},
                "capabilities": {"tools": {}},
            }})
        elif method == "notifications/initialized":
            pass  # notification: no response
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": rid, "result": {"tools": [
                {"name": "echo", "description": "Echo back the message",
                 "inputSchema": {"type": "object",
                                 "properties": {"message": {"type": "string"}},
                                 "required": ["message"]}},
            ]}})
        elif method == "tools/call":
            params = req.get("params", {})
            msg = params.get("arguments", {}).get("message", "")
            send({"jsonrpc": "2.0", "id": rid, "result": {
                "content": [{"type": "text", "text": f"echo: {msg}"}],
            }})
""")


def _server_path(tmp_path: Path) -> Path:
    p = tmp_path / "echo_server.py"
    p.write_text(_ECHO_SERVER, encoding="utf-8")
    return p


def test_stdio_backend_full_round_trip(tmp_path):
    server = _server_path(tmp_path)
    backend = StdioBackend(
        name="echo",
        command=sys.executable,
        args=[str(server)],
        env={"ECHO_MARKER": "present"},
    )
    try:
        backend.start()
        assert backend.is_healthy(), f"backend not healthy: {backend.status.error}"

        # Tool discovery over the real subprocess transport.
        tools = backend.list_tools()
        assert len(tools) == 1
        assert tools[0].name == "echo"

        # Tool call round-trip through stdin/stdout JSON-RPC.
        result = backend.call_tool("echo", {"message": "hello world"})
        text = result["content"][0]["text"]
        assert text == "echo: hello world"
    finally:
        backend.stop()


def test_stdio_backend_env_allowlist(tmp_path):
    """Only the safe passthrough set + declared env reach the subprocess."""
    import os

    server = _server_path(tmp_path)
    # Poison the parent env with a secret that must NOT be passed through.
    os.environ["LEAKED_SECRET"] = "should-not-propagate"
    try:
        backend = StdioBackend(
            name="echo",
            command=sys.executable,
            args=[str(server)],
            env={"ECHO_MARKER": "present"},
        )
        safe_env = backend._env
        assert "ECHO_MARKER" in safe_env
        assert "LEAKED_SECRET" not in safe_env
    finally:
        os.environ.pop("LEAKED_SECRET", None)


def test_stdio_backend_missing_binary_reports_unhealthy():
    backend = StdioBackend(
        name="ghost",
        command="definitely-not-a-real-binary-xyz",
        args=[],
    )
    backend.start()
    assert not backend.is_healthy()
    assert backend.status.error
