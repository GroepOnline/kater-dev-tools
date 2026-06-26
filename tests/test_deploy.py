from __future__ import annotations

from kater.deploy import (
    list_deploy_formats,
    render_cloudflare_config,
    render_deploy,
    render_docker_config,
    render_k8s_config,
    render_sse_config,
    render_stdio_config,
    render_systemd_config,
)


def test_list_deploy_formats():
    formats = list_deploy_formats()
    names = {f["name"] for f in formats}
    assert "stdio" in names
    assert "sse" in names
    assert "docker" in names
    assert "cloudflare" in names
    assert "systemd" in names
    assert "k8s" in names


def test_stdio_config():
    config = render_stdio_config(profile="ops")
    assert config["format"] == "claude-desktop"
    servers = config["mcpServers"]
    assert "kater" in servers
    assert servers["kater"]["type"] == "stdio"
    assert servers["kater"]["command"] == "uvx"


def test_sse_config():
    config = render_sse_config(profile="research", kater_url="https://kater.local/sse")
    servers = config["mcpServers"]
    assert servers["kater"]["url"] == "https://kater.local/sse"


def test_docker_config():
    config = render_docker_config(profile="ops")
    assert config["format"] == "docker-compose"
    svc = config["compose"]["services"]["kater"]
    assert "9090" in svc["ports"][0]
    assert "9091" in svc["ports"][1]


def test_cloudflare_config():
    config = render_cloudflare_config(profile="core", domain="kater.mysite.com")
    assert config["format"] == "cloudflare-tunnel"
    assert config["client_config"]["mcpServers"]["kater"]["url"] == "https://kater.mysite.com/sse"
    assert len(config["steps"]) >= 2


def test_systemd_config():
    config = render_systemd_config(profile="ops")
    assert config["format"] == "systemd"
    assert "[Unit]" in config["unit_file"]
    assert "kater serve" in config["unit_file"]


def test_k8s_config():
    config = render_k8s_config(profile="cloud")
    assert config["format"] == "kubernetes"
    assert config["manifests"]["deployment"]["kind"] == "Deployment"


def test_render_deploy_dispatch():
    for fmt in ("stdio", "sse", "docker", "cloudflare", "systemd", "k8s"):
        config = render_deploy(fmt, profile="core")
        assert "format" in config or "error" not in config


def test_render_deploy_unknown():
    config = render_deploy("nonexistent")
    assert "error" in config
