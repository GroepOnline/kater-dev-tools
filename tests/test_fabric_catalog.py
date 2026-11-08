from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

from kater import authgate, fabric_catalog
from kater.api import Request, fabric_routes, handle
from kater.authgate import RequestIdentity
from kater.connectors.models import (
    AuthBindingKind,
    AuthBindingRef,
    ConnectorRecord,
    ConnectorTransport,
    ConnectorType,
)
from kater.control_plane.contexts import ContextRecord
from kater.fabric_catalog import CatalogKind, catalog_payload, plugin_items
from kater.profiles import McpServerConfig, RiskLevel, ToolSource, Transport

CATALOG_PATHS = (
    "/api/fabric",
    "/api/toolkits",
    "/api/integrations",
    "/api/connections",
    "/api/actions",
    "/api/plugins",
    "/api/mcp/catalog",
)


def _request(
    path: str,
    query: dict[str, list[str]] | None = None,
    headers: dict[str, str] | None = None,
) -> Request:
    return Request(
        method="GET",
        path=path,
        query=query or {},
        headers=headers or {},
        raw_body=b"",
        client_ip="127.0.0.1",
        base_url="http://localhost:9091",
    )


@pytest.mark.parametrize("path", CATALOG_PATHS)
@pytest.mark.parametrize("allowed", [frozenset(), frozenset({"kater.profiles.list"})])
@pytest.mark.parametrize("profile", ["", "core", "ops"])
def test_restricted_catalog_never_reads_metadata(monkeypatch, path, allowed, profile) -> None:
    identity = RequestIdentity(principal_id="restricted", allowed_capabilities=allowed)
    monkeypatch.setattr(fabric_routes, "get_request_identity", lambda: identity)

    def unexpected_catalog_read(**kwargs):
        pytest.fail("A restricted request must not evaluate catalog configuration")

    monkeypatch.setattr(fabric_catalog, "catalog_payload", unexpected_catalog_read)
    response = handle(_request(path, {"profile": [profile], "q": ["github"], "kind": ["mcp"]}))
    assert response.status == 403
    assert response.payload["code"] == "capability_denied"


@pytest.mark.parametrize("path", CATALOG_PATHS)
@pytest.mark.parametrize("identity", [RequestIdentity(), RequestIdentity("admin", "context")])
def test_unrestricted_catalog_retains_discovery(monkeypatch, path, identity) -> None:
    monkeypatch.setattr(fabric_routes, "get_request_identity", lambda: identity)
    response = handle(_request(path))
    assert response.status == 200
    assert "counts" in response.payload


@pytest.mark.parametrize("path", CATALOG_PATHS)
def test_catalog_invalid_context_is_not_downgraded_to_anonymous(path) -> None:
    response = handle(_request(path, headers={"x-kater-context": "invalid-context"}))
    assert response.status == 401


@pytest.mark.parametrize("path", CATALOG_PATHS)
def test_catalog_uses_authenticated_identity_even_if_token_expires(monkeypatch, path) -> None:
    record = ContextRecord(
        context_id="expiring-context",
        principal_id="restricted-reader",
        scopes=frozenset(),
        created_at=datetime.now(UTC),
        allowed_capabilities=frozenset({"kater.profiles.list"}),
    )
    verify = Mock(side_effect=[record, None])
    catalog_read = Mock(side_effect=AssertionError("Restricted catalog must not be read"))
    monkeypatch.setattr(authgate, "verify_token", verify)
    monkeypatch.setattr(fabric_catalog, "catalog_payload", catalog_read)
    try:
        response = handle(_request(path, headers={"x-kater-context": "expiring.token"}))
        assert response.status == 403
        verify.assert_called_once_with("expiring.token")
        catalog_read.assert_not_called()
    finally:
        authgate.set_request_identity(None)


def test_signed_restricted_context_cannot_bypass_catalog_with_profile(
    monkeypatch, tmp_path
) -> None:
    from kater.control_plane import contexts
    from kater.control_plane import tokens as context_tokens

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KATER_CONTEXT_TOKEN_SECRET", "catalog-test-signing-secret")
    contexts.reset_cache()
    context_tokens.reset_token_secret_cache()
    try:
        context = contexts.create_context(
            principal_id="catalog-reader", allowed_capabilities=["kater.profiles.list"]
        )
        token = context_tokens.issue_token(context, ttl_seconds=120)
        headers = {"x-kater-context": token}
        for path in CATALOG_PATHS:
            assert handle(_request(path, {"profile": ["core"]}, headers)).status == 403
        response = handle(_request("/api/capabilities", headers=headers))
        assert response.status == 200
        assert {item["capability_id"] for item in response.payload["capabilities"]} == {
            "kater.profiles.list"
        }
    finally:
        contexts.reset_cache()
        context_tokens.reset_token_secret_cache()


@pytest.mark.parametrize("path", CATALOG_PATHS)
def test_catalog_openapi_describes_filters_and_restriction(path) -> None:
    operation = fabric_routes.FABRIC_OPENAPI_PATHS[path]["get"]
    parameters = {parameter["name"] for parameter in operation["parameters"]}
    assert parameters == ({"q", "profile", "kind"} if path == "/api/fabric" else {"q", "profile"})
    assert "403" in operation["responses"]


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (
            "https://user:secret@example.test:8443/private?token=secret#secret",
            "https://example.test:8443",
        ),
        ("http://[2001:db8::1]:8080/private", "http://[2001:db8::1]:8080"),
        ("https://example.test/path", "https://example.test"),
        ("https://münich.example/path", "https://xn--mnich-kva.example"),
        (None, None),
        ("", None),
        ("file:///private/secret", None),
        ("javascript:secret", None),
        ("https://example.test:notaport/private", None),
        ("https://example.test:65536/private", None),
        ("https://[invalid/private", None),
        ("https:///private", None),
        ("https://exa mple.test/private", None),
        ("https://example.test\n/private", None),
        ("https://example.test%2fsecret/private", None),
        ("https://example.test\\secret/private", None),
    ],
)
def test_catalog_url_projection_is_origin_only(value, expected) -> None:
    assert fabric_catalog._catalog_url_metadata("endpoint", value) == (
        {"endpoint": expected} if expected else {}
    )


def test_catalog_never_serializes_provider_launch_or_auth_configuration(monkeypatch) -> None:
    secret = "synthetic-credential-canary"
    endpoint = f"https://{secret}:{secret}@example.test/{secret}?key={secret}#{secret}"
    source = ToolSource(
        name="fixture-provider",
        description="Synthetic provider",
        transport=Transport.HTTP,
        risk=RiskLevel.LOW,
        homepage=endpoint,
        mcp=McpServerConfig(
            command=secret,
            args=[secret],
            url=endpoint,
            env_template={"API_KEY": secret},
            headers_template={"Authorization": secret},
        ),
    )
    records = {
        kind.value: ConnectorRecord(
            id=kind.value,
            display_name=f"Fixture {kind.value}",
            type=kind,
            version="1",
            transport=ConnectorTransport(kind="http", endpoint=endpoint),
            auth_binding=AuthBindingRef(AuthBindingKind.ENV, secret),
        )
        for kind in (ConnectorType.MCP, ConnectorType.BRIDGE)
    }
    monkeypatch.setattr(fabric_catalog, "visible_tool_sources", lambda: (source,))
    monkeypatch.setattr(fabric_catalog, "_connector_map", lambda: records)
    monkeypatch.setattr(fabric_catalog, "source_is_configured", lambda *args: False)
    monkeypatch.setattr(fabric_catalog, "binding_is_satisfied", lambda *args, **kwargs: False)
    payload = catalog_payload()
    serialized = json.dumps(payload)
    assert secret not in serialized
    for forbidden in ("auth_binding_ref", "env_template", "headers_template", "command", "args"):
        assert f'"{forbidden}"' not in serialized
    assert payload["toolkits"][0]["metadata"]["homepage"] == "https://example.test"
    assert len(payload["mcp"]) == 3
    for item in payload["mcp"]:
        assert item["metadata"]["endpoint"] == "https://example.test"
        assert set(item["metadata"]) <= {"endpoint", "connector_type"}


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
