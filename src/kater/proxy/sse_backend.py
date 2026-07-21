from __future__ import annotations

import json
import logging
import urllib.request
from typing import Any

from kater.proxy.base import BackendOperationalError, BaseBackend

_log = logging.getLogger("kater.proxy.sse")


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

    def _connect(self) -> None:
        self._discover_endpoint()

    def _disconnect(self) -> None:
        pass

    def _discover_endpoint(self) -> None:
        req = urllib.request.Request(
            self._url,
            headers={"Accept": "text/event-stream", **self._headers},
        )
        try:
            # URL is operator-configured in profiles.py, not user input.
            resp = urllib.request.urlopen(req, timeout=self._timeout)
            for line in resp:
                line = line.decode().strip()
                if line.startswith("data:"):
                    data = json.loads(line[5:].strip())
                    if data.get("type") == "endpoint":
                        base = self._url.rsplit("/", 1)[0]
                        self._endpoint = f"{base}{data.get('uri', '')}"
                        return
        except Exception as exc:
            _log.debug("sse endpoint discovery failed for %s: %s", self.name, exc)
        if not self._endpoint:
            self._endpoint = self._url.replace("/sse", "/messages")

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self._endpoint:
            error = "no endpoint discovered"
            self._status.error = error
            self._status.healthy = False
            raise BackendOperationalError(error, fallback_safe=True)
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
                parsed = json.loads(resp.read())
                if (
                    not isinstance(parsed, dict)
                    or parsed.get("jsonrpc") != "2.0"
                    or ("result" not in parsed and "error" not in parsed)
                ):
                    raise ValueError("unexpected malformed SSE response")
                return parsed
            except Exception as exc:
                self._status.error = str(exc)
                self._status.healthy = False
                raise BackendOperationalError(str(exc), fallback_safe=False) from exc
