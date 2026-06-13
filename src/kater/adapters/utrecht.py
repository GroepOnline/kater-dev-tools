from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UtrechtAdapterConfig:
    mcp_url: str | None
    repo_path: Path | None


def load_utrecht_config() -> UtrechtAdapterConfig:
    repo_path = os.environ.get("UTRECHT_REPO_PATH")
    return UtrechtAdapterConfig(
        mcp_url=os.environ.get("UTRECHT_MCP_URL"),
        repo_path=Path(repo_path).expanduser() if repo_path else None,
    )


def utrecht_status() -> dict[str, str | bool | None]:
    config = load_utrecht_config()
    repo_exists = config.repo_path.exists() if config.repo_path else False
    return {
        "mcp_url": config.mcp_url,
        "repo_path": str(config.repo_path) if config.repo_path else None,
        "repo_exists": repo_exists,
        "configured": bool(config.mcp_url or repo_exists),
    }
