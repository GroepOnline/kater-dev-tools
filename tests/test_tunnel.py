from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, mock_open

from kater.tunnel import (
    detect_cloudflared,
    detect_tailscale,
    generate_cloudflare_config,
    generate_tailscale_funnel_cmd,
    start_cloudflared,
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
def test_start_cloudflared_not_installed(monkeypatch):
    monkeypatch.setattr("kater.tunnel.detect_cloudflared", lambda: False)
    info = start_cloudflared()
    assert info.running is False
    assert info.error is not None and "cloudflared not installed" in info.error
    assert info.provider == "cloudflare"

def test_start_cloudflared_managed_unit_success(monkeypatch):
    monkeypatch.setattr("kater.tunnel.detect_cloudflared", lambda: True)
    monkeypatch.setattr("kater.tunnel._managed_unit", lambda: "test-unit.service")

    def mock_systemctl(cmd, unit):
        if cmd == "start":
            return subprocess.CompletedProcess(args=[], returncode=0, stdout="")
        return None

    monkeypatch.setattr("kater.tunnel._systemctl", mock_systemctl)
    monkeypatch.setattr("kater.tunnel._unit_active", lambda unit: False)  # Success

    info = start_cloudflared(domain="test.local")
    assert info.running is True
    assert info.name == "test-unit.service"
    assert info.url == "https://test.local"
    assert info.error is None
    assert info.config["managed_unit"] == "test-unit.service"

def test_start_cloudflared_managed_unit_already_active(monkeypatch):
    monkeypatch.setattr("kater.tunnel.detect_cloudflared", lambda: True)
    monkeypatch.setattr("kater.tunnel._managed_unit", lambda: "test-unit.service")

    # Simulate start command failing, but unit is active
    def mock_systemctl(cmd, unit):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="")

    monkeypatch.setattr("kater.tunnel._systemctl", mock_systemctl)
    monkeypatch.setattr("kater.tunnel._unit_active", lambda unit: True)

    info = start_cloudflared(domain="test.local")
    assert info.running is True
    assert info.error == "Failed to start tunnel unit."

def test_start_cloudflared_managed_unit_fail(monkeypatch):
    monkeypatch.setattr("kater.tunnel.detect_cloudflared", lambda: True)
    monkeypatch.setattr("kater.tunnel._managed_unit", lambda: "test-unit.service")

    # Simulate start command failing, and unit is not active
    def mock_systemctl(cmd, unit):
        return subprocess.CompletedProcess(args=[], returncode=1, stdout="")

    monkeypatch.setattr("kater.tunnel._systemctl", mock_systemctl)
    monkeypatch.setattr("kater.tunnel._unit_active", lambda unit: False)

    info = start_cloudflared(domain="test.local")
    assert info.running is False
    assert info.error == "Failed to start tunnel unit."
    assert info.url is None

def test_start_cloudflared_popen_success(monkeypatch):
    monkeypatch.setattr("kater.tunnel.detect_cloudflared", lambda: True)
    monkeypatch.setattr("kater.tunnel._managed_unit", lambda: None)
    monkeypatch.setattr("os.path.exists", lambda path: False)
    monkeypatch.setattr("os.makedirs", lambda path, exist_ok: None)
    monkeypatch.setattr("time.sleep", lambda s: None) # speed up test

    m_open = mock_open()
    monkeypatch.setattr("builtins.open", m_open)

    m_proc = MagicMock()
    m_proc.poll.return_value = None # Process is running
    m_proc.pid = 12345

    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: m_proc)

    info = start_cloudflared(tunnel_name="my-tunnel", domain="test.local")

    assert info.running is True
    assert info.name == "my-tunnel"
    assert info.pid == 12345
    assert info.url == "https://test.local"
    assert info.error is None
    m_open.assert_called_once()

def test_start_cloudflared_popen_exception(monkeypatch):
    monkeypatch.setattr("kater.tunnel.detect_cloudflared", lambda: True)
    monkeypatch.setattr("kater.tunnel._managed_unit", lambda: None)
    monkeypatch.setattr("os.path.exists", lambda path: True) # skip file creation

    def raise_exception(*args, **kwargs):
        raise Exception("spawn error")

    monkeypatch.setattr("subprocess.Popen", raise_exception)

    info = start_cloudflared(tunnel_name="my-tunnel")

    assert info.running is False
    assert info.error == "spawn error"
    assert info.provider == "cloudflare"
