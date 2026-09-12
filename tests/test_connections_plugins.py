from __future__ import annotations

import json

import pytest

from kater.api import ROUTER, Request, handle
from kater.connections import list_connection_views
from kater.plugins import PluginManifest, get_plugin_manifest, list_plugin_manifests
from kater.settings import KaterSettings, ServerConnection, ServerOverride


def test_plugin_manifest_validates_product_contract() -> None:
    manifest = PluginManifest.from_mapping(
        {
            "id": "example-tools",
            "name": "Example Tools",
            "version": "1.2.3",
            "publisher": "example",
            "toolkits": ["search", "docs"],
            "profiles": ["research"],
        }
    )
    assert manifest.id == "example-tools"
    assert manifest.toolkits == ("docs", "search")
    assert manifest.status == "installed"

    with pytest.raises(ValueError):
        PluginManifest.from_mapping({"id": "Bad Plugin", "name": "Bad", "version": "1.0.0"})


def test_plugin_registry_exposes_core_and_extension() -> None:
    manifests = list_plugin_manifests()
    ids = {manifest.id for manifest in manifests}
    assert "kater-core" in ids
    assert get_plugin_manifest("kater-core") is not None
    assert any(manifest.origin == "extension" for manifest in manifests)


def test_stored_connection_inventory_never_emits_secret() -> None:
    settings = KaterSettings(
        server_overrides={
            "linear": ServerOverride(
                connections=[
                    ServerConnection(
                        id="work",
                        label="workspace",
                        env={"LINEAR_API_KEY": "lin_secret_value"},
                        created_at=123.0,
                    )
                ]
            )
        }
    )
    rows = list_connection_views(integration="linear", settings=settings)
    assert len(rows) == 1
    payload = rows[0].as_dict()
    assert payload["id"] == "linear:work"
    assert payload["configured"] is True
    assert "lin_secret_value" not in json.dumps(payload)


def test_runtime_connection_inventory_uses_synthetic_env_id(monkeypatch) -> None:
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "sentry_runtime_secret")
    rows = list_connection_views(integration="sentry", settings=KaterSettings())
    assert len(rows) == 1
    assert rows[0].id == "sentry:env"
    assert rows[0].storage == "environment"
    assert rows[0].configured is True
    assert "sentry_runtime_secret" not in json.dumps(rows[0].as_dict())


def test_unconfigured_integration_has_no_connection_row(monkeypatch) -> None:
    monkeypatch.delenv("LINEAR_API_KEY", raising=False)
    rows = list_connection_views(integration="linear", settings=KaterSettings())
    assert rows == []


def _request(path: str, *, query: dict[str, list[str]] | None = None) -> Request:
    return Request(
        method="GET",
        path=path,
        query=query or {},
        headers={},
        raw_body=b"",
        client_ip="127.0.0.1",
        base_url="http://127.0.0.1:9091",
    )


def test_connections_api_is_secret_free(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "sentry_api_secret")
    response = handle(_request("/api/connections", query={"integration": ["sentry"]}))
    assert response.status == 200
    payload = response.payload
    assert payload is not None
    assert payload["total"] == 1
    assert payload["connections"][0]["id"] == "sentry:env"
    assert "sentry_api_secret" not in json.dumps(payload)


def test_plugin_manifest_api_returns_core(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    response = handle(_request("/api/plugins/kater-core"))
    assert response.status == 200
    payload = response.payload
    assert payload is not None
    assert payload["plugin"]["id"] == "kater-core"
    assert "github" in payload["plugin"]["toolkits"]


def test_integration_routes_alias_existing_connection_mutations() -> None:
    paths = [
        ("POST", "/api/integrations/linear/credentials"),
        ("POST", "/api/integrations/slack/oauth/start"),
        ("GET", "/api/integrations/slack/connections"),
        ("DELETE", "/api/integrations/slack/connections/demo"),
    ]
    for method, path in paths:
        matched = ROUTER.match(method, path)
        assert matched is not None, (method, path)


def test_connections_cli_json(monkeypatch, tmp_path) -> None:
    from typer.testing import CliRunner

    from kater.cli import app

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SENTRY_AUTH_TOKEN", "sentry_cli_secret")
    result = CliRunner().invoke(
        app,
        ["connections", "--integration", "sentry", "--json"],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.stdout)
    assert payload["total"] == 1
    assert payload["connections"][0]["id"] == "sentry:env"
    assert "sentry_cli_secret" not in result.stdout
