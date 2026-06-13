from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from kater.chains import list_chains
from kater.doctor import parse_profiles, run_doctor
from kater.profiles import DEFAULT_PROFILE, list_profiles
from kater.registry import tools_for_profile

app = typer.Typer(help="Developer MCP gateway for profile-gated code-agent tools.")
profiles_app = typer.Typer(help="Inspecteer Kater toolprofielen.")
mcp_app = typer.Typer(help="Start de Kater MCP server.")
app.add_typer(profiles_app, name="profiles")
app.add_typer(mcp_app, name="mcp")


def _print_json(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2))


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
    report = run_doctor(
        profiles=parse_profiles(profiles),
        cursor_mcp_path=cursor_mcp,
        include_fix_plan=fix_plan or apply,
    )
    if json_output:
        _print_json(report.model_dump(mode="json"))
        return
    typer.echo(f"Profiles: {', '.join(report.profiles)}")
    typer.echo(f"Sources: {len(report.sources)}")
    typer.echo(f"Findings: {len(report.findings)}")
    for finding in report.findings:
        prefix = f"[{finding.severity}] {finding.code}"
        suffix = f" ({finding.source})" if finding.source else ""
        typer.echo(f"{prefix}{suffix}: {finding.message}")


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
        typer.echo(f"{chain.name}: {chain.description}")


@mcp_app.command("serve")
def mcp_serve_command(
    profile: Annotated[str, typer.Option("--profile", help="Profile to expose.")] = DEFAULT_PROFILE,
) -> None:
    """Start the optional MCP server."""
    from kater.mcp_server import serve

    serve(profile=profile)
