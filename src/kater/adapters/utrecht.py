from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


def utrecht_pipeline_status() -> dict[str, Any]:
    config = load_utrecht_config()
    if config.repo_path and config.repo_path.exists():
        pipelines_dir = config.repo_path / "pipelines"
        if pipelines_dir.exists():
            artifacts = [
                str(p.relative_to(config.repo_path))
                for p in pipelines_dir.rglob("*")
                if p.is_file()
            ]
            return {
                "configured": True,
                "pipeline_artifacts": artifacts,
                "artifact_count": len(artifacts),
            }
        return {"configured": True, "pipeline_artifacts": [], "artifact_count": 0}
    return {"configured": False, "pipeline_artifacts": [], "artifact_count": 0}


def utrecht_agent_manifest() -> dict[str, Any]:
    config = load_utrecht_config()
    result: dict[str, Any] = {
        "configured": bool(config.mcp_url),
        "mcp_url": config.mcp_url,
        "reachable": False,
        "tools": [],
    }
    if config.mcp_url:
        try:
            resp = subprocess.run(
                ["curl", "-sS", "-o", "-", "-w", "%{http_code}", config.mcp_url],
                capture_output=True,
                text=True,
                timeout=5,
            )
            result["reachable"] = resp.returncode == 0
            result["http_status"] = resp.stdout.strip() if resp.returncode == 0 else None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            result["reachable"] = False
    return result
