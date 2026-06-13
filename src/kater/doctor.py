from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from kater.profiles import DEFAULT_PROFILE, RiskLevel, ToolSource, sources_for_profiles


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


def parse_profiles(value: str | None) -> set[str]:
    if not value:
        return {DEFAULT_PROFILE}
    return {part.strip() for part in value.split(",") if part.strip()} or {DEFAULT_PROFILE}


def load_cursor_mcp(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def run_doctor(
    *,
    profiles: set[str] | None = None,
    cursor_mcp_path: Path | None = None,
    include_fix_plan: bool = False,
) -> DoctorReport:
    selected_profiles = profiles or {DEFAULT_PROFILE}
    sources = sources_for_profiles(selected_profiles)
    findings = _find_missing_env(sources)
    findings.extend(_find_context_bloat(cursor_mcp_path=cursor_mcp_path, selected=sources))
    fix_actions = _build_fix_actions(findings) if include_fix_plan else []
    return DoctorReport(
        profiles=sorted(selected_profiles),
        sources=[source.model_dump(mode="json") for source in sources],
        findings=findings,
        fix_actions=fix_actions,
    )


def _find_missing_env(sources: list[ToolSource]) -> list[Finding]:
    findings: list[Finding] = []
    for source in sources:
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


def _find_context_bloat(
    *, cursor_mcp_path: Path | None, selected: list[ToolSource]
) -> list[Finding]:
    config = load_cursor_mcp(cursor_mcp_path)
    configured = set(config.get("mcpServers", {}).keys())
    selected_names = {source.name for source in selected}
    extra = sorted(configured - selected_names)
    findings: list[Finding] = []
    if len(configured) >= 4:
        findings.append(
            Finding(
                code="too_many_default_servers",
                severity="warning",
                message=f"Cursor config has {len(configured)} MCP servers enabled.",
                suggested_action="Use a Kater profile and expose one gateway server to agents.",
            )
        )
    for name in extra:
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
