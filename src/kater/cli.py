from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

import typer

from kater.autofix import apply_fix_actions
from kater.chains import list_chains
from kater.doctor import DoctorReport, parse_profiles, run_doctor
from kater.profiles import DEFAULT_PROFILE, all_tool_sources, get_source, list_profiles
from kater.registry import tools_for_profile

app = typer.Typer(help="Developer MCP gateway — one unified tool surface for code agents.")
profiles_app = typer.Typer(help="Inspect profiles.")
mcp_app = typer.Typer(help="MCP server management.")
chain_app = typer.Typer(help="Tool chain execution.")
tunnel_app = typer.Typer(help="Tunnel management (Cloudflare / Tailscale).")
app.add_typer(profiles_app, name="profiles")
app.add_typer(mcp_app, name="mcp")
app.add_typer(chain_app, name="chain")
app.add_typer(tunnel_app, name="tunnel")


def _print_json(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


def _prepare_public_bind_environment(host: str) -> None:
    """Apply secure env defaults before settings are loaded for public binds."""
    normalized = host.strip().lower()
    os.environ["KATER_HOST"] = host
    from kater.settings import invalidate_settings_cache

    invalidate_settings_cache()
    if normalized in {"127.0.0.1", "localhost", "::1"}:
        return

    os.environ.setdefault("KATER_PUBLIC", "1")
    os.environ.setdefault("KATER_AUTH_MODE", "oauth")
    os.environ.setdefault("KATER_RATE_LIMIT", "60")
    os.environ.setdefault("KATER_CORS_ORIGINS", "https://kater.example.com")

    auth_mode = os.environ.get("KATER_AUTH_MODE", "").strip().lower()
    if auth_mode == "none":
        raise typer.BadParameter(
            "public bind requires authentication; set KATER_AUTH_MODE=oauth or apikey"
        )

    rate_limit = os.environ.get("KATER_RATE_LIMIT", "").strip()
    if rate_limit == "0":
        raise typer.BadParameter("public bind requires KATER_RATE_LIMIT greater than 0")

    cors_origins = [
        origin.strip()
        for origin in os.environ.get("KATER_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    if "*" in cors_origins:
        raise typer.BadParameter("public bind must not use wildcard KATER_CORS_ORIGINS")


# ── doctor ─────────────────────────────────────────────────────────


def _apply_doctor_fixes(
    apply: bool, yes: bool, report: DoctorReport, profiles_set: set[str]
) -> dict[str, Any] | None:
    if apply and yes and report.fix_actions:
        output_dir = Path.cwd()
        return apply_fix_actions(
            actions=report.fix_actions,
            output_dir=output_dir,
            profile=",".join(sorted(profiles_set)),
        )
    return None


def _print_doctor_text_report(report: DoctorReport, apply_result: dict[str, Any] | None) -> None:
    typer.echo(f"Profiles: {', '.join(report.profiles)}")
    typer.echo(f"Sources: {len(report.sources)}")
    typer.echo(f"Findings: {len(report.findings)}")
    for finding in report.findings:
        prefix = f"[{finding.severity}] {finding.code}"
        suffix = f" ({finding.source})" if finding.source else ""
        typer.echo(f"{prefix}{suffix}: {finding.message}")
    if apply_result:
        for item in apply_result.get("applied", []):
            typer.echo(f"  Applied: {item['action']} -> {item['target']}")
        for item in apply_result.get("errors", []):
            typer.echo(f"  Error: {item['action']} -> {item['target']}: {item['error']}")


@app.command("doctor")
def doctor_command(
    profiles: Annotated[
        str,
        typer.Option("--profile", help="Comma-separated profiles to inspect."),
    ] = DEFAULT_PROFILE,
    cursor_mcp: Annotated[
        Path | None,
        typer.Option("--cursor-mcp", help="Optional Cursor mcp.json to inspect."),
    ] = None,
    fix_plan: Annotated[
        bool,
        typer.Option("--fix-plan", help="Include proposed safe fix actions."),
    ] = False,
    apply: Annotated[
        bool,
        typer.Option("--apply", help="Apply supported Kater-owned fixes."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Confirm non-interactive apply mode."),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Run context and MCP configuration diagnostics."""
    if apply and not yes:
        typer.echo("Error: --apply requires --yes.", err=True)
        raise typer.Exit(code=2)
    profiles_set = parse_profiles(profiles)
    report = run_doctor(
        profiles=profiles_set,
        cursor_mcp_path=cursor_mcp,
        include_fix_plan=fix_plan or apply,
    )
    apply_result = _apply_doctor_fixes(apply, yes, report, profiles_set)
    if json_output:
        payload = report.model_dump(mode="json")
        if apply_result:
            payload["apply_result"] = apply_result
        _print_json(payload)
        return
    _print_doctor_text_report(report, apply_result)


# ── profiles ───────────────────────────────────────────────────────


@profiles_app.callback(invoke_without_command=True)
def profiles_command(
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """List available Kater profiles."""
    profiles = list_profiles()
    if json_output:
        _print_json({"profiles": profiles})
        return
    for profile in profiles:
        typer.echo(profile)


# ── tools ──────────────────────────────────────────────────────────


@app.command("tools")
def tools_command(
    profile: Annotated[
        str, typer.Option("--profile", help="Profile to inspect.")
    ] = DEFAULT_PROFILE,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """List native Kater tools exposed for a profile."""
    tools = tools_for_profile(profile)
    payload = {
        "profile": profile,
        "tools": [tool.model_dump(exclude={"handler"}) for tool in tools],
    }
    if json_output:
        _print_json(payload)
        return
    for tool in tools:
        typer.echo(f"{tool.name}: {tool.description}")


# ── chains ─────────────────────────────────────────────────────────


@app.command("chains")
def chains_command(
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Only show chains for this profile."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """List predefined tool chains."""
    chains = list_chains(profile)
    payload = {"chains": [chain.model_dump(mode="json") for chain in chains]}
    if json_output:
        _print_json(payload)
        return
    for chain in chains:
        typer.echo(f"{chain.name}: {chain.description} ({len(chain.steps)} steps)")


@chain_app.command("run")
def chain_run_command(
    chain_name: Annotated[str, typer.Argument(help="Chain name to run.")],
    profile: Annotated[
        str, typer.Option("--profile", help="Profile for the chain.")
    ] = DEFAULT_PROFILE,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Execute a predefined tool chain (outputs steps for an agent to follow)."""
    chains = list_chains(profile)
    chain = None
    for c in chains:
        if c.name == chain_name:
            chain = c
            break
    if chain is None:
        from kater.telemetry import record_chain_run

        record_chain_run(chain_name, steps=0, success=False, profile=profile)
        typer.echo(f"Error: chain '{chain_name}' not found for profile '{profile}'.", err=True)
        raise typer.Exit(code=1)
    result: dict[str, Any] = {
        "chain": chain.name,
        "description": chain.description,
        "profile": profile,
        "steps": [
            {"step": i + 1, "tool": step.tool, "reason": step.reason}
            for i, step in enumerate(chain.steps)
        ],
    }
    from kater.telemetry import record_chain_run

    record_chain_run(chain.name, steps=len(chain.steps), profile=profile)
    if json_output:
        _print_json(result)
        return
    typer.echo(f"Chain: {chain.name}")
    typer.echo(f"Profile: {profile}")
    typer.echo("Steps:")
    for step in result["steps"]:
        typer.echo(f"  {step['step']}. {step['tool']} — {step['reason']}")


# ── config ─────────────────────────────────────────────────────────


@app.command("config")
def config_command(
    profile: Annotated[
        str, typer.Option("--profile", help="Profile to render config for.")
    ] = DEFAULT_PROFILE,
    format: Annotated[
        str, typer.Option("--format", help="Output format: json, cursor, or claude.")
    ] = "json",
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Render MCP configuration for a profile."""
    from kater.adapters.external import render_profile_config

    config = render_profile_config(profile)
    if json_output or format in ("json", "cursor", "claude"):
        _print_json(config)
        return
    typer.echo(f"Profile: {profile}")
    for name, cfg in config.get("mcpServers", {}).items():
        typer.echo(f"  {name}: {cfg.get('type', 'unknown')}")


# ── adapters ───────────────────────────────────────────────────────


@app.command("adapters")
def adapters_command(
    profile: Annotated[
        str, typer.Option("--profile", help="Profile to inspect adapters for.")
    ] = DEFAULT_PROFILE,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Scan configured external MCP adapters for a profile."""
    from kater.adapters.external import scan_adapters

    inventory = scan_adapters({profile})
    payload: dict[str, Any] = {
        "profile": profile,
        "adapters": [
            {
                "name": a.source.name,
                "transport": a.source.transport.value,
                "configured": a.configured,
                "missing_env": a.missing_env,
                "risk": a.source.risk.value,
            }
            for a in inventory.sources
        ],
        "total": len(inventory.sources),
        "configured": sum(1 for a in inventory.sources if a.configured),
    }
    if json_output:
        _print_json(payload)
        return
    msg = f"Profile: {profile} — {payload['configured']}/{payload['total']} adapters configured"
    typer.echo(msg)
    for a in payload["adapters"]:
        status = "+" if a["configured"] else "-"
        typer.echo(f"  [{status}] {a['name']} ({a['transport']})")


# ── init ───────────────────────────────────────────────────────────


@app.command("init")
def init_command(
    profile: Annotated[
        str, typer.Option("--profile", help="Default profile for this project.")
    ] = DEFAULT_PROFILE,
    force: Annotated[
        bool, typer.Option("--force", help="Overwrite existing .kater/ config.")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Initialize .kater/ as the single source of truth for MCP config."""
    from kater.init import init_project

    result = init_project(Path.cwd(), profile=profile, force=force)
    if json_output:
        _print_json(result)
        return
    for path in result.get("created", []):
        typer.echo(f"  Created: {path}")
    for item in result.get("skipped", []):
        typer.echo(f"  Skipped: {item['path']} ({item['reason']})")


# ── mcp list / status ──────────────────────────────────────────────


@mcp_app.command("list")
def mcp_list_command(
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Filter by profile."),
    ] = None,
    configured_only: Annotated[
        bool,
        typer.Option("--configured", help="Only show configured servers."),
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """List all known MCP servers in the catalog."""
    from kater.ansi import Table, error, success

    servers = []
    for source in all_tool_sources():
        if source.transport == "native":
            continue
        if profile and profile not in source.profiles:
            continue
        env_ok = all(os.environ.get(v) for v in source.env)
        if configured_only and not env_ok:
            continue
        servers.append(
            {
                "name": source.name,
                "transport": source.transport.value,
                "risk": source.risk.value,
                "profiles": sorted(source.profiles),
                "env_configured": env_ok,
                "env_required": source.env,
                "homepage": source.homepage,
            }
        )
    if json_output:
        _print_json({"total": len(servers), "servers": servers})
        return
    table = Table(
        ["Name", "Transport", "Risk", "Configured", "Profiles"],
        f"MCP Servers ({len(servers)})",
    )
    for s in servers:
        status = success("yes") if s["env_configured"] else error("no")
        profiles = s.get("profiles")
        table.add_row(
            str(s["name"]),
            str(s["transport"]),
            str(s["risk"]),
            status,
            ", ".join(profiles) if isinstance(profiles, list) else "",
        )
    typer.echo(table.render())


@mcp_app.command("status")
def mcp_status_command(
    name: Annotated[str, typer.Argument(help="Server name to check.")],
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Check the configuration status of a specific MCP server."""
    source = get_source(name)
    if not source:
        typer.echo(f"Error: unknown server '{name}'.", err=True)
        raise typer.Exit(code=1)
    env_present = {v: bool(os.environ.get(v)) for v in source.env}
    all_ok = all(env_present.values()) if env_present else True
    payload = {
        "name": source.name,
        "description": source.description,
        "transport": source.transport.value,
        "risk": source.risk.value,
        "profiles": sorted(source.profiles),
        "configured": all_ok,
        "env": env_present,
        "homepage": source.homepage,
        "mcp": source.mcp.model_dump() if source.mcp else None,
    }
    if json_output:
        _print_json(payload)
        return
    typer.echo(f"Server: {source.name}")
    typer.echo(f"  Transport: {source.transport.value}")
    typer.echo(f"  Risk: {source.risk.value}")
    typer.echo(f"  Configured: {'yes' if all_ok else 'no'}")
    for var, present in env_present.items():
        typer.echo(f"    {var}: {'set' if present else 'MISSING'}")


# ── serve (unified) ────────────────────────────────────────────────


@app.command("serve")
def serve_command(
    profile: Annotated[str, typer.Option("--profile", help="Profile to expose.")] = DEFAULT_PROFILE,
    api_port: Annotated[int, typer.Option("--api-port", help="REST API port.")] = 9091,
    mcp_port: Annotated[int, typer.Option("--mcp-port", help="MCP SSE port.")] = 9090,
    ws_port: Annotated[int, typer.Option("--ws-port", help="WebSocket port.")] = 9092,
    host: Annotated[str, typer.Option("--host", help="Bind address.")] = "127.0.0.1",
    api_only: Annotated[bool, typer.Option("--api-only", help="Run only the API.")] = False,
    mcp_only: Annotated[bool, typer.Option("--mcp-only", help="Run only the MCP server.")] = False,
) -> None:
    """Start Kater: REST API + MCP server + WebSocket in one process."""
    os.environ["KATER_PROFILE"] = profile
    _prepare_public_bind_environment(host)

    if api_only:
        from kater.api import serve_api

        typer.echo(f"Kater API on http://{host}:{api_port}")
        serve_api(host, api_port)
        return

    if mcp_only:
        from kater.mcp_server import serve

        typer.echo(f"Kater MCP on http://{host}:{mcp_port}/sse")
        serve(profile=profile, host=host, port=mcp_port)
        return

    typer.echo(f"Kater unified: API :{api_port} + MCP :{mcp_port}/sse + WS :{ws_port}")
    from kater.serve import serve_unified
    from kater.settings import resolve_listen_config

    listen = resolve_listen_config(
        host=host,
        api_port=api_port,
        mcp_port=mcp_port,
        ws_port=ws_port,
    )
    serve_unified(profile=profile, listen=listen)


# ── mcp serve (legacy alias) ───────────────────────────────────────


@mcp_app.command("serve")
def mcp_serve_command(
    profile: Annotated[str, typer.Option("--profile", help="Profile to expose.")] = DEFAULT_PROFILE,
) -> None:
    """Start the MCP SSE server (alias for `kater serve --mcp-only`)."""
    from kater.mcp_server import serve

    serve(profile=profile)


# ── version ────────────────────────────────────────────────────────


@app.command("version")
def version_command() -> None:
    """Show the Kater version."""
    from kater import __version__

    typer.echo(__version__)


# ── enable / disable / toggle ─────────────────────────────────────


def _toggle_server(name: str, action: str, json_output: bool) -> None:
    from kater.settings import load_settings, save_settings

    source = get_source(name)
    if not source:
        typer.echo(f"Error: unknown server '{name}'.", err=True)
        raise typer.Exit(code=1)
    settings = load_settings()
    if action == "enable":
        settings.set_server_enabled(name, True)
    elif action == "disable":
        settings.set_server_enabled(name, False)
    elif action == "toggle":
        current = settings.is_server_enabled(name, default=True)
        settings.set_server_enabled(name, not current)
    save_settings(settings)
    enabled = settings.is_server_enabled(name, default=True)
    if json_output:
        _print_json({"name": name, "action": action, "enabled": enabled})
        return
    state = "enabled" if enabled else "disabled"
    typer.echo(f"  {name}: {state}")


@app.command("enable")
def enable_command(
    name: Annotated[str, typer.Argument(help="Server name to enable.")],
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Enable an MCP server."""
    _toggle_server(name, "enable", json_output)


@app.command("disable")
def disable_command(
    name: Annotated[str, typer.Argument(help="Server name to disable.")],
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Disable an MCP server."""
    _toggle_server(name, "disable", json_output)


@app.command("toggle")
def toggle_command(
    name: Annotated[str, typer.Argument(help="Server name to toggle.")],
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Toggle an MCP server on/off."""
    _toggle_server(name, "toggle", json_output)


# ── deploy ─────────────────────────────────────────────────────────


deploy_app = typer.Typer(help="Generate deployment configs.")
app.add_typer(deploy_app, name="deploy")


@deploy_app.callback(invoke_without_command=True)
def deploy_list_command(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """List available deployment formats."""
    if ctx.invoked_subcommand is not None:
        return
    from kater.deploy import list_deploy_formats

    formats = list_deploy_formats()
    if json_output:
        _print_json({"formats": formats})
        return
    typer.echo("Deployment formats:")
    for f in formats:
        typer.echo(f"  {f['name']:<14} {f['description']}")


@deploy_app.command("render")
def deploy_render_command(
    fmt: Annotated[str, typer.Argument(help="Deployment format.")],
    profile: Annotated[str, typer.Option("--profile", help="Profile.")] = DEFAULT_PROFILE,
    domain: Annotated[
        str, typer.Option("--domain", help="Domain for cloudflare/tunnel.")
    ] = "kater.example.com",
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Render a deployment config for the chosen format."""
    from kater.deploy import render_deploy

    kwargs: dict[str, str] = {}
    if fmt == "cloudflare":
        kwargs["domain"] = domain
    config = render_deploy(fmt, profile=profile, **kwargs)
    _print_json(config)


# ── auth ───────────────────────────────────────────────────────────


auth_app = typer.Typer(help="Manage authentication settings.")
app.add_typer(auth_app, name="auth")


@auth_app.callback(invoke_without_command=True)
def auth_status_command(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Show current auth configuration."""
    if ctx.invoked_subcommand is not None:
        return
    from kater.settings import load_settings

    settings = load_settings()
    payload = settings.auth.model_dump()
    if json_output:
        _print_json(payload)
        return
    typer.echo(f"Auth mode: {payload['mode']}")
    if payload.get("api_keys"):
        typer.echo(f"  API keys: {len(payload['api_keys'])} configured")
    if payload.get("oauth_issuer"):
        typer.echo(f"  OAuth issuer: {payload['oauth_issuer']}")


@auth_app.command("set")
def auth_set_command(
    mode: Annotated[str, typer.Argument(help="Auth mode: none, apikey, or oauth.")],
    key: Annotated[str | None, typer.Option("--key", help="API key to add.")] = None,
    issuer: Annotated[str | None, typer.Option("--issuer", help="OAuth issuer URL.")] = None,
    audience: Annotated[str | None, typer.Option("--audience", help="OAuth audience.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Configure authentication."""
    from kater.settings import AuthConfig, load_settings, save_settings

    if mode not in ("none", "apikey", "oauth"):
        typer.echo("Error: mode must be none, apikey, or oauth.", err=True)
        raise typer.Exit(code=1)
    settings = load_settings()
    api_keys = list(settings.auth.api_keys) if mode == "apikey" else []
    if key and mode == "apikey":
        if key not in api_keys:
            api_keys.append(key)
    settings.auth = AuthConfig(
        mode=mode,
        api_keys=api_keys,
        oauth_issuer=issuer,
        oauth_audience=audience,
    )
    save_settings(settings)
    payload = settings.auth.model_dump()
    if json_output:
        _print_json(payload)
        return
    typer.echo(f"Auth mode set to: {mode}")
    if api_keys:
        typer.echo(f"  API keys: {len(api_keys)}")


# ── settings ───────────────────────────────────────────────────────


@app.command("settings")
def settings_command(
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Show all Kater settings."""
    from kater.settings import load_settings

    settings = load_settings()
    if json_output:
        _print_json(settings.to_dict())
        return
    typer.echo(f"Profile: {settings.default_profile}")
    typer.echo(f"Auth: {settings.auth.mode}")
    typer.echo(f"CORS: {settings.cors_origins}")
    typer.echo(f"Rate limit: {settings.rate_limit_per_min}/min")
    enabled = [n for n, o in settings.server_overrides.items() if o.enabled]
    disabled = [n for n, o in settings.server_overrides.items() if not o.enabled]
    if disabled:
        typer.echo(f"Disabled servers: {', '.join(disabled)}")
    if enabled:
        typer.echo(f"Explicitly enabled: {', '.join(enabled)}")


# ── status / telemetry / evals ─────────────────────────────────────


@app.command("status")
def status_command(
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Live overview of this Kater instance."""
    from kater.ansi import banner, kv_grid
    from kater.telemetry import status_overview

    data = status_overview()
    if json_output:
        _print_json(data)
        return
    typer.echo(banner(f"Kater v{data['version']}", "Developer MCP Gateway"))
    s = data["servers"]
    t = data["telemetry"]
    items = [
        ("Profile", data["profile"]),
        ("Auth", data["auth_mode"]),
        ("Storage", data["storage_backend"]),
        ("API port", str(data["api_port"])),
        ("MCP port", str(data["mcp_port"])),
        ("Servers", f"{s['enabled']}/{s['total']} enabled ({s['configured']} configured)"),
        ("Events", f"{t['total_events']} total ({t['tool_calls']} calls, {t['errors']} errors)"),
        ("Success", f"{t['success_rate']}%"),
        ("Rate limit", f"{data['rate_limit']}/min" if data["rate_limit"] else "unlimited"),
    ]
    typer.echo(kv_grid(items))


@app.command("telemetry")
def telemetry_command(
    limit: Annotated[int, typer.Option("--limit", help="Only show last N events.")] = 0,
    event_type: Annotated[str | None, typer.Option("--type", help="Filter by event type.")] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """View raw telemetry events."""
    from kater.ansi import Table, dim, error, success
    from kater.telemetry import load_events

    events = load_events(limit=limit)
    if event_type:
        events = [e for e in events if e["type"] == event_type]
    if json_output:
        _print_json({"total": len(events), "events": events})
        return
    if not events:
        typer.echo(dim("No telemetry events."))
        return
    table = Table(["#", "Type", "Name", "Status", "Duration", "Profile"], "Telemetry")
    for i, e in enumerate(events, 1):
        ok = e.get("success", True)
        status = success("ok") if ok else error("fail")
        dur = f"{e.get('duration_ms', 0):.1f}ms"
        table.add_row(
            str(i),
            e["type"],
            e["name"],
            status,
            dur,
            e.get("profile") or "-",
        )
    typer.echo(table.render())


@app.command("evals")
def evals_command(
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Aggregated eval metrics from telemetry."""
    from kater.ansi import Table, dim, error, success
    from kater.telemetry import eval_summary

    data = eval_summary()
    if json_output:
        _print_json(data)
        return
    if data["total_events"] == 0:
        typer.echo(dim("No telemetry data yet."))
        return
    summary = data["summary"]
    typer.echo(f"Evals — {data['total_events']} events")
    rate = summary["overall_success_rate"]
    if rate >= 90:
        rate_str = success(f"{rate}%")
    elif rate < 50:
        rate_str = error(f"{rate}%")
    else:
        rate_str = f"{rate}%"
    typer.echo(f"  Success rate: {rate_str}")
    typer.echo(f"  Tool calls: {summary['total_tool_calls']}")
    typer.echo(f"  Chain runs: {summary['total_chain_runs']}")
    typer.echo(f"  Errors: {summary['total_errors']}")

    if data["tool_calls"]["per_tool"]:
        table = Table(["Tool", "Calls", "Success", "Failed", "Rate", "Avg ms"], "Tool Performance")
        for name, stats in sorted(
            data["tool_calls"]["per_tool"].items(),
            key=lambda x: x[1]["total"],
            reverse=True,
        ):
            rate_str = f"{stats['success_rate']}%"
            rate_str = success(rate_str) if stats["success_rate"] >= 90 else error(rate_str)
            table.add_row(
                name,
                str(stats["total"]),
                str(stats["success"]),
                str(stats["failed"]),
                rate_str,
                f"{stats['avg_duration_ms']:.1f}",
            )
        typer.echo(table.render())

    if data["chain_runs"]["per_chain"]:
        table = Table(["Chain", "Runs", "Success", "Failed"], "Chain Performance")
        for name, stats in data["chain_runs"]["per_chain"].items():
            table.add_row(name, str(stats["total"]), str(stats["success"]), str(stats["failed"]))
        typer.echo(table.render())


@app.command("telemetry-clear")
def telemetry_clear_command(
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Clear all telemetry data."""
    from kater.telemetry import clear_events

    count = clear_events()
    if json_output:
        _print_json({"cleared": count})
        return
    typer.echo(f"Cleared {count} events")


# ── tunnel ─────────────────────────────────────────────────────────


@tunnel_app.callback(invoke_without_command=True)
def tunnel_status_command(
    ctx: typer.Context,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Show tunnel status for Cloudflare and Tailscale."""
    if ctx.invoked_subcommand is not None:
        return
    from kater.ansi import kv_grid
    from kater.tunnel import tunnel_overview

    data = tunnel_overview()
    if json_output:
        _print_json(data)
        return
    cf = data["cloudflare"]
    ts = data["tailscale"]
    typer.echo("Tunnel Status:")
    items = [
        ("Cloudflare", "installed" if cf.get("installed") else "not installed"),
        ("  Running", "yes" if cf.get("running") else "no"),
        ("  URL", data["client_configs"]["cloudflare_url"]),
        ("Tailscale", "installed" if ts.get("installed") else "not installed"),
        ("  Connected", "yes" if ts.get("connected") else "no"),
        ("  Funnel", "yes" if ts.get("funnel") else "no"),
    ]
    typer.echo(kv_grid(items))


@tunnel_app.command("start")
def tunnel_start_command(
    provider: Annotated[
        str,
        typer.Option("--provider", "-p", help="cloudflare or tailscale"),
    ] = "cloudflare",
    domain: Annotated[str, typer.Option("--domain", help="Domain for Cloudflare tunnel.")] = "",
    port: Annotated[int, typer.Option("--port", help="Port for Tailscale Funnel.")] = 9090,
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Start a tunnel to expose Kater publicly."""
    from kater.tunnel import start_cloudflared, start_tailscale_funnel

    if provider == "cloudflare":
        resolved = domain or os.environ.get("KATER_DOMAIN") or None
        info = start_cloudflared(domain=resolved)
    elif provider == "tailscale":
        info = start_tailscale_funnel(port=port)
    else:
        typer.echo(f"Error: unknown provider '{provider}'. Use cloudflare or tailscale.", err=True)
        raise typer.Exit(code=1)

    if json_output:
        _print_json(info.to_dict())
        return
    if info.error:
        typer.echo(f"Error: {info.error}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Tunnel started: {info.url}")


@tunnel_app.command("stop")
def tunnel_stop_command(
    provider: Annotated[
        str,
        typer.Option("--provider", "-p", help="cloudflare or tailscale"),
    ] = "cloudflare",
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Stop a running tunnel."""
    from kater.tunnel import stop_cloudflared, stop_tailscale_funnel

    if provider == "cloudflare":
        stopped = stop_cloudflared()
    elif provider == "tailscale":
        stopped = stop_tailscale_funnel()
    else:
        typer.echo(f"Error: unknown provider '{provider}'.", err=True)
        raise typer.Exit(code=1)

    if json_output:
        _print_json({"stopped": stopped, "provider": provider})
        return
    typer.echo(f"{'Stopped' if stopped else 'Failed to stop'} {provider} tunnel")


@tunnel_app.command("config")
def tunnel_config_command(
    provider: Annotated[
        str,
        typer.Option("--provider", "-p", help="cloudflare or tailscale"),
    ] = "cloudflare",
    domain: Annotated[str, typer.Option("--domain", help="Domain for Cloudflare.")] = "",
    json_output: Annotated[bool, typer.Option("--json", help="Output als JSON.")] = False,
) -> None:
    """Generate tunnel configuration."""
    if provider == "cloudflare":
        from kater.tunnel import generate_cloudflare_config

        resolved = domain or os.environ.get("KATER_DOMAIN", "kater.example.com")
        config = generate_cloudflare_config(domain=resolved)
        if json_output:
            _print_json({"provider": "cloudflare", "config": config})
            return
        typer.echo(config)
    elif provider == "tailscale":
        from kater.tunnel import generate_tailscale_funnel_cmd

        cmd = generate_tailscale_funnel_cmd()
        if json_output:
            _print_json({"provider": "tailscale", "command": cmd})
            return
        typer.echo(" ".join(cmd))
    else:
        typer.echo("Error: unknown provider.", err=True)
        raise typer.Exit(code=1)


# ── interactive ────────────────────────────────────────────────────


@app.command("interactive")
def interactive_command(
    profile: Annotated[str, typer.Option("--profile", help="Starting profile.")] = DEFAULT_PROFILE,
    refresh: Annotated[float, typer.Option("--refresh", help="Refresh interval in seconds.")] = 3.0,
) -> None:
    """Live interactive dashboard in the terminal."""
    from kater.interactive import interactive_loop

    interactive_loop(profile=profile, refresh_interval=refresh)
