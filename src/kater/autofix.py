from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kater.doctor import FixAction
from kater.profiles import TOOL_SOURCES


def render_cursor_snippet(
    url: str = "http://127.0.0.1:9090/sse",
    profile: str = "core",
) -> dict[str, Any]:
    return {
        "mcpServers": {
            "kater": {
                "type": "sse",
                "url": url,
                "env": {"KATER_PROFILE": profile},
            }
        }
    }


def render_env_example(profiles: set[str]) -> str:
    lines: list[str] = [
        "# Kater environment variables",
        "# Copy to .env for local Docker Compose. Do not commit real secrets.",
        "",
        f"KATER_PROFILE={','.join(sorted(profiles))}",
        "",
        "# Public / tunnel (required before going live):",
        "# KATER_PUBLIC=1",
        "# KATER_AUTH_MODE=oauth",
        "# KATER_RATE_LIMIT=60",
        "",
    ]
    seen: set[str] = set()
    for source in TOOL_SOURCES:
        if not source.profiles.intersection(profiles):
            continue
        for var in source.env:
            if var not in seen:
                seen.add(var)
                lines.append(f"# {var}=<your-{source.name}-key>")
    lines.append("")
    return "\n".join(lines)


def apply_fix_actions(
    actions: list[FixAction],
    output_dir: Path | None = None,
    profile: str = "core",
) -> dict[str, Any]:
    output_dir = output_dir or Path.cwd()
    results: dict[str, Any] = {"applied": [], "skipped": [], "errors": []}
    for action in actions:
        target = output_dir / action.target
        try:
            if action.action == "render_cursor_snippet":
                target.parent.mkdir(parents=True, exist_ok=True)
                snippet = render_cursor_snippet(profile=profile)
                target.write_text(json.dumps(snippet, indent=2) + "\n", encoding="utf-8")
                results["applied"].append({"action": action.action, "target": str(target)})
            elif action.action == "render_env_example":
                profiles_set = {profile} if profile else {"core"}
                content = render_env_example(profiles_set)
                target.write_text(content, encoding="utf-8")
                results["applied"].append({"action": action.action, "target": str(target)})
            else:
                results["skipped"].append(
                    {"action": action.action, "reason": f"Unknown action: {action.action}"}
                )
        except (OSError, json.JSONDecodeError) as exc:
            results["errors"].append(
                {
                    "action": action.action,
                    "target": str(target),
                    "error": str(exc),
                }
            )
    return results
