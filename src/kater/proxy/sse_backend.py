from __future__ import annotations

import json
import urllib.request
from typing import Any

from kater.proxy.base import BaseBackend
from kater.proxy.models import ProxiedTool


class SSEBackend(BaseBackend):
    def __init__(
        self,
        name: str,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 15.0,
    ) -> None:
        super().__init__()
        self.name = name
        self._url = url
        self._headers = headers or {}
        self._timeout = timeout
        self._next_id = 1
        self._endpoint: str | None = None

    def start(self) -> None:
        try:
            self._discover_endpoint()
            self._initialize()
            self._refresh_tools()
            self._running = True
            self._status.healthy = True
        except Exception as exc:
            self._status.error = str(exc)
            self._status.healthy = False

    def stop(self) -> None:
        self._running = False

    def _discover_endpoint(self) -> None:
        req = urllib.request.Request(
            self._url,
            headers={"Accept": "text/event-stream", **self._headers},
        )
        try:
            resp = urllib.request.urlopen(req, timeout=self._timeout)
            for line in resp:
                line = line.decode().strip()
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    if data.get("type") == "endpoint":
                        base = self._url.rsplit("/", 1)[0]
                        self._endpoint = f"{base}{data.get('uri', '')}"
                        return
        except Exception:
            pass
        if not self._endpoint:
            self._endpoint = self._url.replace("/sse", "/messages")

    def _post_jsonrpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._endpoint:
            return {"error": "no endpoint discovered"}
        msg = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params:
            msg["params"] = params
        self._next_id += 1
        body = json.dumps(msg).encode()
        req = urllib.request.Request(
            self._endpoint,
            data=body,
            headers={
                "Content-Type": "application/json",
                **self._headers,
            },
        )
        with self._lock:
            try:
                resp = urllib.request.urlopen(req, timeout=self._timeout)
                return json.loads(resp.read())
            except Exception as exc:
                self._status.error = str(exc)
                self._status.healthy = False
                return {"error": str(exc)}

    def _initialize(self) -> None:
        self._post_jsonrpc("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "kater-proxy", "version": "1.0"},
        })

    def _refresh_tools(self) -> None:
        result = self._post_jsonrpc("tools/list")
        tools_data = result.get("result", {}).get("tools", [])
        self._tools = [
            ProxiedTool(
                name=t["name"],
                description=t.get("description", ""),
                backend=self.name,
                original_name=t["name"],
                input_schema=t.get("inputSchema", {}),
            )
            for t in tools_data
        ]

    def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        result = self._post_jsonrpc("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        if "error" in result:
            return result
        return result.get("result", result)
