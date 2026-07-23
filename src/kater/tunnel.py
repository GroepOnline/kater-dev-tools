from __future__ import annotations

import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import Any

_log = logging.getLogger("kater.tunnel")


@dataclass
class TunnelInfo:
    provider: str
    name: str
    url: str | None = None
    running: bool = False
    error: str | None = None
    pid: int | None = None
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "name": self.name,
            "url": self.url,
            "running": self.running,
            "error": self.error,
            "pid": self.pid,
        }


# In production the cloudflare tunnel runs as a systemd user unit with
# Restart=always. A bare `pkill` is therefore undone within RestartSec, so the
# tunnel appears to "turn itself back on". When a managed unit is present we
# must control that unit (stop/start) rather than the raw process.
DEFAULT_TUNNEL_UNIT = "kater-cloudflared.service"


def _tunnel_unit() -> str | None:
    return os.environ.get("KATER_TUNNEL_UNIT", DEFAULT_TUNNEL_UNIT) or None


ALLOWED_SYSTEMCTL_CMDS = {"cat", "is-active", "start", "stop"}


def _systemctl(*args: str) -> subprocess.CompletedProcess[str] | None:
    if not args or args[0] not in ALLOWED_SYSTEMCTL_CMDS:
        raise ValueError(f"systemctl command '{args[0] if args else ''}' not allowed")
    for arg in args[1:]:
        if arg.startswith("-"):
            raise ValueError(f"systemctl option injection detected: {arg}")

    if not shutil.which("systemctl"):
        return None
    try:
        return subprocess.run(
            ["systemctl", "--user", *args],
            capture_output=True,
            text=True,
            timeout=8,
        )
    except Exception as exc:
        _log.debug("systemctl %s failed: %s", args, exc)
        return None


def _unit_exists(unit: str) -> bool:
    result = _systemctl("cat", unit)
    return bool(result and result.returncode == 0)


def _unit_active(unit: str) -> bool:
    result = _systemctl("is-active", unit)
    return bool(result and result.stdout.strip() == "active")


def _managed_unit() -> str | None:
    """The systemd unit that owns the cloudflare tunnel, if any."""
    unit = _tunnel_unit()
    return unit if unit and _unit_exists(unit) else None


def detect_cloudflared() -> bool:
    return shutil.which("cloudflared") is not None


def detect_tailscale() -> bool:
    return shutil.which("tailscale") is not None


def tailscale_status() -> dict[str, Any]:
    if not detect_tailscale():
        return {"installed": False, "connected": False}
    try:
        result = subprocess.run(
            ["tailscale", "status", "--json"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            import json

            data = json.loads(result.stdout)
            return {
                "installed": True,
                "connected": data.get("BackendState") == "Running",
                "ip": data.get("TailscaleIPs", [None])[0],
                "hostname": data.get("Self", {}).get("HostName"),
                "funnel": _check_tailscale_funnel(),
            }
    except Exception as exc:
        _log.debug("tailscale status failed: %s", exc)
    return {"installed": True, "connected": False}


def _check_tailscale_funnel() -> bool:
    try:
        result = subprocess.run(
            ["tailscale", "funnel", "status"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and "on" in result.stdout.lower()
    except Exception as exc:
        _log.debug("tailscale funnel status failed: %s", exc)
        return False


def cloudflared_status(tunnel_name: str = "kater") -> dict[str, Any]:
    if not detect_cloudflared():
        return {"installed": False, "running": False}
    unit = _managed_unit()
    # A managed unit is the source of truth: report its state, not a stray pid.
    running = _unit_active(unit) if unit else _is_cloudflared_running()
    config_path = os.path.expanduser(f"~/.cloudflared/{tunnel_name}.yml")
    has_config = os.path.exists(config_path)
    return {
        "installed": True,
        "running": running,
        "tunnel_name": tunnel_name,
        "managed_unit": unit,
        "has_config": has_config,
        "config_path": config_path if has_config else None,
    }


def _is_cloudflared_running() -> bool:
    try:
        result = subprocess.run(
            ["pgrep", "-f", "cloudflared.*tunnel"],
            capture_output=True,
            timeout=3,
        )
        return result.returncode == 0
    except Exception as exc:
        _log.debug("cloudflared process check failed: %s", exc)
        return False


def generate_cloudflare_config(
    tunnel_name: str = "kater",
    domain: str | None = None,
    api_port: int = 9091,
    mcp_port: int = 9090,
    ws_port: int = 9092,
) -> str:
    domain = domain or os.environ.get("KATER_DOMAIN", "kater.example.com")
    return f"""tunnel: {tunnel_name}
credentials-file: ~/.cloudflared/{tunnel_name}.json

ingress:
  - hostname: {domain}
    service: http://localhost:{mcp_port}
    originRequest:
      # FastMCP DNS-rebinding protection only allows localhost Host when
      # bound to 127.0.0.1. Prefer also setting KATER_DOMAIN so /sse accepts
      # the public Host; this rewrite is a belt-and-braces fallback.
      httpHostHeader: 127.0.0.1:{mcp_port}
  - service: http_status:404
"""


def generate_tailscale_funnel_cmd(
    port: int = 9090,
    scope: str = "all",
) -> list[str]:
    if scope == "all":
        return ["tailscale", "funnel", str(port)]
    return ["tailscale", "funnel", f"--set-path=/{scope}", str(port)]


def start_cloudflared(
    tunnel_name: str = "kater",
    config_path: str | None = None,
    domain: str | None = None,
) -> TunnelInfo:
    if not detect_cloudflared():
        return TunnelInfo(
            provider="cloudflare",
            name=tunnel_name,
            error="cloudflared not installed. Install: brew install cloudflared",
        )

    resolved_domain = domain or os.environ.get("KATER_DOMAIN", "kater.example.com")

    # Prefer the managed systemd unit so start/stop stay consistent and the
    # tunnel isn't fought over by a stray Popen process.
    unit = _managed_unit()
    if unit:
        result = _systemctl("start", unit)
        ok = bool(result and result.returncode == 0)
        # `systemctl start` returns once activation is requested; the unit may
        # report active a moment later. Trust the command result so a freshly
        # started unit isn't reported as down.
        running = ok or _unit_active(unit)
        return TunnelInfo(
            provider="cloudflare",
            name=unit,
            url=f"https://{resolved_domain}" if running else None,
            running=running,
            error=None if ok else "Failed to start tunnel unit.",
            config={"managed_unit": unit, "domain": resolved_domain},
        )

    if config_path is None:
        config_path = os.path.expanduser(f"~/.cloudflared/{tunnel_name}.yml")

    if not os.path.exists(config_path):
        config_content = generate_cloudflare_config(tunnel_name=tunnel_name, domain=resolved_domain)
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        with open(config_path, "w") as f:
            f.write(config_content)

    try:
        proc = subprocess.Popen(
            [
                "cloudflared",
                "tunnel",
                "--config",
                config_path,
                "run",
                tunnel_name,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
        return TunnelInfo(
            provider="cloudflare",
            name=tunnel_name,
            url=f"https://{resolved_domain}",
            running=proc.poll() is None,
            pid=proc.pid,
            config={"config_path": config_path, "domain": resolved_domain},
        )
    except Exception as exc:
        return TunnelInfo(
            provider="cloudflare",
            name=tunnel_name,
            error=str(exc),
        )


def stop_cloudflared() -> bool:
    # Stop the owning systemd unit when present; otherwise a Restart=always unit
    # would respawn the tunnel within seconds and it would look "still on".
    unit = _managed_unit()
    if unit:
        result = _systemctl("stop", unit)
        return bool(result and result.returncode == 0)
    try:
        subprocess.run(
            ["pkill", "-f", "cloudflared.*tunnel"],
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception as exc:
        _log.debug("stopping cloudflared failed: %s", exc)
        return False


def start_tailscale_funnel(port: int = 9090) -> TunnelInfo:
    if not detect_tailscale():
        return TunnelInfo(
            provider="tailscale",
            name="funnel",
            error="tailscale not installed. Install: https://tailscale.com/download",
        )
    try:
        ts_status = tailscale_status()
        if not ts_status.get("connected"):
            return TunnelInfo(
                provider="tailscale",
                name="funnel",
                error="Tailscale not connected. Run: tailscale up",
            )
        proc = subprocess.Popen(
            ["tailscale", "funnel", str(port)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(1)
        hostname = ts_status.get("hostname", "machine")
        return TunnelInfo(
            provider="tailscale",
            name="funnel",
            url=f"https://{hostname}.ts.net",
            running=proc.poll() is None,
            pid=proc.pid,
            config={"port": port},
        )
    except Exception as exc:
        return TunnelInfo(
            provider="tailscale",
            name="funnel",
            error=str(exc),
        )


def stop_tailscale_funnel(port: int = 9090) -> bool:
    try:
        subprocess.run(
            ["tailscale", "funnel", "reset"],
            capture_output=True,
            timeout=5,
        )
        return True
    except Exception as exc:
        _log.debug("tailscale funnel reset failed: %s", exc)
        return False


def tunnel_overview(domain: str | None = None) -> dict[str, Any]:
    resolved = domain or os.environ.get("KATER_DOMAIN", "kater.example.com")
    return {
        "cloudflare": cloudflared_status(),
        "tailscale": tailscale_status(),
        "suggested_domain": resolved,
        "available": {
            "cloudflare": detect_cloudflared(),
            "tailscale": detect_tailscale(),
        },
        "client_configs": {
            "cloudflare_url": f"https://{resolved}/sse",
            "tailscale_url": "https://<hostname>.ts.net:9090/sse",
        },
    }
