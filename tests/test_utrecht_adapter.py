from __future__ import annotations

from kater.adapters.utrecht import utrecht_pipeline_status, utrecht_status


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


def test_utrecht_pipeline_status_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("UTRECHT_REPO_PATH", raising=False)

    payload = utrecht_pipeline_status()

    assert payload["configured"] is False


def test_utrecht_pipeline_status_with_repo(monkeypatch, tmp_path) -> None:
    pipelines = tmp_path / "pipelines"
    pipelines.mkdir(parents=True)
    (pipelines / "extract.json").write_text("{}")
    (pipelines / "transform.json").write_text("{}")

    monkeypatch.setenv("UTRECHT_REPO_PATH", str(tmp_path))

    payload = utrecht_pipeline_status()

    assert payload["configured"] is True
    assert payload["artifact_count"] == 2
    assert "pipelines/extract.json" in payload["pipeline_artifacts"]
