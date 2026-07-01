from __future__ import annotations

import logging
import os
import threading
import time
from typing import Any

from kater.adapters.external import resolve_remote_headers
from kater.profiles import TOOL_SOURCES, RiskLevel, ToolSource, Transport
from kater.proxy.aggregator import Aggregator
from kater.proxy.base import BaseBackend
from kater.proxy.models import BackendStatus
from kater.proxy.sse_backend import SSEBackend
from kater.proxy.stdio_backend import StdioBackend
from kater.proxy.streamable_http_backend import StreamableHTTPBackend
from kater.settings import load_settings

logger = logging.getLogger("kater.proxy")


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failures = 0
        self._state = "closed"
        self._opened_at = 0.0
        # Half-open admits exactly one trial call; concurrent callers are
        # rejected until the probe resolves (closed or re-opened).
        self._probe_in_flight = False
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            self._maybe_half_open()
            return self._state

    def _maybe_half_open(self) -> None:
        if (
            self._state == "open"
            and time.monotonic() - self._opened_at >= self._recovery_timeout
        ):
            self._state = "half_open"
            self._probe_in_flight = False

    def can_call(self) -> bool:
        with self._lock:
            self._maybe_half_open()
            if self._state == "closed":
                return True
            if self._state == "half_open" and not self._probe_in_flight:
                # Reserve the single probe slot so only one caller gets through.
                self._probe_in_flight = True
                return True
            return False

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = "closed"
            self._probe_in_flight = False

    def record_failure(self) -> None:
        with self._lock:
            self._failures += 1
            if self._state == "half_open":
                self._state = "open"
                self._opened_at = time.monotonic()
                self._probe_in_flight = False
            elif self._failures >= self._failure_threshold:
                self._state = "open"
                self._opened_at = time.monotonic()
                self._probe_in_flight = False


class ProxyManager:
    def __init__(self) -> None:
        self._backends: dict[str, BaseBackend] = {}
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()
        self._aggregator = Aggregator()
        self._started = False
        settings = load_settings()
        self._failure_threshold = settings.proxy_failure_threshold
        self._recovery_timeout = settings.proxy_recovery_timeout

    def start(self, profile: str) -> None:
        with self._lock:
            if self._started:
                return
            self._start_backends(profile)
            self._started = True

    def stop(self) -> None:
        with self._lock:
            for name, backend in list(self._backends.items()):
                try:
                    backend.stop()
                except Exception as exc:
                    logger.warning("Error stopping %s: %s", name, exc)
            self._backends.clear()
            self._breakers.clear()
            self._aggregator.clear()
            self._started = False

    def register_backend(self, name: str, backend: BaseBackend) -> None:
        with self._lock:
            backend.start()
            tools = backend.list_tools()
            self._aggregator.add_backend_tools(name, tools)
            self._backends[name] = backend
            self._breakers[name] = CircuitBreaker(
                failure_threshold=self._failure_threshold,
                recovery_timeout=self._recovery_timeout,
            )

    def _start_backends(self, profile: str) -> None:
        settings = load_settings()
        for source in TOOL_SOURCES:
            if source.transport == Transport.NATIVE:
                continue
            default_enabled = source.default_enabled
            if settings.high_risk_default_disabled and source.risk == RiskLevel.HIGH:
                default_enabled = False
            if not settings.is_server_enabled(source.name, default=default_enabled):
                continue
            if profile not in source.profiles and profile != "core":
                continue
            if not source.mcp:
                continue
            env_ok = all(os.environ.get(v) for v in source.env)
            if source.env and not env_ok:
                continue
            backend = self._create_backend(source)
            if backend is None:
                continue
            try:
                backend.start()
                tools = backend.list_tools()
                self._aggregator.add_backend_tools(source.name, tools)
                self._backends[source.name] = backend
                self._breakers[source.name] = CircuitBreaker(
                    failure_threshold=self._failure_threshold,
                    recovery_timeout=self._recovery_timeout,
                )
                logger.info(
                    "Started %s: %d tools", source.name, len(tools)
                )
            except Exception as exc:
                logger.warning("Failed to start %s: %s", source.name, exc)

    def _create_backend(self, source: ToolSource) -> BaseBackend | None:
        if source.transport == Transport.STDIO:
            if not source.mcp or not source.mcp.command:
                return None
            env: dict[str, str] = {}
            for key, val in source.mcp.env_template.items():
                if val.startswith("${") and val.endswith("}"):
                    env_var = val[2:-1]
                    real = os.environ.get(env_var)
                    if real:
                        env[key] = real
                else:
                    env[key] = val
            return StdioBackend(
                name=source.name,
                command=source.mcp.command,
                args=source.mcp.args,
                env=env,
            )
        if source.transport in (Transport.SSE, Transport.HTTP):
            if not source.mcp:
                return None
            url = source.mcp.url or ""
            if not url:
                return None
            for var in source.env:
                env_val = os.environ.get(var)
                if env_val:
                    url = url.replace(f"${{{var}}}", env_val)
            if "${" in url and "}" in url:
                return None
            headers = resolve_remote_headers(source, include_secrets=True)
            if url.rstrip("/").endswith("/mcp"):
                return StreamableHTTPBackend(
                    name=source.name,
                    url=url,
                    headers=headers,
                )
            return SSEBackend(name=source.name, url=url, headers=headers)
        return None

    def list_tools(self) -> list[dict[str, Any]]:
        return self._aggregator.for_mcp()

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        route = self._aggregator.resolve(name)
        if route is None:
            return {"error": f"Unknown tool: {name}"}
        backend_name, original_name = route
        breaker = self._breakers.get(backend_name)
        if breaker is not None and not breaker.can_call():
            return {"error": f"Circuit open for {backend_name}"}
        backend = self._backends.get(backend_name)
        if not backend:
            # can_call() may have reserved a half-open probe; release it as a
            # failure so the slot does not leak while the backend is missing.
            if breaker is not None:
                breaker.record_failure()
            return {"error": f"Backend not available: {backend_name}"}
        if not backend.is_healthy():
            if breaker is not None:
                breaker.record_failure()
            return {"error": f"Backend unhealthy: {backend_name}"}
        try:
            result = backend.call_tool(original_name, arguments)
        except Exception as exc:
            result = {"error": f"Backend error: {exc}"}
        if breaker is not None:
            if "error" in result:
                breaker.record_failure()
            else:
                breaker.record_success()
        return result

    def statuses(self) -> list[BackendStatus]:
        result = []
        for name, backend in self._backends.items():
            status = backend.status
            breaker = self._breakers.get(name)
            status.breaker_state = breaker.state if breaker else "unknown"
            result.append(status)
        return result

    def health_check(self) -> dict[str, bool]:
        return {
            name: backend.is_healthy()
            for name, backend in self._backends.items()
        }

    def tool_count(self) -> int:
        return self._aggregator.count()

    def backend_count(self) -> int:
        return len(self._backends)

    @property
    def started(self) -> bool:
        return self._started


_proxy: ProxyManager | None = None
_proxy_lock = threading.Lock()


def get_proxy() -> ProxyManager:
    global _proxy
    if _proxy is None:
        with _proxy_lock:
            if _proxy is None:
                _proxy = ProxyManager()
    return _proxy


def reset_proxy() -> None:
    global _proxy
    with _proxy_lock:
        if _proxy is not None:
            _proxy.stop()
        _proxy = None
