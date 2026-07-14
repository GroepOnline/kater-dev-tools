from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

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
    try:
        from kater.websocket import broadcast_event

        broadcast_event(event.to_dict())
    except Exception as exc:
        _log.debug("telemetry broadcast failed: %s", exc)


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
        if all(os.environ.get(v) for v in source.env):
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