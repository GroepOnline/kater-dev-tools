from __future__ import annotations

import logging
import os
import re
import threading
import time
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any

from kater.adapters.external import resolve_remote_headers
from kater.control_plane import (
    AccountState,
    ProviderAccount,
    QuotaAwareRouter,
    RouteBinding,
    RoutingDecision,
    RoutingRequest,
    clear_route_affinity,
    consume_quota,
    get_route_affinity,
    list_route_candidates,
    record_routing_decision,
    set_route_affinity,
    set_route_candidate_state,
)
from kater.doctor import parse_profiles
from kater.profiles import RiskLevel, ToolSource, Transport, all_tool_sources
from kater.proxy.aggregator import Aggregator
from kater.proxy.base import BackendOperationalError, BaseBackend
from kater.proxy.models import BackendStatus, ProxiedTool
from kater.proxy.sse_backend import SSEBackend
from kater.proxy.stdio_backend import StdioBackend
from kater.proxy.streamable_http_backend import StreamableHTTPBackend
from kater.settings import load_settings
from kater.telemetry import TelemetryEvent, record_event

logger = logging.getLogger("kater.proxy")

_ROUTE_META_KEY = "_kater_route"
MAX_CONTEXT_ID_LENGTH = 128
MAX_REQUIRED_SCOPES = 32
MAX_SCOPE_LENGTH = 64
MAX_ESTIMATED_UNITS = 1_000_000
_BEARER_SECRET = re.compile(r"(?i)\bBearer\s+[^\s,;]+")
_NAMED_SECRET = re.compile(
    r"(?i)\b(authorization|api[-_ ]?key|token|secret|password)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)


def _route_error_summary(error: str | None) -> str | None:
    if not error:
        return None
    text = " ".join(str(error).split())
    text = _BEARER_SECRET.sub("Bearer ***", text)
    text = _NAMED_SECRET.sub(r"\1\2***", text)
    return text[:500]


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
        self._probe_in_flight = False
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            self._maybe_half_open()
            return self._state

    def _maybe_half_open(self) -> None:
        if self._state == "open" and time.monotonic() - self._opened_at >= self._recovery_timeout:
            self._state = "half_open"
            self._probe_in_flight = False

    def can_call(self) -> bool:
        with self._lock:
            self._maybe_half_open()
            if self._state == "closed":
                return True
            if self._state == "half_open" and not self._probe_in_flight:
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
        self._route_lock = threading.Lock()
        self._route_in_flight: dict[tuple[str, str], int] = {}
        self._aggregator = Aggregator()
        self._router = QuotaAwareRouter()
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
            with self._route_lock:
                self._route_in_flight.clear()
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
        profile_names = parse_profiles(profile)
        settings = load_settings()
        for source in all_tool_sources():
            if source.transport == Transport.NATIVE:
                continue
            enabled_default = True
            if settings.high_risk_default_disabled and source.risk == RiskLevel.HIGH:
                enabled_default = False
            if not settings.is_server_enabled(source.name, default=enabled_default):
                continue
            if not profile_names.intersection(source.profiles) and "core" not in profile_names:
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
                logger.info("Started %s: %d tools", source.name, len(tools))
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

    def _compatible_route_bindings(
        self,
        bindings: list[RouteBinding],
    ) -> list[tuple[RouteBinding, ProxiedTool]]:
        """Keep only candidates with an identical object-shaped MCP input schema."""
        compatible: list[tuple[RouteBinding, ProxiedTool]] = []
        canonical_schema: dict[str, Any] | None = None
        for binding in bindings:
            source = self._aggregator.get_tool(
                f"{binding.account.backend}__{binding.account.tool_name}"
            )
            if source is None:
                continue
            schema = dict(source.input_schema or {})
            if schema.get("type") not in (None, "object"):
                logger.warning(
                    "route candidate %s/%s excluded: non-object schema",
                    binding.capability,
                    binding.account.account_id,
                )
                continue
            if canonical_schema is None:
                canonical_schema = schema
            if schema != canonical_schema:
                logger.warning(
                    "route candidate %s/%s excluded: schema mismatch for %s",
                    binding.capability,
                    binding.account.account_id,
                    binding.account.tool_name,
                )
                continue
            compatible.append((binding, source))
        return compatible

    def list_tools(self) -> list[dict[str, Any]]:
        from kater.capabilities.discovery import CapabilityDenied, assert_invocable

        tools = self._aggregator.for_mcp()
        seen = {item["name"] for item in tools}
        grouped: dict[str, list[RouteBinding]] = {}
        for binding in list_route_candidates():
            grouped.setdefault(binding.capability, []).append(binding)
        for capability, bindings in grouped.items():
            if capability in seen:
                continue
            try:
                assert_invocable(capability)
            except CapabilityDenied:
                # Managed + non-invocable capabilities stay hidden from discovery.
                continue
            compatible = self._compatible_route_bindings(bindings)
            if not compatible:
                continue
            source = compatible[0][1]
            schema = dict(source.input_schema or {})
            properties = dict(schema.get("properties") or {})
            properties[_ROUTE_META_KEY] = {
                "type": "object",
                "description": (
                    "Optional routing hints. Context is an affinity key, not an identity."
                ),
                "properties": {
                    "context_id": {
                        "type": "string",
                        "maxLength": MAX_CONTEXT_ID_LENGTH,
                        "description": "Affinity key only; not an authenticated principal.",
                    },
                    "required_scopes": {
                        "type": "array",
                        "description": (
                            "Routing compatibility constraint only; not authorization."
                        ),
                        "items": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": MAX_SCOPE_LENGTH,
                        },
                        "maxItems": MAX_REQUIRED_SCOPES,
                    },
                    "estimated_units": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": MAX_ESTIMATED_UNITS,
                    },
                },
                "additionalProperties": False,
            }
            schema["type"] = "object"
            schema["properties"] = properties
            tools.append(
                {
                    "name": capability,
                    "description": (
                        f"[Kater route pool] {source.description} "
                        f"({len(compatible)} compatible candidates)"
                    ),
                    "inputSchema": schema,
                }
            )
            seen.add(capability)
        return tools

    def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        from kater.capabilities.discovery import CapabilityDenied, assert_invocable

        # Re-check registry on every invoke: discovery is not authority (CHE-659).
        try:
            assert_invocable(name)
        except CapabilityDenied as exc:
            return {
                "error": str(exc),
                "code": "capability_denied",
                "capability_id": exc.capability_id,
                "reason": exc.reason,
            }
        route = self._aggregator.resolve(name)
        if route is not None:
            result, _ = self._call_backend(route[0], route[1], arguments)
            return result
        return self._call_logical_tool(name, arguments)

    def _call_backend(
        self,
        backend_name: str,
        original_name: str,
        arguments: dict[str, Any],
        *,
        record_tool_errors: bool = True,
    ) -> tuple[dict[str, Any], bool]:
        # Second tuple element is fallback_safe: True only when the request
        # was never dispatched (safe to try another account).
        _ = record_tool_errors
        breaker = self._breakers.get(backend_name)
        if breaker is not None and not breaker.can_call():
            return {"error": f"Circuit open for {backend_name}"}, True
        backend = self._backends.get(backend_name)
        if not backend:
            if breaker is not None:
                breaker.record_failure()
            return {"error": f"Backend not available: {backend_name}"}, True
        # Allow breaker-authorized half-open probes even when the previous
        # call latched healthy=False. Block only when the process/session is down.
        if not backend.is_healthy() and not getattr(backend, "_running", False):
            if breaker is not None:
                breaker.record_failure()
            return {"error": f"Backend unhealthy: {backend_name}"}, True
        try:
            result = backend.call_tool(original_name, arguments)
        except BackendOperationalError as exc:
            if breaker is not None:
                breaker.record_failure()
            logger.warning(
                "backend %s transport failed: %s (fallback_safe=%s)",
                backend_name,
                type(exc).__name__,
                exc.fallback_safe,
            )
            return (
                {"error": f"Backend error: {type(exc).__name__}"},
                bool(exc.fallback_safe),
            )
        except Exception as exc:
            # Programming / unexpected errors: trip breaker, do NOT fallback
            # (may have already executed upstream).
            if breaker is not None:
                breaker.record_failure()
            logger.warning(
                "backend %s invocation failed: %s",
                backend_name,
                type(exc).__name__,
            )
            return {"error": f"Backend error: {type(exc).__name__}"}, False
        # Valid MCP response (success or business error): restore health +
        # clear half-open; never fallback.
        backend._status.healthy = True
        backend._status.error = None
        if breaker is not None:
            breaker.record_success()
        return result, False

    def _parse_route_meta(
        self, arguments: dict[str, Any]
    ) -> tuple[dict[str, Any], str, frozenset[str], int] | dict[str, Any]:
        """Return (call_args, context_id, scopes, units) or an error dict."""
        call_arguments = dict(arguments)
        if _ROUTE_META_KEY not in call_arguments:
            return call_arguments, "mcp-default", frozenset(), 1
        raw_meta = call_arguments.pop(_ROUTE_META_KEY)
        if not isinstance(raw_meta, dict):
            return {"error": "_kater_route must be an object"}
        unknown = set(raw_meta) - {"context_id", "required_scopes", "estimated_units"}
        if unknown:
            return {"error": ("_kater_route has unknown fields: " + ", ".join(sorted(unknown)))}
        raw_context = raw_meta.get("context_id", "mcp-default")
        if not isinstance(raw_context, str):
            return {"error": "_kater_route.context_id must be a string"}
        context_id = raw_context.strip() or "mcp-default"
        if len(context_id) > MAX_CONTEXT_ID_LENGTH:
            return {
                "error": (f"_kater_route.context_id exceeds {MAX_CONTEXT_ID_LENGTH} characters")
            }
        raw_scopes = raw_meta.get("required_scopes", [])
        if raw_scopes is None:
            raw_scopes = []
        if not isinstance(raw_scopes, list):
            return {"error": "_kater_route.required_scopes must be an array of strings"}
        if len(raw_scopes) > MAX_REQUIRED_SCOPES:
            return {"error": (f"_kater_route.required_scopes exceeds {MAX_REQUIRED_SCOPES} items")}
        scopes: list[str] = []
        for item in raw_scopes:
            if not isinstance(item, str) or not item:
                return {"error": "_kater_route.required_scopes items must be non-empty strings"}
            if len(item) > MAX_SCOPE_LENGTH:
                return {
                    "error": (
                        f"_kater_route.required_scopes item exceeds {MAX_SCOPE_LENGTH} characters"
                    )
                }
            scopes.append(item)
        raw_units = raw_meta.get("estimated_units", 1)
        if isinstance(raw_units, bool) or not isinstance(raw_units, int):
            return {"error": "_kater_route.estimated_units must be an integer >= 1"}
        if raw_units < 1 or raw_units > MAX_ESTIMATED_UNITS:
            return {
                "error": (
                    f"_kater_route.estimated_units must be between 1 and {MAX_ESTIMATED_UNITS}"
                )
            }
        return call_arguments, context_id, frozenset(scopes), raw_units

    def _call_logical_tool(
        self,
        capability: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        bindings = list_route_candidates(capability)
        if not bindings:
            return {"error": f"Unknown tool: {capability}"}
        compatible = self._compatible_route_bindings(bindings)
        if not compatible:
            return {"error": f"No available schema-compatible route for {capability}"}

        parsed = self._parse_route_meta(arguments)
        if isinstance(parsed, dict):
            return parsed
        call_arguments, context_id, required_scopes, estimated_units = parsed

        accounts = [
            self._runtime_account(binding.account, capability) for binding, _source in compatible
        ]
        request = RoutingRequest(
            capability=capability,
            context_id=context_id,
            required_scopes=required_scopes,
            estimated_units=estimated_units,
        )
        ranked = self._router.rank(accounts, request)
        affinity = get_route_affinity(capability, context_id)
        if affinity:
            ranked.sort(key=lambda item: item.account_id != affinity)
        if not ranked:
            return {
                "error": f"No eligible route for {capability}",
                "context_id": context_id,
            }

        concurrent_limits = {account.account_id: account.max_concurrent for account in accounts}
        attempts: list[dict[str, Any]] = []
        last_error = "no route attempted"
        for decision in ranked:
            key = (capability, decision.account_id)
            # Atomic check-and-reserve against max_concurrent so two callers
            # cannot both take the last slot.
            with self._route_lock:
                current = self._route_in_flight.get(key, 0)
                limit = concurrent_limits.get(decision.account_id, 1)
                if current >= limit:
                    attempts.append(
                        {
                            "account_id": decision.account_id,
                            "backend": decision.backend,
                            "tool_name": decision.tool_name,
                            "error": "max_concurrent reached",
                            "retriable": True,
                        }
                    )
                    continue
                self._route_in_flight[key] = current + 1
            try:
                result, fallback_safe = self._call_backend(
                    decision.backend,
                    decision.tool_name,
                    call_arguments,
                    record_tool_errors=False,
                )
            finally:
                with self._route_lock:
                    remaining = self._route_in_flight.get(key, 1) - 1
                    if remaining > 0:
                        self._route_in_flight[key] = remaining
                    else:
                        self._route_in_flight.pop(key, None)

            error = str(result.get("error", "")) if "error" in result else None
            if error is None:
                # Upstream succeeded — never replace the result with a
                # bookkeeping failure (would encourage client-side replay).
                try:
                    consume_quota(capability, decision.account_id, estimated_units)
                    set_route_candidate_state(
                        capability,
                        decision.account_id,
                        AccountState.ACTIVE,
                    )
                    set_route_affinity(capability, context_id, decision.account_id)
                    self._record_route_event(request, decision, "success")
                except Exception as exc:
                    logger.warning(
                        "post-success route bookkeeping failed for %s: %s",
                        capability,
                        exc,
                    )
                return result

            last_error = error
            outcome = "fallback" if fallback_safe else "failed"
            if fallback_safe:
                clear_route_affinity(
                    capability,
                    context_id,
                    account_id=decision.account_id,
                )
                set_route_candidate_state(
                    capability,
                    decision.account_id,
                    AccountState.COOLDOWN,
                    cooldown_until=(datetime.now(UTC) + timedelta(seconds=self._recovery_timeout)),
                )
            self._record_route_event(request, decision, outcome, error=error)
            attempts.append(
                {
                    "account_id": decision.account_id,
                    "backend": decision.backend,
                    "tool_name": decision.tool_name,
                    "error": _route_error_summary(error),
                    "retriable": fallback_safe,
                }
            )
            if not fallback_safe:
                return result

        return {
            "error": f"All routes failed for {capability}: {_route_error_summary(last_error)}",
            "attempts": attempts,
        }

    def _runtime_account(self, account: ProviderAccount, capability: str) -> ProviderAccount:
        key = (capability, account.account_id)
        with self._route_lock:
            in_flight = self._route_in_flight.get(key, 0)
        backend = self._backends.get(account.backend)
        latency_ms = account.latency_ms
        if backend is not None:
            latency_ms = backend.status.latency_ms or latency_ms
        return replace(account, in_flight=in_flight, latency_ms=latency_ms)

    def _record_route_event(
        self,
        request: RoutingRequest,
        decision: RoutingDecision,
        outcome: str,
        *,
        error: str | None = None,
    ) -> None:
        safe_error = _route_error_summary(error)
        try:
            record_routing_decision(
                request,
                decision,
                outcome=outcome,
                error=safe_error,
            )
        except Exception as exc:
            logger.warning("failed to persist routing decision: %s", exc)
        record_event(
            TelemetryEvent(
                type="route_decision",
                name=request.capability,
                success=outcome == "success",
                metadata={
                    "context_id": request.context_id,
                    "account_id": decision.account_id,
                    "provider": decision.provider,
                    "backend": decision.backend,
                    "tool_name": decision.tool_name,
                    "estimated_units": request.estimated_units,
                    "score": decision.score,
                    "reasons": decision.reasons,
                    "outcome": outcome,
                    "error": safe_error,
                },
            )
        )

    def statuses(self) -> list[BackendStatus]:
        result = []
        for name, backend in self._backends.items():
            status = backend.status
            breaker = self._breakers.get(name)
            status.breaker_state = breaker.state if breaker else "unknown"
            result.append(status)
        return result

    def health_check(self) -> dict[str, bool]:
        return {name: backend.is_healthy() for name, backend in self._backends.items()}

    def tool_count(self) -> int:
        return len(self.list_tools())

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
