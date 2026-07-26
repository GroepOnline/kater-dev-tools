"""Built-in automation kinds executed by the engine."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from kater.adapters.external import scan_adapters
from kater.browser.session import get_manager
from kater.doctor import run_doctor
from kater.proxy import get_proxy
from kater.storage import prune_all
from kater.telemetry import TelemetryEvent, record_event

KindHandler = Callable[[dict[str, Any]], dict[str, Any]]

KNOWN_KINDS = frozenset(
    {
        "doctor_watch",
        "browser_reap",
        "proxy_heal",
        "telemetry_prune",
        "credential_nudge",
    }
)


def run_doctor_watch(config: dict[str, Any]) -> dict[str, Any]:
    profile = str(config.get("profile") or "core")
    started = time.perf_counter()
    report = run_doctor(profiles={profile})
    duration_ms = (time.perf_counter() - started) * 1000.0
    findings = list(report.findings)
    warnings = sum(1 for f in findings if getattr(f, "severity", "") == "warning")
    errors = sum(1 for f in findings if getattr(f, "severity", "") == "error")
    record_event(
        TelemetryEvent(
            type="automation",
            name="doctor_watch",
            success=errors == 0,
            duration_ms=duration_ms,
            profile=profile,
            metadata={
                "findings": len(findings),
                "warnings": warnings,
                "errors": errors,
            },
        )
    )
    return {
        "profile": profile,
        "findings": len(findings),
        "warnings": warnings,
        "errors": errors,
    }


def run_browser_reap(config: dict[str, Any]) -> dict[str, Any]:
    del config
    closed = get_manager().reap_expired()
    return {"closed": int(closed)}


def run_proxy_heal(config: dict[str, Any]) -> dict[str, Any]:
    del config
    proxy = get_proxy()
    if not proxy.started:
        return {"healed": 0, "skipped": "proxy_not_started"}
    for method_name in ("restart_failed", "heal_backends", "heal"):
        method = getattr(proxy, method_name, None)
        if not callable(method):
            continue
        result = method()
        if isinstance(result, dict):
            return {"healed": result.get("healed", result), "method": method_name}
        return {"healed": result, "method": method_name}
    # No restart API on ProxyManager yet — succeed as a no-op.
    unhealthy = [
        name for name, ok in proxy.health_check().items() if not ok
    ]
    return {"healed": 0, "skipped": "no_heal_api", "unhealthy": unhealthy}


def run_telemetry_prune(config: dict[str, Any]) -> dict[str, Any]:
    del config
    removed = prune_all()
    return {"removed": int(removed)}


def run_credential_nudge(config: dict[str, Any]) -> dict[str, Any]:
    profile = str(config.get("profile") or "core")
    inventory = scan_adapters(profiles={profile})
    missing: list[dict[str, Any]] = []
    for adapter in inventory.sources:
        if adapter.missing_env:
            missing.append(
                {
                    "server": adapter.source.name,
                    "missing_env": list(adapter.missing_env),
                }
            )
    record_event(
        TelemetryEvent(
            type="status",
            name="credential_nudge",
            success=True,
            profile=profile,
            metadata={
                "missing_count": len(missing),
                "servers": [item["server"] for item in missing],
            },
        )
    )
    return {"profile": profile, "missing_count": len(missing), "servers": missing}


HANDLERS: dict[str, KindHandler] = {
    "doctor_watch": run_doctor_watch,
    "browser_reap": run_browser_reap,
    "proxy_heal": run_proxy_heal,
    "telemetry_prune": run_telemetry_prune,
    "credential_nudge": run_credential_nudge,
}


def run_kind(kind: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
    handler = HANDLERS.get(kind)
    if handler is None:
        raise ValueError(f"unknown automation kind: {kind}")
    return handler(dict(config or {}))
