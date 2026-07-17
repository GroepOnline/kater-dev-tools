from __future__ import annotations

import pytest

from kater.tunnel import (
    _systemctl,
    detect_cloudflared,
    detect_tailscale,
    generate_cloudflare_config,
    generate_tailscale_funnel_cmd,
    tunnel_overview,
)


def test_systemctl_validation():
    with pytest.raises(ValueError, match="systemctl command '' not allowed"):
        _systemctl()

    with pytest.raises(ValueError, match="systemctl command 'status' not allowed"):
        _systemctl("status", "my-unit.service")

    with pytest.raises(ValueError, match="systemctl option injection detected: --help"):
        _systemctl("start", "--help")

    with pytest.raises(ValueError, match="systemctl option injection detected: -f"):
        _systemctl("stop", "my-unit.service", "-f")


def test_detect_cloudflared():
    result = detect_cloudflared()
    assert isinstance(result, bool)


def test_detect_tailscale():
    result = detect_tailscale()
    assert isinstance(result, bool)


def test_generate_cloudflare_config():
    config = generate_cloudflare_config(
        tunnel_name="my-tunnel",
        domain="kater.example.com",
    )
    assert "tunnel: my-tunnel" in config
    assert "hostname: kater.example.com" in config
    assert "localhost:9090" in config
    assert "ingress:" in config
    assert "api.kater" not in config


def test_generate_tailscale_funnel_cmd():
    cmd = generate_tailscale_funnel_cmd(port=9090)
    assert "tailscale" in cmd
    assert "funnel" in cmd
    assert "9090" in cmd


def test_tunnel_overview():
    overview = tunnel_overview(domain="test.example.com")
    assert "cloudflare" in overview
    assert "tailscale" in overview
    assert "available" in overview
    assert "client_configs" in overview
    assert overview["client_configs"]["cloudflare_url"] == "https://test.example.com/sse"


def test_tunnel_overview_defaults(monkeypatch):
    monkeypatch.delenv("KATER_DOMAIN", raising=False)
    overview = tunnel_overview()
    assert overview["suggested_domain"] == "kater.example.com"
