from __future__ import annotations

import functools
import inspect
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from kater.control_plane.usage import record_usage_event
from kater.storage import clear_all_events, insert_event, query_events

_log = logging.getLogger("kater.telemetry")


@dataclass
class TelemetryEvent:
    type: str
    name: str
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    success: bool = True
    profile: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "name": self.name,
            "timestamp": self.timestamp,
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "profile": self.profile,
            "metadata": self.metadata,
        }


def record_event(event: TelemetryEvent) -> None:
    insert_event(event.to_dict())
    if event.type == "route_decision":
        _emit_usage_from_route(event)
    try:
        from kater.websocket import broadcast_event

        broadcast_event(event.to_dict())
    except Exception as exc:
        _log.debug("telemetry broadcast failed: %s", exc)


def _emit_usage_from_route(event: TelemetryEvent) -> None:
    """Mirror control-plane route outcomes into the usage ledger."""
    meta = event.metadata or {}
    try:
        cost_raw = meta.get("estimated_units", 0)
        cost_units = float(cost_raw) if cost_raw is not None else 0.0
    except (TypeError, ValueError):
        cost_units = 0.0
    try:
        record_usage_event(
            capability=event.name,
            backend=meta.get("backend"),
            tool_name=meta.get("tool_name"),
            account_id=meta.get("account_id"),
            context_id=meta.get("context_id"),
            principal_id=meta.get("principal_id"),
            success=bool(event.success),
            duration_ms=float(event.duration_ms or 0),
            cost_units=cost_units,
            metadata={
                "outcome": meta.get("outcome"),
                "provider": meta.get("provider"),
                "error": meta.get("error"),
            },
            timestamp=event.timestamp,
        )
    except Exception as exc:
        _log.warning("usage event record failed for %s: %s", event.name, exc)


def record_tool_call(
    tool: str,
    success: bool = True,
    duration_ms: float = 0.0,
    profile: str | None = None,
    **metadata: Any,
) -> None:
    record_event(
        TelemetryEvent(
            type="tool_call",
            name=tool,
            success=success,
            duration_ms=duration_ms,
            profile=profile,
            metadata=metadata,
        )
    )


def wrap_tool_handler(
    name: str,
    handler: Callable[..., Any],
    *,
    profile: str | None = None,
) -> Callable[..., Any]:
    """Record a ``tool_call`` telemetry event around a native MCP handler.

    Telemetry failures never propagate: a CallTool must still return its result.
    Argument values are not copied into metadata (they can contain secrets).
    """

    @functools.wraps(handler)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        started = time.perf_counter()
        success = True
        try:
            return handler(*args, **kwargs)
        except Exception:
            success = False
            raise
        finally:
            try:
                record_tool_call(
                    name,
                    success=success,
                    duration_ms=(time.perf_counter() - started) * 1000.0,
                    profile=profile,
                )
            except Exception:
                _log.debug("tool_call telemetry failed for %s", name, exc_info=True)

    try:
        wrapped.__signature__ = inspect.signature(handler)  # type: ignore[attr-defined]
    except (TypeError, ValueError):
        pass
    return wrapped


def record_chain_run(
    chain: str,
    steps: int = 0,
    success: bool = True,
    profile: str | None = None,
    **metadata: Any,
) -> None:
    record_event(
        TelemetryEvent(
            type="chain_run",
            name=chain,
            success=success,
            profile=profile,
            metadata={"steps": steps, **metadata},
        )
    )


def record_server_toggle(server: str, action: str, enabled: bool) -> None:
    record_event(
        TelemetryEvent(
            type="server_toggle",
            name=server,
            metadata={"action": action, "enabled": enabled},
        )
    )


def record_error(source: str, message: str, **metadata: Any) -> None:
    record_event(
        TelemetryEvent(
            type="error",
            name=source,
            success=False,
            metadata={"message": message, **metadata},
        )
    )


def load_events(limit: int = 0) -> list[dict[str, Any]]:
    return query_events(limit=limit)


def clear_events() -> int:
    return clear_all_events()


# ── Aggregation / Evals ────────────────────────────────────────────


def eval_summary() -> dict[str, Any]:
    events = query_events()
    if not events:
        return {
            "total_events": 0,
            "time_span_s": 0,
            "tool_calls": {"total": 0, "unique_tools": 0, "per_tool": {}},
            "chain_runs": {"total": 0, "unique_chains": 0, "per_chain": {}},
            "errors": {"total": 0, "recent": []},
            "server_toggles": 0,
            "routing": {"total": 0, "success": 0, "fallback": 0, "failed": 0},
            "summary": {
                "total_tool_calls": 0,
                "total_chain_runs": 0,
                "total_errors": 0,
                "overall_success_rate": 0.0,
            },
        }

    tool_calls = [e for e in events if e["type"] == "tool_call"]
    chain_runs = [e for e in events if e["type"] == "chain_run"]
    errors = [e for e in events if e["type"] == "error"]
    toggles = [e for e in events if e["type"] == "server_toggle"]
    route_events = [e for e in events if e["type"] == "route_decision"]

    tool_stats: dict[str, dict[str, Any]] = {}
    for tc in tool_calls:
        name = tc["name"]
        if name not in tool_stats:
            tool_stats[name] = {
                "total": 0,
                "success": 0,
                "failed": 0,
                "durations": [],
            }
        tool_stats[name]["total"] += 1
        if tc["success"]:
            tool_stats[name]["success"] += 1
        else:
            tool_stats[name]["failed"] += 1
        tool_stats[name]["durations"].append(tc.get("duration_ms", 0))

    per_tool: dict[str, dict[str, Any]] = {}
    for name, stats in tool_stats.items():
        durations = stats.pop("durations", [])
        avg_ms = round(sum(durations) / len(durations), 2) if durations else 0.0
        per_tool[name] = {
            "total": stats["total"],
            "success": stats["success"],
            "failed": stats["failed"],
            "avg_duration_ms": avg_ms,
            "success_rate": round(stats["success"] / stats["total"] * 100, 1)
            if stats["total"]
            else 0.0,
        }

    chain_stats: dict[str, dict[str, Any]] = {}
    for cr in chain_runs:
        name = cr["name"]
        if name not in chain_stats:
            chain_stats[name] = {"total": 0, "success": 0, "failed": 0}
        chain_stats[name]["total"] += 1
        if cr["success"]:
            chain_stats[name]["success"] += 1
        else:
            chain_stats[name]["failed"] += 1

    route_outcomes = {"success": 0, "fallback": 0, "failed": 0}
    for event in route_events:
        outcome = str((event.get("metadata") or {}).get("outcome") or "failed")
        route_outcomes[outcome] = route_outcomes.get(outcome, 0) + 1

    time_span = round(events[-1]["timestamp"] - events[0]["timestamp"], 1)

    return {
        "total_events": len(events),
        "time_span_s": time_span,
        "tool_calls": {
            "total": len(tool_calls),
            "unique_tools": len(per_tool),
            "per_tool": per_tool,
        },
        "chain_runs": {
            "total": len(chain_runs),
            "unique_chains": len(chain_stats),
            "per_chain": chain_stats,
        },
        "errors": {
            "total": len(errors),
            "recent": errors[-10:],
        },
        "server_toggles": len(toggles),
        "routing": {
            "total": len(route_events),
            "success": route_outcomes.get("success", 0),
            "fallback": route_outcomes.get("fallback", 0),
            "failed": route_outcomes.get("failed", 0),
        },
        "summary": {
            "total_tool_calls": len(tool_calls),
            "total_chain_runs": len(chain_runs),
            "total_errors": len(errors),
            "overall_success_rate": round(
                sum(1 for tc in tool_calls if tc["success"]) / len(tool_calls) * 100,
                1,
            )
            if tool_calls
            else 0.0,
        },
    }


def status_overview() -> dict[str, Any]:
    import os

    from kater import __version__
    from kater.connect import source_is_configured
    from kater.profiles import all_tool_sources
    from kater.settings import load_settings

    settings = load_settings()
    enabled_count = 0
    disabled_count = 0
    configured_count = 0
    missing_count = 0

    for source in all_tool_sources():
        if source.transport == "native":
            continue
        if settings.is_server_enabled(source.name, default=True):
            enabled_count += 1
        else:
            disabled_count += 1
        if source_is_configured(source, settings):
            configured_count += 1
        else:
            missing_count += 1

    eval_data = eval_summary()
    try:
        from kater.control_plane.store import route_overview

        routing_overview = route_overview()
    except Exception as exc:
        _log.debug("control-plane overview unavailable: %s", exc)
        routing_overview = {
            "capabilities": 0,
            "candidates": 0,
            "active_candidates": 0,
            "decisions": 0,
        }

    return {
        "version": __version__,
        "profile": os.environ.get("KATER_PROFILE", "core"),
        "auth_mode": settings.auth.mode,
        "api_port": settings.api_port,
        "mcp_port": settings.mcp_port,
        "storage_backend": settings.storage_backend,
        "servers": {
            "total": enabled_count + disabled_count,
            "enabled": enabled_count,
            "disabled": disabled_count,
            "configured": configured_count,
            "missing_env": missing_count,
        },
        "routing": {
            **routing_overview,
            "events": eval_data["routing"],
        },
        "telemetry": {
            "total_events": eval_data["total_events"],
            "tool_calls": eval_data["summary"]["total_tool_calls"],
            "chain_runs": eval_data["summary"]["total_chain_runs"],
            "errors": eval_data["summary"]["total_errors"],
            "success_rate": eval_data["summary"]["overall_success_rate"],
        },
        "cors": settings.cors_origins,
        "rate_limit": settings.rate_limit_per_min,
    }
