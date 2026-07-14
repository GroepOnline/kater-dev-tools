from __future__ import annotations

import json
import logging
import urllib.error
import urllib.request
from typing import Any

from kater.proxy.base import BackendOperationalError, BaseBackend

_log = logging.getLogger("kater.proxy.streamable_http")


class StreamableHTTPBackend(BaseBackend):
    """MCP Streamable HTTP transport (POST /mcp, SSE-framed responses)."""

    def __init__(
        self,
        name: str,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__()
        self.name = name
        self._url = url
        self._headers = headers or {}
        self._timeout = timeout
        self._next_id = 1
        self._session_id: str | None = None

    def _connect(self) -> None:
        pass

    def _disconnect(self) -> None:
        pass

    def _parse_sse_body(self, body: str) -> dict[str, Any]:
        for line in body.splitlines():
            if line.startswith("data:"):
                return json.loads(line[5:].strip())
        if not body.strip():
            raise ValueError("unexpected empty streamable HTTP response")
        return json.loads(body)

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
        is_notification = method.startswith("notifications/")
        if not is_notification:
            msg["id"] = self._next_id
            self._next_id += 1
        if params:
            msg["params"] = params

        req_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self._headers,
        }
        if self._session_id:
            req_headers["mcp-session-id"] = self._session_id

        req = urllib.request.Request(
            self._url,
            data=json.dumps(msg).encode(),
            headers=req_headers,
            method="POST",
        )
        with self._lock:
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    session = resp.headers.get("mcp-session-id")
                    if session:
                        self._session_id = session
                    raw = resp.read().decode()
                if is_notification and not raw.strip():
                    return {}
                parsed = self._parse_sse_body(raw)
                if (
                    not isinstance(parsed, dict)
                    or parsed.get("jsonrpc") != "2.0"
                    or ("result" not in parsed and "error" not in parsed)
                ):
                    raise ValueError(
                        "unexpected malformed streamable HTTP response"
                    )
                return parsed
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode(errors="replace")
                self._status.error = detail or str(exc)
                self._status.healthy = False
                raise BackendOperationalError(detail or str(exc)) from exc
            except Exception as exc:
                self._status.error = str(exc)
                self._status.healthy = False
                raise BackendOperationalError(str(exc)) from exc
