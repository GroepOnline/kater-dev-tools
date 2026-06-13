from __future__ import annotations

from kater.adapters.utrecht import utrecht_status


def test_utrecht_adapter_reports_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("UTRECHT_MCP_URL", raising=False)
    monkeypatch.delenv("UTRECHT_REPO_PATH", raising=False)

    payload = utrecht_status()

    assert payload["configured"] is False
    assert payload["repo_exists"] is False


def test_utrecht_adapter_accepts_mcp_url(monkeypatch) -> None:
    monkeypatch.setenv("UTRECHT_MCP_URL", "http://127.0.0.1:9090/sse")

    payload = utrecht_status()

    assert payload["configured"] is True
    assert payload["mcp_url"] == "http://127.0.0.1:9090/sse"
