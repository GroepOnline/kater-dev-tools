from __future__ import annotations
import subprocess
import pytest

from kater.tunnel import (
    stop_cloudflared,
    detect_cloudflared,
    detect_tailscale,
    generate_cloudflare_config,
    generate_tailscale_funnel_cmd,
    tunnel_overview,
)


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
    assert "kater.example.com" in config
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


def test_stop_cloudflared_with_managed_unit_success(monkeypatch):
    monkeypatch.setattr("kater.tunnel._managed_unit", lambda: "test.service")
    monkeypatch.setattr("kater.tunnel._systemctl", lambda *args: subprocess.CompletedProcess(args, 0, stdout=""))
    assert stop_cloudflared() is True

def test_stop_cloudflared_with_managed_unit_failure(monkeypatch):
    monkeypatch.setattr("kater.tunnel._managed_unit", lambda: "test.service")
    monkeypatch.setattr("kater.tunnel._systemctl", lambda *args: subprocess.CompletedProcess(args, 1, stdout=""))
    assert stop_cloudflared() is False

def test_stop_cloudflared_with_managed_unit_none(monkeypatch):
    monkeypatch.setattr("kater.tunnel._managed_unit", lambda: "test.service")
    monkeypatch.setattr("kater.tunnel._systemctl", lambda *args: None)
    assert stop_cloudflared() is False

def test_stop_cloudflared_no_managed_unit_success(monkeypatch):
    monkeypatch.setattr("kater.tunnel._managed_unit", lambda: None)
    def mock_run(args, **kwargs):
        pass
    monkeypatch.setattr(subprocess, "run", mock_run)
    assert stop_cloudflared() is True

def test_stop_cloudflared_no_managed_unit_failure(monkeypatch):
    monkeypatch.setattr("kater.tunnel._managed_unit", lambda: None)
    def mock_run(args, **kwargs):
        raise Exception("Command failed")
    monkeypatch.setattr(subprocess, "run", mock_run)
    assert stop_cloudflared() is False
