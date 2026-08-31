#!/usr/bin/env sh
set -eu

if ! curl -sf http://127.0.0.1:9091/health >/dev/null; then
  echo "e2e-mcp: kater is not running on :9091" >&2
  echo "Start with: KATER_PROXY=1 KATER_PROFILE=ops kater serve" >&2
  exit 1
fi

uv run python - <<'PY'
import asyncio
import base64
import json
import os
import socket
import sys
import urllib.request

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    mark = "ok" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail else ""))
    if not ok:
        failures.append(name)


for path in (
    "/health",
    "/api/status",
    "/api/catalog",
    "/api/spec",
    "/dashboard",
    "/studio",
    "/studio/assets/studio.js",
    "/studio/assets/studio.css",
):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:9091{path}", timeout=10) as resp:
            check(f"REST {path}", resp.status == 200)
    except Exception as exc:
        check(f"REST {path}", False, str(exc))


async def mcp_checks() -> None:
    from mcp import ClientSession
    from mcp.client.sse import sse_client

    async with sse_client("http://127.0.0.1:9090/sse") as (read, write):
        async with ClientSession(read, write) as session:
            init = await session.initialize()
            info = getattr(init, "server_info", None) or getattr(init, "serverInfo", None)
            check(
                "MCP initialize",
                info is not None,
                (getattr(info, "name", None) or "") if info is not None else "",
            )
            tools = await session.list_tools()
            names = [tool.name for tool in tools.tools]
            check("MCP tools/list", len(names) > 0, f"{len(names)} tools")
            check("MCP native tools", "kater_profiles" in names)

            profiles = await session.call_tool("kater_profiles", {})
            profiles_text = profiles.content[0].text if profiles.content else ""
            check(
                "MCP tools/call kater_profiles",
                "profiles" in profiles_text and "Error executing tool" not in profiles_text,
                profiles_text[:120],
            )

            proxy_enabled = False
            if "kater_proxy_status" in names:
                payload = json.loads((await session.call_tool("kater_proxy_status", {})).content[0].text)
                proxy_enabled = bool(payload.get("enabled"))
                check(
                    "kater_proxy_status",
                    True,
                    f"enabled={payload.get('enabled')} backends={payload.get('backends')} tools={payload.get('tools')}",
                )

            if proxy_enabled and any(name.startswith("linear__") for name in names):
                result = await session.call_tool("linear__list_issues", {"limit": 1})
                body = result.content[0].text if result.content else ""
                check("linear__list_issues", "Error executing tool" not in body, body[:120])


asyncio.run(mcp_checks())

sock = socket.create_connection(("127.0.0.1", 9092), timeout=5)
ws_key = base64.b64encode(os.urandom(16)).decode()
sock.sendall(
    b"GET /ws HTTP/1.1\r\n"
    b"Host: 127.0.0.1:9092\r\n"
    b"Upgrade: websocket\r\n"
    b"Connection: Upgrade\r\n"
    + f"Sec-WebSocket-Key: {ws_key}\r\n".encode()
    + b"Sec-WebSocket-Version: 13\r\n\r\n"
)
upgrade = sock.recv(4096).decode(errors="replace")
sock.close()
check("WebSocket /ws", upgrade.split("\r\n", 1)[0].endswith("101 Switching Protocols"))

if failures:
    print("e2e-mcp failed:", ", ".join(failures), file=sys.stderr)
    raise SystemExit(1)

print("e2e-mcp ok")
PY
