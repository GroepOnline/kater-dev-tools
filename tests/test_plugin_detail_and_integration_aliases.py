from __future__ import annotations

from kater.api import ROUTER, handle
from kater.api.models import Request
from kater.authgate import RequestIdentity
from kater.openapi_spec import generate_spec
from tests._rest import call


def _get(path: str) -> Request:
    return Request(
        method="GET",
        path=path,
        query={},
        headers={},
        raw_body=b"",
        client_ip="127.0.0.1",
        base_url="http://localhost:9091",
    )


def _route(method: str, pattern: str):
    return next(
        route for route in ROUTER._routes if route.method == method and route.pattern == pattern
    )


def test_plugin_detail_returns_core_manifest() -> None:
    response = handle(_get("/api/plugins/kater-core"))
    assert response.status == 200
    plugin = response.payload["plugin"]
    assert plugin["id"] == "plugin:kater-core"
    assert plugin["plugin_id"] == "kater-core"
    assert plugin["kind"] == "plugin"
    assert "github" in plugin["metadata"]["toolkits"]


def test_plugin_detail_unknown_is_not_found() -> None:
    response = handle(_get("/api/plugins/missing-plugin"))
    assert response.status == 404
    assert response.payload["code"] == "not_found"


def test_plugin_detail_restricted_identity_is_denied(monkeypatch) -> None:
    from kater.api import fabric_routes

    identity = RequestIdentity(principal_id="restricted", allowed_capabilities=frozenset())
    monkeypatch.setattr(fabric_routes, "get_request_identity", lambda: identity)
    response = handle(_get("/api/plugins/kater-core"))
    assert response.status == 403
    assert response.payload["code"] == "capability_denied"


def test_integration_routes_alias_mcp_server_handlers() -> None:
    pairs = (
        ("POST", "/api/integrations/{name}/credentials", "/api/mcp/servers/{name}/credentials"),
        ("POST", "/api/integrations/{name}/oauth/start", "/api/mcp/servers/{name}/oauth/start"),
        ("GET", "/api/integrations/{name}/connections", "/api/mcp/servers/{name}/connections"),
        (
            "DELETE",
            "/api/integrations/{name}/connections/{conn_id}",
            "/api/mcp/servers/{name}/connections/{conn_id}",
        ),
    )
    for method, alias, canonical in pairs:
        assert _route(method, alias).handler is _route(method, canonical).handler


def test_integration_connection_list_matches_mcp_route() -> None:
    mcp = call("GET", "/api/mcp/servers/github/connections")
    alias = call("GET", "/api/integrations/github/connections")
    assert mcp.status == 200
    assert alias.status == 200
    assert alias.payload == mcp.payload
    assert "connections" in alias.payload


def test_integration_alias_unknown_server_matches_mcp_404() -> None:
    mcp = call("GET", "/api/mcp/servers/not-a-server/connections")
    alias = call("GET", "/api/integrations/not-a-server/connections")
    assert mcp.status == 404
    assert alias.payload == mcp.payload


def test_openapi_documents_plugin_detail_and_integration_aliases() -> None:
    paths = generate_spec()["paths"]
    assert "/api/plugins/{plugin_id}" in paths
    assert "404" in paths["/api/plugins/{plugin_id}"]["get"]["responses"]
    for path in (
        "/api/integrations/{name}/credentials",
        "/api/integrations/{name}/oauth/start",
        "/api/integrations/{name}/connections",
        "/api/integrations/{name}/connections/{conn_id}",
    ):
        assert paths[path] is paths[path.replace("/api/integrations/", "/api/mcp/servers/")]
