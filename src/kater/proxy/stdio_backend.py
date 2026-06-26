from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Any

from kater.proxy.base import BaseBackend
from kater.proxy.models import ProxiedTool


class StdioBackend(BaseBackend):
    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__()
        self.name = name
        self._command = command
        self._args = args or []
        self._env = {**os.environ, **(env or {})}
        self._timeout = timeout
        self._proc: subprocess.Popen[bytes] | None = None
        self._next_id = 1

    def start(self) -> None:
        try:
            self._proc = subprocess.Popen(
                [self._command, *self._args],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self._env,
            )
            self._running = True
            self._initialize()
            self._refresh_tools()
            self._status.healthy = True
        except (OSError, FileNotFoundError) as exc:
            self._status.error = str(exc)
            self._status.healthy = False
            self._running = False

    def stop(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            except OSError:
                pass
            self._proc = None
        self._running = False

    def _send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._proc or not self._proc.stdin or not self._proc.stdout:
            return {"error": "backend not started"}

        msg = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
        }
        if params:
            msg["params"] = params
        self._next_id += 1

        with self._lock:
            try:
                self._proc.stdin.write(
                    (json.dumps(msg) + "\n").encode()
                )
                self._proc.stdin.flush()

                deadline = time.time() + self._timeout
                while time.time() < deadline:
                    line = self._proc.stdout.readline()
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line.decode())
                    if data.get("id") == msg["id"]:
                        return data
                return {"error": "timeout waiting for response"}
            except (OSError, json.JSONDecodeError) as exc:
                self._status.error = str(exc)
                self._status.healthy = False
                return {"error": str(exc)}

    def _initialize(self) -> None:
        self._send("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "kater-proxy", "version": "1.0"},
        })
        self._send("notifications/initialized")

    def _refresh_tools(self) -> None:
        result = self._send("tools/list")
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
        result = self._send("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        if "error" in result:
            return result
        return result.get("result", result)
