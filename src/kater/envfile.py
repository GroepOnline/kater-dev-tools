"""Project-local environment bootstrap for Kater.

``kater init`` writes ``.kater/.env``. Until this module existed those secrets
were never applied on ``kater serve``, so proxy backends stayed dark unless
the operator exported them in the shell.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

_ENV_LINE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$")


def _strip_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse a dotenv file into a dict. Invalid lines are skipped."""
    if not path.is_file():
        return {}
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        match = _ENV_LINE.match(text)
        if not match:
            continue
        result[match.group(1)] = _strip_value(match.group(2))
    return result


def load_project_env(project_dir: Path | None = None) -> list[str]:
    """Load project dotenv files into ``os.environ`` without overriding.

    Precedence (highest first): already-set process env, then ``.kater/.env``,
    then project ``.env``. Returns paths that contributed at least one key.
    """
    root = (project_dir or Path.cwd()).resolve()
    # Apply .kater first so its keys win via setdefault; then root .env fills gaps.
    ordered = [root / ".kater" / ".env", root / ".env"]
    contributed: list[str] = []
    for path in ordered:
        parsed = parse_env_file(path)
        if not parsed:
            continue
        wrote = False
        for key, value in parsed.items():
            if key not in os.environ:
                os.environ[key] = value
                wrote = True
        if wrote:
            contributed.append(str(path))
    return contributed


def resolve_use_proxy(*, profile: str | None = None) -> bool:
    """Decide whether to start the backend proxy.

    Explicit ``KATER_PROXY`` wins. When unset, auto-enable if at least one
    non-native adapter for the active profile has all required env vars set.
    """
    raw = os.environ.get("KATER_PROXY")
    if raw is not None and raw.strip() != "":
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    from kater.doctor import parse_profiles
    from kater.profiles import Transport, all_tool_sources

    active = profile or os.environ.get("KATER_PROFILE", "core")
    profile_names = parse_profiles(active)
    for source in all_tool_sources():
        if source.transport == Transport.NATIVE:
            continue
        # Auto-on is credential-driven: ignore no-env catalog entries so a
        # bare `core` profile does not spawn every free stdio backend.
        if not source.env:
            continue
        if not profile_names.intersection(source.profiles):
            # Mirror proxy start: profile "core" still admits everything.
            if "core" not in profile_names:
                continue
        if all(os.environ.get(v) for v in source.env):
            return True
    return False


def ensure_cursor_mcp(
    project_dir: Path | None = None,
    *,
    mcp_url: str = "http://127.0.0.1:9090/sse",
) -> dict[str, Any]:
    """Ensure project ``.cursor/mcp.json`` points Cursor at the local gateway.

    Merges with an existing file and never removes other MCP server entries.
    """
    root = (project_dir or Path.cwd()).resolve()
    cursor_dir = root / ".cursor"
    path = cursor_dir / "mcp.json"
    cursor_dir.mkdir(parents=True, exist_ok=True)

    existing: dict[str, Any] = {}
    created = False
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except (json.JSONDecodeError, OSError):
            existing = {}
    else:
        created = True

    servers = existing.get("mcpServers")
    if not isinstance(servers, dict):
        servers = {}
        existing["mcpServers"] = servers

    entry = servers.get("kater")
    desired = {"type": "sse", "url": mcp_url}
    changed = entry != desired
    servers["kater"] = desired
    if created or changed:
        path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")

    return {
        "path": str(path),
        "created": created,
        "updated": changed and not created,
        "url": mcp_url,
    }
