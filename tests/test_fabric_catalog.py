from __future__ import annotations

from kater.api import Request, handle
from kater.fabric_catalog import CatalogKind, catalog_payload, plugin_items


def test_toolkit_catalog_exposes_existing_sources() -> None:
    payload = catalog_payload(kind=CatalogKind.TOOLKIT)

    names = {item["name"] for item in payload["toolkits"]}
    assert "github" in names
    assert "linear" in names
    assert payload["counts"]["toolkit"] == len(payload["toolkits"])
    assert payload["integrations"] == []
    assert payload["plugins"] == []
    assert payload["mcp"] == []


def test_plugin_catalog_contains_core_bundle() -> None:
    plugins = plugin_items()

    core = next(item for item in plugins if item.id == "plugin:kater-core")
    assert "github" in core.capabilities
    assert core.status == "installed"
    assert core.origin == "builtin"


def test_fabric_api_can_filter_mcp_surface() -> None:
    response = handle(
        Request(
            method="GET",
            path="/api/fabric",
            query={"kind": ["mcp"]},
            headers={},
            raw_body=b"",
            client_ip="127.0.0.1",
            base_url="http://localhost:9091",
        )
    )

    assert response.status == 200
    assert response.payload is not None
    assert response.payload["toolkits"] == []
    assert response.payload["integrations"] == []
    assert response.payload["plugins"] == []
    assert response.payload["counts"]["mcp"] > 0


def test_fabric_api_rejects_unknown_kind() -> None:
    response = handle(
        Request(
            method="GET",
            path="/api/fabric",
            query={"kind": ["wat"]},
            headers={},
            raw_body=b"",
            client_ip="127.0.0.1",
            base_url="http://localhost:9091",
        )
    )

    assert response.status == 400
    assert response.payload == {"error": "unknown catalog kind: wat"}
