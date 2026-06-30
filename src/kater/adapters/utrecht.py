from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PRIVATE_TEXT_PATTERNS = (
    re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
    re.compile(r"tskey-[a-z0-9-]+", re.IGNORECASE),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)
FORBIDDEN_NODE_KEYS = frozenset(
    {
        "ip",
        "ipv4",
        "ipv6",
        "tailscale_ip",
        "tailscale_ips",
        "ssh",
        "ssh_user",
        "ssh_config",
        "user",
        "username",
        "token",
        "secret",
        "private_key",
        "key",
        "endpoint",
        "url",
    }
)
SAFE_NODE_KEYS = frozenset(
    {
        "hostname",
        "role",
        "status",
        "source",
        "cpu",
        "ram",
        "last_seen",
    }
)


@dataclass(frozen=True)
class UtrechtAdapterConfig:
    mcp_url: str | None
    repo_path: Path | None
    fleet_inventory_path: Path | None


def load_utrecht_config() -> UtrechtAdapterConfig:
    repo_path = os.environ.get("UTRECHT_REPO_PATH")
    fleet_inventory_path = os.environ.get("UTRECHT_FLEET_INVENTORY_PATH")
    return UtrechtAdapterConfig(
        mcp_url=os.environ.get("UTRECHT_MCP_URL"),
        repo_path=Path(repo_path).expanduser() if repo_path else None,
        fleet_inventory_path=Path(fleet_inventory_path).expanduser()
        if fleet_inventory_path
        else None,
    )


def utrecht_status() -> dict[str, str | bool | None]:
    config = load_utrecht_config()
    repo_exists = config.repo_path.exists() if config.repo_path else False
    return {
        "mcp_url": config.mcp_url,
        "repo_path": str(config.repo_path) if config.repo_path else None,
        "repo_exists": repo_exists,
        "fleet_inventory_path": str(config.fleet_inventory_path)
        if config.fleet_inventory_path
        else None,
        "fleet_inventory_exists": config.fleet_inventory_path.exists()
        if config.fleet_inventory_path
        else False,
        "configured": bool(config.mcp_url or repo_exists or config.fleet_inventory_path),
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


def utrecht_fleet_inventory_summary() -> dict[str, Any]:
    config = load_utrecht_config()
    if not config.fleet_inventory_path:
        return {
            "configured": False,
            "path": None,
            "ok": False,
            "error": "Set UTRECHT_FLEET_INVENTORY_PATH to a safe utrecht-fleet inventory JSON.",
            "nodes": [],
        }
    path = config.fleet_inventory_path
    if not path.exists():
        return {
            "configured": True,
            "path": str(path),
            "ok": False,
            "error": "fleet_inventory_missing",
            "nodes": [],
        }

    payload = json.loads(path.read_text(encoding="utf-8"))
    nodes = _validate_safe_fleet_inventory(payload)
    status_counts: dict[str, int] = {}
    for node in nodes:
        status = str(node.get("status") or "unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    return {
        "configured": True,
        "path": str(path),
        "ok": True,
        "schema_version": payload.get("schema_version"),
        "inventory_kind": payload.get("inventory_kind"),
        "source": payload.get("source"),
        "privacy": payload.get("privacy", {}),
        "node_count": len(nodes),
        "status_counts": status_counts,
        "nodes": nodes,
    }


def _validate_safe_fleet_inventory(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("Fleet inventory root must be a JSON object.")
    if payload.get("source") != "utrecht-fleet":
        raise ValueError("Fleet inventory source must be utrecht-fleet.")
    privacy = payload.get("privacy")
    if not isinstance(privacy, dict) or privacy.get("contains_host_private_data") is not False:
        raise ValueError("Fleet inventory must declare contains_host_private_data=false.")
    nodes = payload.get("nodes")
    if not isinstance(nodes, list):
        raise ValueError("Fleet inventory nodes must be a list.")

    serialized = json.dumps(payload, sort_keys=True)
    for pattern in PRIVATE_TEXT_PATTERNS:
        if pattern.search(serialized):
            raise ValueError("Fleet inventory contains private-looking text.")

    safe_nodes: list[dict[str, Any]] = []
    for node in nodes:
        if not isinstance(node, dict):
            raise ValueError("Fleet inventory node must be an object.")
        extra = set(node) - SAFE_NODE_KEYS
        forbidden = set(node).intersection(FORBIDDEN_NODE_KEYS)
        if forbidden or extra:
            blocked = sorted(forbidden or extra)
            raise ValueError(f"Fleet inventory node has unsupported private field(s): {blocked}.")
        for required in ("hostname", "role", "status", "source"):
            if not str(node.get(required) or "").strip():
                raise ValueError(f"Fleet inventory node missing required field: {required}.")
        safe_nodes.append({key: node.get(key) for key in sorted(SAFE_NODE_KEYS) if key in node})
    return safe_nodes
