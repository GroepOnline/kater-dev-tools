from __future__ import annotations

import json
from pathlib import Path

import pytest

from kater.adapters.utrecht import (
    utrecht_fleet_inventory_summary,
    utrecht_pipeline_status,
    utrecht_status,
)


def test_utrecht_adapter_reports_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("UTRECHT_MCP_URL", raising=False)
    monkeypatch.delenv("UTRECHT_REPO_PATH", raising=False)
    monkeypatch.delenv("UTRECHT_FLEET_INVENTORY_PATH", raising=False)

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
    assert Path("pipelines/extract.json") in [
        Path(artifact) for artifact in payload["pipeline_artifacts"]
    ]


def test_utrecht_fleet_inventory_summary_unconfigured(monkeypatch) -> None:
    monkeypatch.delenv("UTRECHT_FLEET_INVENTORY_PATH", raising=False)

    payload = utrecht_fleet_inventory_summary()

    assert payload["configured"] is False
    assert payload["ok"] is False
    assert payload["nodes"] == []


def test_utrecht_fleet_inventory_summary_accepts_safe_inventory(monkeypatch, tmp_path) -> None:
    inventory = {
        "schema_version": 1,
        "inventory_kind": "manual_seed",
        "source": "utrecht-fleet",
        "privacy": {"contains_host_private_data": False},
        "nodes": [
            {
                "hostname": "sofie",
                "role": "Brain, pipeline, intake",
                "status": "ok",
                "source": "README.md",
                "cpu": "8 cores",
                "ram": "7.5GB",
                "last_seen": None,
            },
            {
                "hostname": "kater",
                "role": "Unverified historical node",
                "status": "review",
                "source": "Notion Fleet Node Registry",
            },
        ],
    }
    path = tmp_path / "fleet.json"
    path.write_text(json.dumps(inventory), encoding="utf-8")
    monkeypatch.setenv("UTRECHT_FLEET_INVENTORY_PATH", str(path))

    payload = utrecht_fleet_inventory_summary()

    assert payload["ok"] is True
    assert payload["node_count"] == 2
    assert payload["status_counts"] == {"ok": 1, "review": 1}
    assert payload["nodes"][0]["hostname"] == "sofie"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("tailscale_ip", "100.64.0.1"),
        ("ssh", "sofie"),
        ("token", "tskey-auth-example"),
    ],
)
def test_utrecht_fleet_inventory_rejects_private_fields(
    monkeypatch,
    tmp_path,
    field: str,
    value: str,
) -> None:
    inventory = {
        "schema_version": 1,
        "source": "utrecht-fleet",
        "privacy": {"contains_host_private_data": False},
        "nodes": [
            {
                "hostname": "sofie",
                "role": "Brain",
                "status": "ok",
                "source": "README.md",
                field: value,
            }
        ],
    }
    path = tmp_path / "fleet.json"
    path.write_text(json.dumps(inventory), encoding="utf-8")
    monkeypatch.setenv("UTRECHT_FLEET_INVENTORY_PATH", str(path))

    with pytest.raises(ValueError, match=r"private|unsupported"):
        utrecht_fleet_inventory_summary()
