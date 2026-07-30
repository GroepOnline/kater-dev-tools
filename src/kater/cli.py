from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

import typer

from kater.autofix import apply_fix_actions
from kater.chains import list_chains
from kater.doctor import parse_profiles, run_doctor
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
    apply_result = None
    if apply and yes and report.fix_actions:
        output_dir = Path.cwd()
        apply_result = apply_fix_actions(
            actions=report.fix_actions,
            output_dir=output_dir,
            profile=",".join(sorted(profiles_set)),
        )
    if json_output:
        payload = report.model_dump(mode="json")
        if apply_result:
            payload["apply_result"] = apply_result
        _print_json(payload)
        return
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
    proxy: Annotated[
        bool | None,
        typer.Option(
            "--proxy/--no-proxy",
            help="Force proxy on/off. Default: auto when adapter secrets are set.",
        ),
    ] = None,
) -> None:
    """Start Kater: REST API + MCP server + WebSocket in one process."""
    from kater.envfile import load_project_env, resolve_use_proxy

    load_project_env()
    os.environ["KATER_PROFILE"] = profile
    _prepare_public_bind_environment(host)
    use_proxy = resolve_use_proxy(profile=profile) if proxy is None else proxy

    if api_only:
        from kater.api import serve_api

        typer.echo(f"Kater API on http://{host}:{api_port}")
        serve_api(host, api_port)
        return

    if mcp_only:
        from kater.mcp_server import serve
        from kater.settings import load_settings

        load_settings().apply_credentials_to_env()
        typer.echo(
            f"Kater MCP on http://{host}:{mcp_port}/sse (proxy={'on' if use_proxy else 'off'})"
        )
        serve(profile=profile, host=host, port=mcp_port, use_proxy=use_proxy)
        return

    typer.echo(
        f"Kater unified: API :{api_port} + MCP :{mcp_port}/sse + WS :{ws_port} "
        f"(proxy={'on' if use_proxy else 'off'})"
    )
    from kater.serve import serve_unified
    from kater.settings import resolve_listen_config

    listen = resolve_listen_config(
        host=host,
        api_port=api_port,
        mcp_port=mcp_port,
        ws_port=ws_port,
    )
    serve_unified(profile=profile, listen=listen, use_proxy=use_proxy)


@app.command("up")
def up_command(
    profile: Annotated[str, typer.Option("--profile", help="Profile to expose.")] = "ops",
    api_port: Annotated[int, typer.Option("--api-port", help="REST API port.")] = 9091,
    mcp_port: Annotated[int, typer.Option("--mcp-port", help="MCP SSE port.")] = 9090,
    ws_port: Annotated[int, typer.Option("--ws-port", help="WebSocket port.")] = 9092,
    host: Annotated[str, typer.Option("--host", help="Bind address.")] = "127.0.0.1",
    force_init: Annotated[
        bool, typer.Option("--force-init", help="Overwrite .kater/ if it already exists.")
    ] = False,
) -> None:
    """Bootstrap local Kater and start the gateway (init + Cursor MCP + serve)."""
    from kater.envfile import ensure_cursor_mcp, load_project_env, resolve_use_proxy
    from kater.init import init_project

    root = Path.cwd()
    kater_dir = root / ".kater"
    if force_init or not (kater_dir / "config.json").exists():
        result = init_project(root, profile=profile, force=force_init)
        for path in result.get("created", []):
            typer.echo(f"  Created: {path}")
        for item in result.get("skipped", []):
            typer.echo(f"  Skipped: {item['path']} ({item['reason']})")
    else:
        cursor = ensure_cursor_mcp(root, mcp_url=f"http://{host}:{mcp_port}/sse")
        if cursor.get("created"):
            typer.echo(f"  Created: {cursor['path']}")
        elif cursor.get("updated"):
            typer.echo(f"  Updated: {cursor['path']}")

    loaded = load_project_env(root)
    for path in loaded:
        typer.echo(f"  Loaded env: {path}")

    use_proxy = resolve_use_proxy(profile=profile)
    typer.echo(
        f"Starting Kater ({profile}): dashboard http://{host}:{api_port} "
        f"| MCP http://{host}:{mcp_port}/sse | proxy={'on' if use_proxy else 'off'}"
    )
    if not use_proxy:
        typer.echo(
            "  Tip: put adapter keys in .kater/.env (e.g. LINEAR_API_KEY=...) "
            "to auto-enable proxy backends."
        )

    os.environ["KATER_PROFILE"] = profile
    _prepare_public_bind_environment(host)
    from kater.serve import serve_unified
    from kater.settings import resolve_listen_config

    listen = resolve_listen_config(
        host=host,
        api_port=api_port,
        mcp_port=mcp_port,
        ws_port=ws_port,
    )
    serve_unified(profile=profile, listen=listen, use_proxy=use_proxy)


# ── mcp serve (legacy alias) ───────────────────────────────────────


@mcp_app.command("serve")
def mcp_serve_command(
    profile: Annotated[str, typer.Option("--profile", help="Profile to expose.")] = DEFAULT_PROFILE,
) -> None:
    """Start the MCP SSE server (alias for `kater serve --mcp-only`)."""
    from kater.envfile import load_project_env, resolve_use_proxy
    from kater.mcp_server import serve
    from kater.settings import load_settings

    load_project_env()
    os.environ["KATER_PROFILE"] = profile
    load_settings().apply_credentials_to_env()
    serve(
        profile=profile,
        use_proxy=resolve_use_proxy(profile=profile),
    )


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


# ── pr control-plane (§3/§4/§6/§7) ───────────────────────────────


pr_app = typer.Typer(help="PR merge-readiness gate and merge (gh-backed).")
app.add_typer(pr_app, name="pr")


@pr_app.command("policy")
def pr_policy_command(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Show the resolved merge-gate policy."""
    from kater.pr_control import pr_policy_tool

    result = pr_policy_tool()
    if json_output:
        _print_json(result)
        return
    policy = result["policy"]
    typer.echo("Merge-gate policy:")
    for key, value in policy.items():
        typer.echo(f"  {key}: {value}")


@pr_app.command("list")
def pr_list_command(
    state: Annotated[str, typer.Option("--state", help="open|closed|all.")] = "open",
    limit: Annotated[int, typer.Option("--limit", help="Max PRs.")] = 30,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """List pull requests with merge-readiness summary."""
    from kater.pr_control import pr_list_tool

    result = pr_list_tool(state=state, limit=limit)
    if json_output:
        _print_json(result)
        return
    typer.echo(f"{result['count']} {state} PR(s):")
    for pr in result["pulls"]:
        verdict = (pr.get("gate") or {}).get("verdict", "?") if "gate" in pr else "?"
        typer.echo(f"  #{pr['number']} [{verdict}] {pr['title']}")


@pr_app.command("gate")
def pr_gate_command(
    number: Annotated[int, typer.Argument(help="PR number.")],
    expected_head_sha: Annotated[
        str, typer.Option("--expected-head", help="Pin the expected head SHA.")
    ] = "",
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Evaluate the deterministic merge gate for a PR."""
    from kater.pr_control import pr_gate_tool

    try:
        result = pr_gate_tool(number, expected_head_sha=expected_head_sha)
    except RuntimeError as exc:
        typer.echo(f"Gate failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if json_output:
        _print_json(result)
        return
    typer.echo(f"PR #{number}: {result['verdict']}")
    if result["reasons"]:
        typer.echo("  reasons: " + ", ".join(result["reasons"]))
    if expected_head_sha:
        match = result["details"].get("head_sha_matches")
        typer.echo(f"  expected head match: {match}")


@pr_app.command("merge")
def pr_merge_command(
    number: Annotated[int, typer.Argument(help="PR number.")],
    expected_head_sha: Annotated[
        str, typer.Option("--expected-head", help="Pin the expected head SHA (required).")
    ] = "",
    actor: Annotated[str, typer.Option("--actor", help="Actor label for the audit trail.")] = "",
) -> None:
    """Gate-then-merge a PR (squash). Requires PASS and pinned expected head."""
    from kater.pr_control import MergeRejected, pr_merge_tool

    try:
        result = pr_merge_tool(number, expected_head_sha=expected_head_sha, actor=actor)
    except MergeRejected as exc:
        typer.echo(f"Merge blocked: {exc}", err=True)
        raise typer.Exit(code=2) from exc
    except RuntimeError as exc:
        typer.echo(f"Merge failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"Merged PR #{result['pr_number']} (head {result['head_sha']}).")


# ── migrate ────────────────────────────────────────────────────────


migrate_app = typer.Typer(help="SQLite schema migrations.")
app.add_typer(migrate_app, name="migrate")


@migrate_app.command("status")
def migrate_status_command(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Show current schema version and pending migrations."""
    from kater.migrations import schema_status

    status = schema_status()
    if json_output:
        _print_json(status)
        return
    typer.echo(f"database: {status['database']}")
    typer.echo(f"current:  {status['current_version']} / latest {status['latest_version']}")
    typer.echo(f"dirty:    {status['dirty']}")
    pending = status["pending"]
    if not pending:
        typer.echo("pending:  none")
        return
    typer.echo(f"pending:  {len(pending)}")
    for item in pending:
        typer.echo(f"  {item['version']}: {item['name']}")


@migrate_app.command("apply")
def migrate_apply_command(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Report pending migrations without applying.")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """
    Apply pending SQLite schema migrations, or report them without applying when using --dry-run.
    """
    from kater.migrations import MigrationError, run_migrations

    try:
        results = run_migrations(dry_run=dry_run)
    except MigrationError as exc:
        typer.echo(f"Migration failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    payload = [{"version": r.version, "name": r.name, "status": r.status} for r in results]
    if json_output:
        _print_json({"dry_run": dry_run, "results": payload})
        return
    if not payload:
        typer.echo("No migrations registered.")
        return
    for item in payload:
        typer.echo(f"  {item['version']}: {item['name']} [{item['status']}]")


# ── backup ─────────────────────────────────────────────────────────


backup_app = typer.Typer(help="Backup and restore .kater state.")
app.add_typer(backup_app, name="backup")


@backup_app.command("create")
def backup_create_command(
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="Destination .tar.gz path or directory."),
    ] = None,
    no_secrets: Annotated[
        bool, typer.Option("--no-secrets", help="Omit oauth/.env and redact settings secrets.")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """
    Create a verifiable `.tar.gz` backup of the `.kater` state.

    Parameters:
        output (Path | None): Destination archive path or directory; uses the default destination
            when omitted.
        no_secrets (bool): Exclude OAuth and environment files and redact settings secrets when
            true.
    """
    from kater.backup import BackupError, create_backup

    try:
        result = create_backup(output, include_secrets=not no_secrets)
    except BackupError as exc:
        typer.echo(f"Backup failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    payload = {
        "path": str(result.path),
        "bytes": result.bytes,
        "files": list(result.files),
        "schema_version": result.schema_version,
        "include_secrets": result.include_secrets,
    }
    if json_output:
        _print_json(payload)
        return
    typer.echo(f"Wrote {result.path} ({result.bytes} bytes, {len(result.files)} files)")


@backup_app.command("inspect")
def backup_inspect_command(
    path: Annotated[Path, typer.Argument(help="Backup .tar.gz to inspect.")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """
    Validate a backup archive and display its manifest or inspection report.

    Parameters:
        path (Path): Backup archive to inspect.
        json_output (bool): Whether to output the inspection report as JSON.
    """
    from kater.backup import BackupError, inspect_backup

    try:
        report = inspect_backup(path)
    except BackupError as exc:
        typer.echo(f"Inspect failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    if json_output:
        _print_json(report)
        return
    typer.echo(f"path:            {report['path']}")
    typer.echo(f"ok:              {report['ok']}")
    typer.echo(f"bundle_version:  {report['bundle_version']}")
    typer.echo(f"kater_version:   {report['kater_version']}")
    typer.echo(f"schema_version:  {report['schema_version']}")
    typer.echo(f"include_secrets: {report['include_secrets']}")
    typer.echo(f"files:           {', '.join(entry['name'] for entry in report['files'])}")
    if report["missing"]:
        typer.echo(f"missing:         {', '.join(report['missing'])}")
    if report["unexpected"]:
        typer.echo(f"unexpected:      {', '.join(report['unexpected'])}")
    if report["mismatches"]:
        typer.echo(f"mismatches:      {', '.join(report['mismatches'])}")


@backup_app.command("restore")
def backup_restore_command(
    path: Annotated[Path, typer.Argument(help="Backup .tar.gz to restore.")],
    force: Annotated[
        bool, typer.Option("--force", help="Replace existing .kater (safety backup first).")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Restore `.kater` state from a backup bundle.

    Parameters:
        path (Path): Backup bundle to restore.
        force (bool): Whether to replace the existing `.kater` directory.
        json_output (bool): Whether to output the result as JSON.
    """
    from kater.backup import BackupError, restore_backup

    try:
        result = restore_backup(path, force=force)
    except BackupError as exc:
        typer.echo(f"Restore failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    payload = {
        "restored_files": list(result.restored_files),
        "schema_version": result.schema_version,
        "safety_backup": str(result.safety_backup) if result.safety_backup else None,
        "migrations_applied": list(result.migrations_applied),
    }
    if json_output:
        _print_json(payload)
        return
    typer.echo(
        f"Restored {len(result.restored_files)} file(s); schema version {result.schema_version}"
    )
    if result.safety_backup is not None:
        typer.echo(f"Safety backup: {result.safety_backup}")


# ── browser ────────────────────────────────────────────────────────


browser_app = typer.Typer(help="Native agent browser lane.")
app.add_typer(browser_app, name="browser")


@browser_app.command("providers")
def browser_providers_command(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Report which browser backends are available without starting one."""
    from kater.browser.tools import browser_providers_tool

    result = browser_providers_tool()
    if json_output:
        _print_json(result)
        return
    for info in result["providers"]:
        avail = "available" if info.get("available") else "unavailable"
        detail = info.get("detail") or ""
        typer.echo(f"  {info.get('kind')}: {avail}" + (f" - {detail}" if detail else ""))


@browser_app.command("sessions")
def browser_sessions_command(
    live: Annotated[bool, typer.Option("--live", help="Hide closed/failed sessions.")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """List browser sessions and lane statistics."""
    from kater.browser.tools import browser_sessions_tool

    result = browser_sessions_tool(live_only=live)
    if json_output:
        _print_json(result)
        return
    sessions = result["sessions"]
    typer.echo(f"{len(sessions)} session(s):")
    for session in sessions:
        typer.echo(
            f"  {session.get('session_id')} [{session.get('state')}] "
            f"{session.get('current_url') or '(no url)'}"
        )


@browser_app.command("open")
def browser_open_command(
    label: Annotated[str, typer.Option("--label", help="Human label for the session.")] = "",
    url: Annotated[str, typer.Option("--url", help="Navigate here after opening.")] = "",
    profile: Annotated[str, typer.Option("--profile", help="Owning Kater profile.")] = "core",
    width: Annotated[int, typer.Option("--width", help="Viewport width.")] = 1280,
    height: Annotated[int, typer.Option("--height", help="Viewport height.")] = 800,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Open a browser session and optionally navigate it to a URL.

    Parameters:
        label (str): Human-readable label for the session.
        url (str): URL to navigate to after opening the session.
        profile (str): Kater profile that owns the session.
        width (int): Browser viewport width in pixels.
        height (int): Browser viewport height in pixels.
        json_output (bool): Whether to output the result as JSON.
    """
    from kater.browser.tools import browser_act_tool, browser_open_tool

    kwargs: dict[str, Any] = {"profile": profile, "width": width, "height": height}
    if label:
        kwargs["label"] = label
    result = browser_open_tool(**kwargs)
    if result.get("ok") and url:
        session_id = result["session"]["session_id"]
        result["navigate"] = browser_act_tool(session_id=session_id, kind="navigate", url=url)
    if json_output:
        _print_json(result)
        return
    if not result.get("ok"):
        typer.echo(f"Open failed: {result.get('error')}", err=True)
        raise typer.Exit(code=1)
    session = result["session"]
    typer.echo(f"Opened {session['session_id']} [{session.get('state')}]")
    nav = result.get("navigate")
    if isinstance(nav, dict) and not nav.get("ok", True):
        typer.echo(f"Navigate failed: {nav.get('error')}", err=True)
        raise typer.Exit(code=1)


@browser_app.command("act")
def browser_act_command(
    session_id: Annotated[str, typer.Argument(help="Session id from browser open.")],
    kind: Annotated[str, typer.Option("--kind", help="Action kind (navigate, click, …).")],
    url: Annotated[str, typer.Option("--url", help="Target URL (navigate).")] = "",
    selector: Annotated[str, typer.Option("--selector", help="CSS selector.")] = "",
    text: Annotated[str, typer.Option("--text", help="Text to type.")] = "",
    key: Annotated[str, typer.Option("--key", help="Key to press.")] = "",
    value: Annotated[str, typer.Option("--value", help="Option value (select).")] = "",
    expression: Annotated[str, typer.Option("--expression", help="JS expression.")] = "",
    delta_y: Annotated[
        int | None, typer.Option("--delta-y", help="Vertical scroll delta in pixels.")
    ] = None,
    timeout_ms: Annotated[
        int | None, typer.Option("--timeout-ms", help="Per-action timeout override.")
    ] = None,
    full_page: Annotated[
        bool, typer.Option("--full-page", help="Full-page capture when kind=screenshot.")
    ] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """
    Run a browser action in an open session.

    Parameters:
        session_id (str): Identifier of the browser session.
        kind (str): Action to perform.
        url (str): Target URL for navigation actions.
        selector (str): CSS selector for element actions.
        text (str): Text to enter.
        key (str): Key to press.
        value (str): Option value for selection actions.
        expression (str): JavaScript expression to evaluate.
        delta_y (int | None): Vertical scroll distance in pixels.
        timeout_ms (int | None): Action timeout in milliseconds.
        full_page (bool): Whether screenshot actions should capture the full page.
        json_output (bool): Whether to output the result as JSON.

    Returns:
        None
    """
    from kater.browser.tools import browser_act_tool

    kwargs: dict[str, Any] = {"session_id": session_id, "kind": kind}
    if url:
        kwargs["url"] = url
    if selector:
        kwargs["selector"] = selector
    if text:
        kwargs["text"] = text
    if key:
        kwargs["key"] = key
    if value:
        kwargs["value"] = value
    if expression:
        kwargs["expression"] = expression
    if delta_y is not None:
        kwargs["delta_y"] = delta_y
    if timeout_ms is not None:
        kwargs["timeout_ms"] = timeout_ms
    if full_page:
        kwargs["full_page"] = True
    result = browser_act_tool(**kwargs)
    if json_output:
        _print_json(result)
        return
    if not result.get("ok", True):
        typer.echo(f"Act failed: {result.get('error')}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"{kind} ok" + (f" → {result.get('url')}" if result.get("url") else ""))


@browser_app.command("screenshot")
def browser_screenshot_command(
    session_id: Annotated[str, typer.Argument(help="Session id from browser open.")],
    full_page: Annotated[bool, typer.Option("--full-page", help="Capture the full page.")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """
    Capture a screenshot of the current browser page.

    Parameters:
        session_id (str): Identifier of the browser session.
        full_page (bool): Whether to capture the entire page.
        json_output (bool): Whether to output the result as JSON.

    Returns:
        None
    """
    from kater.browser.tools import browser_screenshot_tool

    result = browser_screenshot_tool(session_id=session_id, full_page=full_page)
    if json_output:
        _print_json(result)
        return
    if not result.get("ok", True):
        typer.echo(f"Screenshot failed: {result.get('error')}", err=True)
        raise typer.Exit(code=1)
    image = result.get("screenshot_b64") or result.get("image_base64") or ""
    typer.echo(f"Screenshot ok ({len(image)} base64 chars)")


@browser_app.command("close")
def browser_close_command(
    session_id: Annotated[
        str | None, typer.Argument(help="Session id to close (omit with --all).")
    ] = None,
    close_all: Annotated[bool, typer.Option("--all", help="Close every session.")] = False,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Close one browser session, or every session with --all."""
    from kater.browser.tools import browser_close_tool

    if not close_all and not session_id:
        typer.echo("Provide SESSION_ID or pass --all.", err=True)
        raise typer.Exit(code=2)
    kwargs: dict[str, Any] = {"all": True} if close_all else {"session_id": session_id}
    result = browser_close_tool(**kwargs)
    if json_output:
        _print_json(result)
        return
    if not result.get("ok"):
        typer.echo(f"Close failed: {result.get('error')}", err=True)
        raise typer.Exit(code=1)
    if close_all:
        typer.echo(f"Closed {result.get('closed', 0)} session(s)")
        return
    session = result.get("session") or {}
    typer.echo(f"Closed {session.get('session_id', session_id)}")


# ── automations ────────────────────────────────────────────────────


automations_app = typer.Typer(help="Scheduled automations (doctor, reap, prune, nudges).")
app.add_typer(automations_app, name="automations")


@automations_app.command("list")
def automations_list_command(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """List automations and seed defaults when the table is empty."""
    from kater.automations import get_engine

    engine = get_engine()
    engine.ensure_defaults()
    items = [item.to_dict() for item in engine.list()]
    if json_output:
        _print_json({"automations": items, "total": len(items)})
        return
    typer.echo(f"{len(items)} automation(s):")
    for item in items:
        state = "on" if item["enabled"] else "off"
        last = item.get("last_status") or "-"
        typer.echo(
            f"  {item['id']} [{state}] {item['kind']} every {item['schedule_seconds']}s last={last}"
        )


@automations_app.command("run")
def automations_run_command(
    automation_id: Annotated[str, typer.Argument(help="Automation id to run.")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Force one automation run now."""
    from kater.automations import get_engine

    try:
        result = get_engine().run_now(automation_id)
    except KeyError:
        typer.echo(f"Automation not found: {automation_id}", err=True)
        raise typer.Exit(code=1) from None
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from None
    payload = result.to_dict()
    if json_output:
        _print_json(payload)
        return
    if payload["status"] != "ok":
        typer.echo(f"Run failed: {payload.get('error')}", err=True)
        raise typer.Exit(code=1)
    typer.echo(f"Ran {payload['id']} ({payload['kind']}) ok")


@automations_app.command("enable")
def automations_enable_command(
    automation_id: Annotated[str, typer.Argument(help="Automation id to enable.")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """
    Enable the specified automation.

    Parameters:
        automation_id (str): Identifier of the automation to enable.
        json_output (bool): Whether to output the enabled automation as JSON.

    Raises:
        typer.Exit: If the automation does not exist.
    """
    from kater.automations import get_engine

    automation = get_engine().set_enabled(automation_id, True)
    if automation is None:
        typer.echo(f"Automation not found: {automation_id}", err=True)
        raise typer.Exit(code=1)
    if json_output:
        _print_json(automation.to_dict())
        return
    typer.echo(f"Enabled {automation.id}")


@automations_app.command("disable")
def automations_disable_command(
    automation_id: Annotated[str, typer.Argument(help="Automation id to disable.")],
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Disable an automation."""
    from kater.automations import get_engine

    automation = get_engine().set_enabled(automation_id, False)
    if automation is None:
        typer.echo(f"Automation not found: {automation_id}", err=True)
        raise typer.Exit(code=1)
    if json_output:
        _print_json(automation.to_dict())
        return
    typer.echo(f"Disabled {automation.id}")


# ── computer ───────────────────────────────────────────────────────


computer_app = typer.Typer(help="Computer guest connector (HTTP capability lane).")
app.add_typer(computer_app, name="computer")


@computer_app.command("status")
def computer_status_command(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """Show whether the Computer connector is configured and active."""
    from kater.capabilities.wiring import computer_status, ensure_computer_connector

    ensure_computer_connector()
    payload = computer_status()
    if json_output:
        _print_json(payload)
        return
    state = "active" if payload["active"] else ("configured" if payload["configured"] else "off")
    typer.echo(
        f"Computer [{state}] host={payload['base_url_host'] or '-'} "
        f"profile={payload['profile']} capabilities={payload['capability_count']}"
    )


@computer_app.command("capabilities")
def computer_capabilities_command(
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """List Computer tools exposed by the active connector."""
    from kater.capabilities.wiring import ensure_computer_connector

    connector = ensure_computer_connector()
    tools = connector.list_tools() if connector is not None else []
    payload = {"tools": tools, "total": len(tools)}
    if json_output:
        _print_json(payload)
        return
    if not tools:
        typer.echo("No Computer capabilities (connector not configured).")
        return
    typer.echo(f"{len(tools)} capability(ies):")
    for tool in tools:
        typer.echo(f"  {tool.get('name')}")


@computer_app.command("invoke")
def computer_invoke_command(
    capability_id: Annotated[str, typer.Argument(help="Capability id to invoke.")],
    arg: Annotated[
        list[str] | None,
        typer.Option("--arg", help="Argument as key=value (repeatable)."),
    ] = None,
    args_json: Annotated[
        str,
        typer.Option("--args", help="JSON object of invocation arguments."),
    ] = "",
    args_file: Annotated[
        Path | None,
        typer.Option("--args-file", help="Path to a JSON object of arguments."),
    ] = None,
    json_output: Annotated[bool, typer.Option("--json", help="Output as JSON.")] = False,
) -> None:
    """
    Invoke a Computer capability with the provided arguments.

    Parameters:
        capability_id (str): Identifier of the capability to invoke.
        arg (list[str] | None): Additional arguments in `key=value` format.
        args_json (str): Invocation arguments as a JSON object.
        args_file (Path | None): Path to a file containing invocation arguments as a JSON object.
        json_output (bool): Whether to output the result as JSON.

    Returns:
        None
    """
    from kater.capabilities.wiring import ensure_computer_connector

    connector = ensure_computer_connector()
    if connector is None:
        typer.echo("Computer connector is not configured (set KATER_COMPUTER_URL+TOKEN).", err=True)
        raise typer.Exit(code=1)

    arguments: dict[str, Any] = {}
    if args_file is not None:
        try:
            loaded = json.loads(args_file.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            typer.echo(f"Failed to read --args-file: {exc}", err=True)
            raise typer.Exit(code=2) from exc
        if not isinstance(loaded, dict):
            typer.echo("--args-file must contain a JSON object.", err=True)
            raise typer.Exit(code=2)
        arguments.update(loaded)
    if args_json.strip():
        try:
            loaded = json.loads(args_json)
        except json.JSONDecodeError as exc:
            typer.echo(f"Invalid --args JSON: {exc}", err=True)
            raise typer.Exit(code=2) from exc
        if not isinstance(loaded, dict):
            typer.echo("--args must be a JSON object.", err=True)
            raise typer.Exit(code=2)
        arguments.update(loaded)
    for item in arg or ():
        if "=" not in item:
            typer.echo(f"--arg must be key=value, got {item!r}", err=True)
            raise typer.Exit(code=2)
        key, value = item.split("=", 1)
        if not key:
            typer.echo(f"--arg must be key=value, got {item!r}", err=True)
            raise typer.Exit(code=2)
        arguments[key] = value

    result = connector.call(capability_id, arguments)
    if json_output:
        _print_json(result)
        return
    status = result.get("status", "unknown")
    typer.echo(f"{capability_id}: {status}")
    if status != "succeeded":
        error = result.get("error") or {}
        code = error.get("code") if isinstance(error, dict) else None
        if code:
            typer.echo(f"  error: {code}", err=True)
        raise typer.Exit(code=1)
