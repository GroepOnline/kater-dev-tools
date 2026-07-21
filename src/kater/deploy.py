from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field

_SAFE_TOKEN = re.compile(r"^[A-Za-z0-9._-]+$")
_SAFE_PATH = re.compile(r"^[A-Za-z0-9._/\\:-]+$")


class DeployTarget(BaseModel):
    name: str
    description: str
    transport: str  # stdio | sse | docker | cloudflare | systemd
    config: dict[str, Any] = Field(default_factory=dict)


def render_stdio_config(
    profile: str = "core",
    kater_url: str = "http://127.0.0.1:9090/sse",
) -> dict[str, Any]:
    """Config for running Kater as a local stdio bridge (e.g. Claude Desktop)."""
    return {
        "format": "claude-desktop",
        "description": (
            "Add this to ~/Library/Application Support/Claude/claude_desktop_config.json"
        ),
        "mcpServers": {
            "kater": {
                "type": "stdio",
                "command": "uvx",
                "args": ["kater", "serve", "--mcp-only", "--profile", profile],
                "env": {"KATER_PROFILE": profile},
            }
        },
    }


def render_sse_config(
    profile: str = "core",
    kater_url: str = "http://127.0.0.1:9090/sse",
) -> dict[str, Any]:
    """Config for connecting to Kater over SSE (Cursor, ChatGPT, etc.)."""
    return {
        "format": "cursor-chatgpt",
        "description": "Remote SSE endpoint for any MCP-compatible client",
        "mcpServers": {
            "kater": {
                "type": "sse",
                "url": kater_url,
                "env": {"KATER_PROFILE": profile},
            }
        },
    }


def render_docker_config(
    profile: str = "core",
    image: str = "kater-dev-tools:latest",
    api_port: int = 9091,
    mcp_port: int = 9090,
    cors_origins: str = "https://kater.example.com",
) -> dict[str, Any]:
    """Docker Compose snippet for self-hosted deployment."""
    return {
        "format": "docker-compose",
        "description": "Self-hosted Docker deployment",
        "compose": {
            "services": {
                "kater": {
                    "image": image,
                    "restart": "unless-stopped",
                    "command": ["kater", "serve", "--host", "0.0.0.0"],  # noqa: S104
                    "environment": {
                        "KATER_PROFILE": profile,
                        "KATER_PUBLIC": "1",
                        "KATER_AUTH_MODE": "oauth",
                        "KATER_RATE_LIMIT": "60",
                        "KATER_CORS_ORIGINS": cors_origins,
                        "KATER_HOST": "0.0.0.0",  # noqa: S104
                    },
                    "ports": [
                        f"{mcp_port}:9090",
                        f"{api_port}:9091",
                    ],
                    "healthcheck": {
                        "test": ["CMD", "curl", "-sf", "http://localhost:9091/health"],
                        "interval": "30s",
                        "timeout": "5s",
                        "retries": 3,
                    },
                }
            }
        },
    }


def render_cloudflare_config(
    profile: str = "core",
    domain: str = "kater.example.com",
    tunnel_name: str = "kater",
) -> dict[str, Any]:
    """Cloudflare Tunnel config for public deployment without exposing ports."""
    return {
        "format": "cloudflare-tunnel",
        "description": "Expose Kater via Cloudflare Tunnel — no open ports needed",
        "environment": {
            "KATER_PUBLIC": "1",
            "KATER_AUTH_MODE": "oauth",
            "KATER_RATE_LIMIT": "60",
            "KATER_HOST": "127.0.0.1",
        },
        "steps": [
            "cloudflared tunnel login",
            f"cloudflared tunnel create {tunnel_name}",
            f"cloudflared tunnel route dns {tunnel_name} {domain}",
            "./scripts/deploy-cloudflare.sh " + domain + " " + tunnel_name,
        ],
        "tunnel_config": {
            "tunnel": tunnel_name,
            "credentials-file": f"~/.cloudflared/{tunnel_name}.json",
            "ingress": [
                {
                    "hostname": domain,
                    "service": "http://localhost:9090",
                },
                {
                    "service": "http_status:404",
                },
            ],
        },
        "client_config": {
            "mcpServers": {
                "kater": {
                    "type": "sse",
                    "url": f"https://{domain}/sse",
                    "env": {"KATER_PROFILE": profile},
                }
            }
        },
    }


def render_systemd_config(
    profile: str = "core",
    user: str | None = None,
    workdir: str | None = None,
) -> dict[str, Any]:
    """Systemd unit file for Linux server deployment."""
    import getpass
    import os

    user = user or getpass.getuser()
    workdir = workdir or os.getcwd()
    if not _SAFE_TOKEN.match(profile):
        raise ValueError(f"Invalid profile: {profile!r}")
    if not _SAFE_TOKEN.match(user):
        raise ValueError(f"Invalid user: {user!r}")
    if not _SAFE_PATH.match(workdir):
        raise ValueError(f"Invalid workdir: {workdir!r}")
    unit = f"""[Unit]
Description=Kater MCP Gateway
After=network.target

[Service]
Type=simple
User={user}
WorkingDirectory={workdir}
ExecStart={workdir}/.venv/bin/kater serve --profile {profile}
Restart=on-failure
RestartSec=5
Environment=KATER_PROFILE={profile}

[Install]
WantedBy=multi-user.target"""

    return {
        "format": "systemd",
        "description": "Install as a systemd service on Linux",
        "unit_file": unit,
        "install_steps": [
            f"sudo tee /etc/systemd/system/kater.service << 'EOF'\n{unit}\nEOF",
            "sudo systemctl daemon-reload",
            "sudo systemctl enable kater",
            "sudo systemctl start kater",
        ],
    }


def render_k8s_config(
    profile: str = "core",
    image: str = "kater-dev-tools:latest",
    domain: str = "kater.example.com",
) -> dict[str, Any]:
    """Kubernetes manifests for cluster deployment."""
    return {
        "format": "kubernetes",
        "description": "Deploy to Kubernetes",
        "manifests": {
            "deployment": {
                "apiVersion": "apps/v1",
                "kind": "Deployment",
                "metadata": {"name": "kater"},
                "spec": {
                    "replicas": 1,
                    "selector": {"matchLabels": {"app": "kater"}},
                    "template": {
                        "metadata": {"labels": {"app": "kater"}},
                        "spec": {
                            "containers": [
                                {
                                    "name": "kater",
                                    "image": image,
                                    "ports": [
                                        {"containerPort": 9090, "name": "mcp"},
                                        {"containerPort": 9091, "name": "api"},
                                    ],
                                    "env": [{"name": "KATER_PROFILE", "value": profile}],
                                    "livenessProbe": {
                                        "httpGet": {"path": "/health", "port": 9091},
                                        "periodSeconds": 30,
                                    },
                                }
                            ]
                        },
                    },
                },
            },
            "service": {
                "apiVersion": "v1",
                "kind": "Service",
                "metadata": {"name": "kater"},
                "spec": {
                    "selector": {"app": "kater"},
                    "ports": [
                        {"port": 9090, "name": "mcp"},
                        {"port": 9091, "name": "api"},
                    ],
                },
            },
        },
    }


DEPLOY_FORMATS: dict[str, tuple[str, Callable[..., dict[str, Any]]]] = {
    "stdio": ("Local stdio process (Claude Desktop)", render_stdio_config),
    "sse": ("Remote SSE endpoint (Cursor, ChatGPT)", render_sse_config),
    "docker": ("Docker Compose self-hosted", render_docker_config),
    "cloudflare": ("Cloudflare Tunnel (no open ports)", render_cloudflare_config),
    "systemd": ("Systemd service (Linux server)", render_systemd_config),
    "k8s": ("Kubernetes cluster", render_k8s_config),
}


def list_deploy_formats() -> list[dict[str, str]]:
    return [{"name": name, "description": desc} for name, (desc, _) in DEPLOY_FORMATS.items()]


def render_deploy(
    fmt: str,
    profile: str = "core",
    **kwargs: Any,
) -> dict[str, Any]:
    if fmt not in DEPLOY_FORMATS:
        available = ", ".join(DEPLOY_FORMATS)
        return {"error": f"Unknown format '{fmt}'. Available: {available}"}
    _, renderer = DEPLOY_FORMATS[fmt]
    return renderer(profile=profile, **kwargs)
