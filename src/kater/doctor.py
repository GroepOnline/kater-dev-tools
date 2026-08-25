from __future__ import annotations

import json
import os
import socket
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from kater.profiles import (
    DEFAULT_PROFILE,
    RiskLevel,
    ToolSource,
    Transport,
    all_tool_sources,
    sources_for_profiles,
)

_GATEWAY_SERVER_NAMES = frozenset({"kater"})


class Finding(BaseModel):
    code: str
    severity: str
    message: str
    source: str | None = None
    suggested_action: str | None = None


class FixAction(BaseModel):
    action: str
    target: str
    description: str
    reversible: bool = True


class DoctorReport(BaseModel):
    profiles: list[str]
    sources: list[dict[str, Any]]
    findings: list[Finding] = Field(default_factory=list)
    fix_actions: list[FixAction] = Field(default_factory=list)
    github_identity: dict[str, Any] | None = None


def parse_profiles(value: str | None) -> set[str]:
    if not value:
        return {DEFAULT_PROFILE}
    return {part.strip() for part in value.split(",") if part.strip()} or {DEFAULT_PROFILE}


def load_cursor_mcp(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, ValueError, OSError):
        return {}
    return data if isinstance(data, dict) else {}


def _catalog_source_names() -> set[str]:
    return {source.name for source in all_tool_sources()}


def _mcp_server_entries(config: dict[str, Any]) -> dict[str, Any]:
    servers = config.get("mcpServers", {})
    return servers if isinstance(servers, dict) else {}


def _default_port(scheme: str) -> int:
    return 443 if scheme == "https" else 80


def is_gateway_server(name: str, entry: Any) -> bool:
    """Return True when a Cursor MCP entry points at the Kater gateway."""
    if name in _GATEWAY_SERVER_NAMES:
        return True
    if not isinstance(entry, dict):
        return False
    if entry.get("type") != "sse":
        return False
    url = str(entry.get("url", "")).strip()
    if not url:
        return False
    kater_url = os.environ.get("KATER_URL", "http://127.0.0.1:9090/sse").strip()
    if url == kater_url:
        return True
    if not url.endswith("/sse"):
        return False
    parsed = urlparse(url)
    if parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
        return False
    # Same loopback host alone is not enough: a direct satellite on another
    # port (e.g. http://127.0.0.1:8080/sse) must stay non-gateway.
    kater_parsed = urlparse(kater_url)
    entry_port = parsed.port or _default_port(parsed.scheme)
    kater_port = kater_parsed.port or _default_port(kater_parsed.scheme)
    return entry_port == kater_port


def resolve_cursor_mcp(path: Path | None) -> Path | None:
    if path is not None:
        return path if path.exists() else None
    candidates = [Path.cwd() / ".cursor" / "mcp.json", Path.home() / ".cursor" / "mcp.json"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def run_doctor(
    *,
    profiles: set[str] | None = None,
    cursor_mcp_path: Path | None = None,
    include_fix_plan: bool = False,
) -> DoctorReport:
    selected_profiles = profiles or {DEFAULT_PROFILE}
    sources = sources_for_profiles(selected_profiles)
    effective_mcp_path = resolve_cursor_mcp(cursor_mcp_path)
    findings = _find_missing_env(sources)
    findings.extend(_adapter_config_check(selected_profiles))
    findings.extend(_connector_health_check(selected_profiles))
    findings.extend(_find_context_bloat(cursor_mcp_path=effective_mcp_path, selected=sources))
    findings.extend(_security_check())
    findings.extend(_browser_lane_check())
    fix_actions = _build_fix_actions(findings) if include_fix_plan else []
    from kater.github_transport import github_token_identity

    return DoctorReport(
        profiles=sorted(selected_profiles),
        sources=[source.model_dump(mode="json") for source in sources],
        findings=findings,
        fix_actions=fix_actions,
        github_identity=github_token_identity(),
    )


def _source_expected_enabled(source: ToolSource) -> bool:
    """Match proxy eligibility: HIGH-risk adapters stay optional unless enabled."""
    from kater.settings import load_settings

    if source.transport is Transport.NATIVE:
        return False
    settings = load_settings()
    enabled_default = not (settings.high_risk_default_disabled and source.risk == RiskLevel.HIGH)
    return settings.is_server_enabled(source.name, default=enabled_default)


def _find_missing_env(sources: list[ToolSource]) -> list[Finding]:
    findings: list[Finding] = []
    for source in sources:
        if not _source_expected_enabled(source):
            continue
        missing = [name for name in source.env if not os.environ.get(name)]
        if missing:
            findings.append(
                Finding(
                    code="missing_env",
                    severity="warning",
                    source=source.name,
                    message=f"{source.name} is selected but missing env: {', '.join(missing)}",
                    suggested_action=(
                        "Set the env vars or remove this profile for the current task."
                    ),
                )
            )
    return findings


def _adapter_config_check(selected_profiles: set[str]) -> list[Finding]:
    from kater.adapters.external import scan_adapters

    findings: list[Finding] = []
    inventory = scan_adapters(profiles=selected_profiles)
    for adapter in inventory.sources:
        if not adapter.configured and adapter.missing_env:
            findings.append(
                Finding(
                    code="adapter_not_configured",
                    severity="info",
                    source=adapter.source.name,
                    message=(
                        f"{adapter.source.name} ({adapter.source.transport}) not configured. "
                        f"Set: {', '.join(adapter.missing_env)}"
                    ),
                    suggested_action=(
                        f"Set {', '.join(adapter.missing_env)} to enable this adapter."
                    ),
                )
            )
        elif adapter.configured:
            findings.append(
                Finding(
                    code="adapter_ready",
                    severity="info",
                    source=adapter.source.name,
                    message=f"{adapter.source.name} ({adapter.source.transport}) configured.",
                    suggested_action="Use kater config --profile ... to generate the MCP config.",
                )
            )
    return findings


def _connector_health_check(selected_profiles: set[str]) -> list[Finding]:
    """Recompute connector-catalog health. Disabled / out-of-scope is not broken."""
    try:
        from kater.connectors.health import evaluate_health
        from kater.connectors.models import HealthState
        from kater.connectors.seed import seed_builtin_connectors
        from kater.connectors.store import list_connectors_with_errors
    except Exception:
        return []

    try:
        seed_builtin_connectors()
        records, record_errors = list_connectors_with_errors()
    except Exception:
        return []

    findings: list[Finding] = [
        Finding(
            code="connector_invalid",
            severity="warning",
            source=error.connector_id,
            message=f"Persisted connector row is invalid: {error}",
            suggested_action="Repair or re-register only the invalid connector row.",
        )
        for error in record_errors
    ]
    for record in records:
        if record.profiles and not record.profiles.intersection(selected_profiles):
            continue
        applicable_profiles = sorted(record.profiles.intersection(selected_profiles))
        profile = applicable_profiles[0] if applicable_profiles else None
        health = evaluate_health(record, profile=profile)
        if record.metadata.get("unsupported_runtime") is True:
            code, severity = "connector_unsupported", "info"
            message = f"{record.id} is unsupported on this runtime."
        elif record.metadata.get("scope") == "out_of_scope":
            code, severity = "connector_out_of_scope", "info"
            message = f"{record.id} is out of scope and stays disabled."
        elif health.state is HealthState.HEALTHY:
            if record.transport.kind in {"http", "sse"}:
                code, severity = "connector_configured", "info"
                message = f"{record.id} connector is configured; live reachability was not probed."
            else:
                code, severity = "connector_ready", "info"
                message = f"{record.id} connector is healthy."
        elif health.state is HealthState.DISABLED:
            code, severity = "connector_disabled", "info"
            message = f"{record.id} connector is disabled."
        elif health.state is HealthState.AUTH_MISSING:
            code, severity = "connector_auth_missing", "warning"
            message = f"{record.id} is enabled but missing auth refs: {health.detail}"
        elif health.state is HealthState.UNAVAILABLE:
            code, severity = "connector_unavailable", "warning"
            message = f"{record.id} is unavailable: {health.detail}"
        elif health.state is HealthState.DEGRADED:
            code, severity = "connector_degraded", "warning"
            message = f"{record.id} is degraded: {health.detail}"
        elif health.state is HealthState.POLICY_BLOCKED:
            code, severity = "connector_policy_blocked", "info"
            message = f"{record.id} is blocked for the selected profile."
        elif health.state is HealthState.UNSUPPORTED:
            code, severity = "connector_unsupported", "info"
            message = f"{record.id} is unsupported: {health.detail}"
        else:
            code, severity = "connector_health", "info"
            message = f"{record.id} health is {health.state.value}."
        findings.append(
            Finding(
                code=code,
                severity=severity,
                source=record.id,
                message=message,
                suggested_action=None,
            )
        )
    return findings


def _find_context_bloat(
    *, cursor_mcp_path: Path | None, selected: list[ToolSource]
) -> list[Finding]:
    config = load_cursor_mcp(cursor_mcp_path)
    entries = _mcp_server_entries(config)
    configured = set(entries.keys())
    catalog_names = _catalog_source_names()
    gateway_names = {name for name, entry in entries.items() if is_gateway_server(name, entry)}
    non_gateway = configured - gateway_names
    proxyable_outside = sorted(name for name in non_gateway if name in catalog_names)
    satellite_names = sorted(name for name in non_gateway if name not in catalog_names)
    findings: list[Finding] = []

    if gateway_names:
        if len(proxyable_outside) >= 3:
            findings.append(
                Finding(
                    code="too_many_default_servers",
                    severity="warning",
                    message=(
                        f"Cursor config exposes {len(proxyable_outside)} profile-gated MCP "
                        f"servers directly alongside the Kater gateway."
                    ),
                    suggested_action=(
                        "Route catalog MCPs through Kater profiles instead of registering "
                        "them directly in Cursor."
                    ),
                )
            )
    elif len(configured) >= 4:
        findings.append(
            Finding(
                code="too_many_default_servers",
                severity="warning",
                message=f"Cursor config has {len(configured)} MCP servers enabled.",
                suggested_action="Use a Kater profile and expose one gateway server to agents.",
            )
        )

    for name in proxyable_outside:
        findings.append(
            Finding(
                code="server_outside_profile",
                severity="info",
                source=name,
                message=f"{name} is configured but not selected by the active Kater profile.",
                suggested_action=(
                    "Move it behind a profile or keep it only in a task-specific config."
                ),
            )
        )

    for name in satellite_names:
        findings.append(
            Finding(
                code="satellite_server",
                severity="info",
                source=name,
                message=(
                    f"{name} is a direct MCP server outside the Kater catalog "
                    "(no profile adapter yet)."
                ),
                suggested_action=(
                    "Keep it direct until a Kater adapter exists, or register it via "
                    "KATER_EXTENSIONS_MODULE."
                ),
            )
        )

    for source in selected:
        if source.risk == RiskLevel.HIGH and source.name in configured:
            findings.append(
                Finding(
                    code="high_risk_direct_server",
                    severity="warning",
                    source=source.name,
                    message=f"{source.name} has write-capable or broad account tools.",
                    suggested_action="Expose it only through an explicit task profile.",
                )
            )
    return findings


def _browser_expected() -> bool:
    from kater.settings import _env_truthy

    if _env_truthy("KATER_BROWSER_ENABLE"):
        return True
    if os.environ.get("KATER_BROWSER_CDP_URL", "").strip():
        return True
    if os.environ.get("KATER_BROWSER_STEEL_URL", "").strip():
        return True
    return False


def _browser_lane_check() -> list[Finding]:
    """Surface native browser provider readiness without launching a browser."""
    from kater.browser.providers import probe_providers

    findings: list[Finding] = []
    providers = probe_providers()
    available = [info for info in providers if info.available]
    if available:
        kinds = ", ".join(info.kind.value for info in available)
        findings.append(
            Finding(
                code="browser_lane_ready",
                severity="info",
                source="browser",
                message=f"Native browser lane providers available: {kinds}.",
                suggested_action=(
                    "Use kater_browser_open / kater browser open, or open the Browser view."
                ),
            )
        )
        return findings
    if _browser_expected():
        findings.append(
            Finding(
                code="browser_lane_unavailable",
                severity="info",
                source="browser",
                message=(
                    "A native browser provider was expected but none is available "
                    "(Playwright/Chromium, KATER_BROWSER_CDP_URL, or KATER_BROWSER_STEEL_URL)."
                ),
                suggested_action=("uv sync --extra browser && playwright install chromium"),
            )
        )
        return findings
    company_control = socket.gethostname() in {"chef-control-az-01", "chef-kater-shadow"}
    message = "Native Kater browser is unsupported on this runtime."
    if company_control:
        message += " Company-control browse uses the ChefGroep browser MCP, not Playwright."
    findings.append(
        Finding(
            code="browser_lane_unsupported",
            severity="info",
            source="browser",
            message=message,
            suggested_action=(
                "Leave kater[browser] uninstalled here, or set KATER_BROWSER_CDP_URL / "
                "KATER_BROWSER_ENABLE if this host should drive a browser."
            ),
        )
    )
    return findings


def _security_check() -> list[Finding]:
    from kater.settings import _is_public_deploy, load_settings

    findings: list[Finding] = []
    settings = load_settings()
    host = os.environ.get("KATER_HOST", settings.host)
    is_public = _is_public_deploy(host)

    if not is_public:
        return findings

    if settings.auth.mode == "none":
        findings.append(
            Finding(
                code="public_without_auth",
                severity="error",
                message=(
                    "Kater is marked public (KATER_PUBLIC=1 or non-loopback host) "
                    "but auth mode is 'none'."
                ),
                suggested_action=(
                    "Set KATER_AUTH_MODE=oauth (ChatGPT) or apikey (Cursor/agents) "
                    "before exposing via tunnel or public IP."
                ),
            )
        )

    if settings.auth.mode == "apikey" and not settings.auth.api_keys:
        findings.append(
            Finding(
                code="public_apikey_missing",
                severity="error",
                message="Public deployment uses apikey auth but no KATER_API_KEY is set.",
                suggested_action="Set KATER_API_KEY or KATER_API_KEYS before going live.",
            )
        )

    if settings.rate_limit_per_min <= 0:
        findings.append(
            Finding(
                code="public_no_rate_limit",
                severity="warning",
                message="Public deployment has rate limiting disabled.",
                suggested_action="Set KATER_RATE_LIMIT=60 (or higher) for production.",
            )
        )

    if "*" in settings.cors_origins:
        findings.append(
            Finding(
                code="public_cors_wildcard",
                severity="warning",
                message="CORS allows any origin on a public deployment.",
                suggested_action=("Set KATER_CORS_ORIGINS to your dashboard origin only."),
            )
        )

    if is_public and settings.auth.mode == "oauth":
        allow_dynamic_registration = os.environ.get(
            "KATER_ALLOW_DYNAMIC_REGISTRATION", ""
        ).strip().lower() in {"1", "true", "yes", "on"}
        registration_token_set = bool(os.environ.get("KATER_REGISTRATION_TOKEN"))
        if allow_dynamic_registration and not registration_token_set:
            findings.append(
                Finding(
                    code="public_oauth_registration_token_missing",
                    severity="error",
                    message=(
                        "Dynamic OAuth registration is enabled but "
                        "KATER_REGISTRATION_TOKEN is not set, so /register will stay "
                        "disabled in public mode."
                    ),
                    suggested_action=(
                        "Set KATER_REGISTRATION_TOKEN and pass it as "
                        "X-Registration-Token, or remove KATER_ALLOW_DYNAMIC_REGISTRATION."
                    ),
                )
            )
        elif registration_token_set and not allow_dynamic_registration:
            findings.append(
                Finding(
                    code="public_oauth_registration_disabled",
                    severity="info",
                    message=(
                        "KATER_REGISTRATION_TOKEN is set, but dynamic OAuth "
                        "registration is disabled in public mode."
                    ),
                    suggested_action=(
                        "Set KATER_ALLOW_DYNAMIC_REGISTRATION=1 only if you need "
                        "runtime client registration."
                    ),
                )
            )
        if not os.environ.get("KATER_ADMIN_KEY"):
            findings.append(
                Finding(
                    code="public_no_admin_key",
                    severity="info",
                    message=("KATER_ADMIN_KEY is not set; public settings mutations are disabled."),
                    suggested_action=(
                        "Set KATER_ADMIN_KEY when the dashboard or API must change "
                        "settings in public mode."
                    ),
                )
            )
        if not os.environ.get("KATER_CONNECT_PUBLIC_BASE_URL", "").strip():
            findings.append(
                Finding(
                    code="public_connect_base_url_missing",
                    severity="info",
                    message=(
                        "KATER_CONNECT_PUBLIC_BASE_URL is unset; public Catalog "
                        "Connect will not trust Host / X-Forwarded-Host for redirects."
                    ),
                    suggested_action=(
                        "Set KATER_CONNECT_PUBLIC_BASE_URL=https://<canonical-host> "
                        "if you need Connect at all; HTTPS only."
                    ),
                )
            )
        findings.append(
            Finding(
                code="public_oauth_ready",
                severity="info",
                message="OAuth auth enabled — compatible with ChatGPT Remote MCP.",
                suggested_action="Use https://<your-domain>/sse as the MCP server URL.",
            )
        )

    return findings


def _build_fix_actions(findings: list[Finding]) -> list[FixAction]:
    actions: list[FixAction] = []
    if any(finding.code == "too_many_default_servers" for finding in findings):
        actions.append(
            FixAction(
                action="render_cursor_snippet",
                target=".cursor/mcp.kater.json",
                description="Render a minimal Cursor MCP snippet pointing to the Kater gateway.",
            )
        )
    if any(finding.code == "missing_env" for finding in findings):
        actions.append(
            FixAction(
                action="render_env_example",
                target=".env.kater.example",
                description="Render an env example for the selected profile.",
            )
        )
    return actions
