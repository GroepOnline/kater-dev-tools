from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from kater.profiles import DEFAULT_PROFILE, TOOL_SOURCES, list_profiles

KATER_DIR = ".kater"
KATER_CONFIG = "config.json"
KATER_ENV = ".env"


def init_project(
    project_dir: Path | None = None,
    profile: str = DEFAULT_PROFILE,
    force: bool = False,
) -> dict[str, Any]:
    project_dir = project_dir or Path.cwd()
    kater_dir = project_dir / KATER_DIR
    config_path = kater_dir / KATER_CONFIG
    env_path = kater_dir / KATER_ENV

    result: dict[str, Any] = {
        "created": [],
        "skipped": [],
        "kater_dir": str(kater_dir),
    }

    if kater_dir.exists() and not force:
        result["skipped"].append({"path": str(kater_dir), "reason": "Already exists. Use --force."})
        return result

    kater_dir.mkdir(parents=True, exist_ok=True)

    config = _render_kater_config(profile)
    config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    result["created"].append(str(config_path))

    env_content = _render_env_file(profile)
    env_path.write_text(env_content, encoding="utf-8")
    result["created"].append(str(env_path))

    _write_gitignore(kater_dir)
    result["created"].append(str(kater_dir / ".gitignore"))

    return result


def _render_kater_config(profile: str) -> dict[str, Any]:
    return {
        "version": 1,
        "default_profile": profile,
        "api_port": 9091,
        "mcp_port": 9090,
        "profiles": list_profiles(),
        "servers": [
            {
                "name": s.name,
                "transport": s.transport.value,
                "risk": s.risk.value,
                "profiles": sorted(s.profiles),
            }
            for s in TOOL_SOURCES
            if s.transport != "native"
        ],
    }


def _render_env_file(profile: str) -> str:
    lines: list[str] = [
        "# Kater environment — fill in your secrets.",
        "# This file is git-ignored by default.",
        "",
        f"KATER_PROFILE={profile}",
        "",
    ]
    seen: set[str] = set()
    for source in TOOL_SOURCES:
        if profile not in source.profiles and profile != "core":
            continue
        for var in source.env:
            if var not in seen:
                seen.add(var)
                lines.append(f"# {var}=")
    lines.append("")
    return "\n".join(lines)


def _write_gitignore(kater_dir: Path) -> None:
    (kater_dir / ".gitignore").write_text(".env\n", encoding="utf-8")


def load_project_config(project_dir: Path | None = None) -> dict[str, Any] | None:
    project_dir = project_dir or Path.cwd()
    config_path = project_dir / KATER_DIR / KATER_CONFIG
    if not config_path.exists():
        return None
    return json.loads(config_path.read_text(encoding="utf-8"))
