from __future__ import annotations

import json
import sqlite3
from unittest.mock import Mock

import pytest

from kater import extensions, fabric_catalog, profiles
from kater.api import ROUTER, Request, fabric_routes
from kater.authgate import RequestIdentity
from kater.connectors.models import ConnectorRecord, ConnectorTransport, ConnectorType
from kater.profiles import McpServerConfig, RiskLevel, ToolSource, Transport

PATHS = (
    "/api/fabric",
    "/api/toolkits",
    "/api/integrations",
    "/api/plugins",
    "/api/mcp/catalog",
    "/api/connections",
    "/api/actions",
)


@pytest.fixture(autouse=True)
def clean_kater_state(monkeypatch, tmp_path):
    """Replace shared database fixture with a strict SQL-free catalog fixture."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_PUBLIC", "1")
    monkeypatch.setenv("KATER_EXTENSIONS_MODULE", "fixture.extension")

    def no_database(*args, **kwargs):
        pytest.fail("Catalog visibility tests must not open a database")

    monkeypatch.setattr(sqlite3, "connect", no_database)
    sources = tuple(
        ToolSource(
            name=name,
            description=name,
            transport=Transport.HTTP,
            risk=RiskLevel.LOW,
            profiles=set(source_profiles),
            mcp=McpServerConfig(url="https://example.test/mcp"),
        )
        for name, source_profiles in (
            ("public-source", {"core"}),
            ("mixed-source", {"core", "secret-profile"}),
            ("private-source", {"secret-profile"}),
        )
    )
    monkeypatch.setattr(profiles, "_BUILTIN_TOOL_SOURCES", sources)
    monkeypatch.setattr(fabric_catalog, "TOOL_SOURCES", sources)
    manifests = (
        {"id": "private-plugin", "profiles": ["secret-profile"], "toolkits": ["private-source"]},
        {"id": "private-toolkit-plugin", "toolkits": ["private-source"]},
        {
            "id": "mixed-plugin",
            "profiles": ["core", "secret-profile"],
            "toolkits": ["public-source", "mixed-source", "private-source"],
        },
    )
    attributes = {"PRIVATE_PROFILES": {"secret-profile"}, "PLUGINS": manifests}

    def extension_attr(name, default):
        return attributes.get(name, default)

    monkeypatch.setattr(extensions, "extension_attr", extension_attr)
    monkeypatch.setattr(fabric_catalog, "extension_attr", extension_attr)
    records = [
        ConnectorRecord(
            id=name,
            display_name=name,
            type=kind,
            version="1",
            profiles=frozenset(record_profiles),
            transport=ConnectorTransport(kind="http", endpoint="https://example.test/mcp"),
        )
        for name, record_profiles, kind in (
            # A persisted row must not resurrect a hidden source, even with stale public profiles.
            ("private-source", {"core"}, ConnectorType.MCP),
            ("mixed-source", {"core", "secret-profile"}, ConnectorType.MCP),
            ("private-mcp", {"secret-profile"}, ConnectorType.MCP),
            ("private-bridge", {"secret-profile"}, ConnectorType.BRIDGE),
            ("private-api", {"secret-profile"}, ConnectorType.API),
            ("mixed-dynamic", {"core", "secret-profile"}, ConnectorType.BRIDGE),
            ("unscoped-dynamic", set(), ConnectorType.MCP),
        )
    ]
    monkeypatch.setattr(fabric_catalog, "list_connectors", lambda: records)
    monkeypatch.setattr(
        fabric_catalog, "load_settings", lambda: Mock(is_server_enabled=Mock(return_value=True))
    )
    monkeypatch.setattr(fabric_catalog, "source_is_configured", lambda *args: False)
    monkeypatch.setattr(fabric_catalog, "binding_is_satisfied", lambda *args, **kwargs: False)
    monkeypatch.setattr(fabric_routes, "get_request_identity", lambda: RequestIdentity())
    yield attributes


def response_for(path, query=None):
    matched = ROUTER.match("GET", path)
    assert matched is not None
    route, params = matched
    return route.handler(
        Request(
            method="GET",
            path=path,
            query=query or {},
            headers={},
            raw_body=b"",
            client_ip="127.0.0.1",
            base_url="http://localhost:9091",
            params=params,
        )
    )


@pytest.mark.parametrize("path", PATHS)
@pytest.mark.parametrize("public_value", ["1", "true", "yes", "on"])
def test_public_catalog_filters_private_records_and_metadata(monkeypatch, path, public_value):
    monkeypatch.setenv("KATER_PUBLIC", public_value)
    response = response_for(path)
    assert response.status == 200
    serialized = json.dumps(response.payload)
    for private_value in (
        "secret-profile",
        "private-source",
        "private-mcp",
        "private-bridge",
        "private-api",
        "private-plugin",
        "private-toolkit-plugin",
    ):
        assert private_value not in serialized
    assert response.payload["total"] > 0
    if path in {"/api/fabric", "/api/integrations", "/api/mcp/catalog"}:
        assert "mixed-dynamic" in serialized
        assert "unscoped-dynamic" in serialized


@pytest.mark.parametrize("path", PATHS)
def test_private_profile_filter_cannot_reveal_metadata(path):
    response = response_for(path, {"profile": ["secret-profile"]})
    assert response.status == 200
    assert response.payload["total"] == 0


def test_nonpublic_catalog_retains_private_and_mixed_entries(monkeypatch):
    monkeypatch.setenv("KATER_PUBLIC", "0")
    payload = fabric_catalog.catalog_payload()
    serialized = json.dumps(payload)
    for name in (
        "secret-profile",
        "private-source",
        "private-mcp",
        "private-bridge",
        "private-api",
        "private-plugin",
    ):
        assert name in serialized
    mixed = next(item for item in payload["plugins"] if item["id"] == "plugin:mixed-plugin")
    assert mixed["profiles"] == ["core", "secret-profile"]
    assert "private-source" in mixed["metadata"]["toolkits"]


@pytest.mark.parametrize("path", PATHS)
def test_capability_restriction_still_precedes_catalog_read(monkeypatch, path):
    identity = RequestIdentity(
        "restricted", allowed_capabilities=frozenset({"kater.profiles.list"})
    )
    monkeypatch.setattr(fabric_routes, "get_request_identity", lambda: identity)
    forbidden = Mock(side_effect=AssertionError("Restricted catalog must not be evaluated"))
    monkeypatch.setattr(fabric_catalog, "catalog_payload", forbidden)
    response = response_for(path)
    assert response.status == 403
    assert response.payload["code"] == "capability_denied"
    forbidden.assert_not_called()


def test_hidden_connection_detail_is_not_found():
    response = response_for("/api/connections/private-source:default")
    assert response.status == 404
    assert response.payload["code"] == "not_found"


def test_private_only_extension_does_not_reappear_as_implicit_plugin(
    monkeypatch, clean_kater_state
):
    clean_kater_state["PLUGINS"] = ()
    private = profiles.all_tool_sources()[-1]
    clean_kater_state["TOOL_SOURCES"] = (private,)
    monkeypatch.setattr(profiles, "_BUILTIN_TOOL_SOURCES", ())
    monkeypatch.setattr(fabric_catalog, "TOOL_SOURCES", ())
    assert [item.id for item in fabric_catalog.plugin_items()] == ["plugin:kater-core"]
