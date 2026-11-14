"""Tests for openapi_spec.py — the OpenAPI 3.1 schema generator.

Covers: generate_spec, _build_paths, _build_schemas, schema correctness,
required fields, and drift-guard (all ROUTER routes must appear in paths).
"""

from __future__ import annotations

from kater.openapi_spec import (
    API_TITLE,
    API_VERSION,
    OPENAPI_VERSION,
    _build_paths,
    _build_schemas,
    generate_spec,
)


class TestGenerateSpec:
    def test_returns_valid_openapi_structure(self):
        spec = generate_spec()
        assert spec["openapi"] == OPENAPI_VERSION
        assert spec["info"]["title"] == API_TITLE
        assert spec["info"]["version"] == API_VERSION
        assert spec["info"]["license"]["name"] == "MIT"

    def test_has_paths_and_schemas(self):
        spec = generate_spec()
        assert "paths" in spec
        assert "components" in spec
        assert "schemas" in spec["components"]

    def test_servers_defined(self):
        spec = generate_spec()
        assert len(spec["servers"]) >= 1
        assert "url" in spec["servers"][0]


class TestBuildPaths:
    def test_health_endpoint_exists(self):
        paths = _build_paths()
        assert "/health" in paths
        assert "get" in paths["/health"]

    def test_health_live_endpoint_exists(self):
        paths = _build_paths()
        assert "/health/live" in paths
        assert "get" in paths["/health/live"]

    def test_health_ready_endpoint_exists(self):
        paths = _build_paths()
        assert "/health/ready" in paths
        assert "get" in paths["/health/ready"]

    def test_studio_routes_exist_with_static_content_types(self):
        paths = _build_paths()
        assert "text/html" in paths["/studio"]["get"]["responses"]["200"]["content"]
        assert (
            "text/javascript"
            in paths["/studio/assets/studio.js"]["get"]["responses"]["200"]["content"]
        )
        assert (
            "text/css"
            in paths["/studio/assets/studio.css"]["get"]["responses"]["200"]["content"]
        )

    def test_profiles_endpoint_exists(self):
        paths = _build_paths()
        assert "/api/profiles" in paths

    def test_tools_endpoint_exists(self):
        paths = _build_paths()
        assert "/api/tools" in paths

    def test_authorize_endpoint_exists(self):
        paths = _build_paths()
        assert "/authorize" in paths

    def test_token_endpoint_exists(self):
        paths = _build_paths()
        assert "/token" in paths

    def test_register_endpoint_exists(self):
        paths = _build_paths()
        assert "/register" in paths

    def test_well_known_exists(self):
        paths = _build_paths()
        well_known = [p for p in paths if p.startswith("/.well-known")]
        assert len(well_known) > 0

    def test_all_routes_have_responses(self):
        paths = _build_paths()
        for path, methods in paths.items():
            for method, spec in methods.items():
                if method in ("get", "post", "put", "delete", "patch", "head"):
                    assert "responses" in spec, f"{method.upper()} {path} missing responses"

    def test_browser_paths_exist(self):
        paths = _build_paths()
        assert "get" in paths["/api/browser/providers"]
        assert {"get", "post", "delete"} <= set(paths["/api/browser/sessions"])
        assert {"get", "delete"} <= set(paths["/api/browser/sessions/{session_id}"])
        assert "post" in paths["/api/browser/sessions/{session_id}/act"]
        assert "post" in paths["/api/browser/sessions/{session_id}/screenshot"]
        assert "get" in paths["/api/browser/stats"]

    def test_automations_paths_exist(self):
        paths = _build_paths()
        assert {"get", "post"} <= set(paths["/api/automations"])
        assert {"get", "delete"} <= set(paths["/api/automations/{id}"])
        for suffix in ("run", "enable", "disable"):
            assert "post" in paths[f"/api/automations/{{id}}/{suffix}"]

    def test_catalog_triggers_path_exists(self):
        paths = _build_paths()
        assert "/api/catalog/{name}/triggers" in paths
        assert "get" in paths["/api/catalog/{name}/triggers"]


class TestBuildSchemas:
    def test_has_schemas(self):
        schemas = _build_schemas()
        assert len(schemas) > 0

    def test_schemas_are_valid_structure(self):
        schemas = _build_schemas()
        for name, schema in schemas.items():
            assert "type" in schema or "$ref" in schema or "properties" in schema, (
                f"Schema {name} has no type/ref/properties"
            )

    def test_trigger_ref_schema_exists(self):
        schemas = _build_schemas()
        assert "TriggerRef" in schemas
        ref = schemas["TriggerRef"]
        assert ref["type"] == "object"
        assert "name" in ref["properties"]
        assert "cadence" in ref["properties"]
        assert "realtime" in ref["properties"]["cadence"]["enum"]
        assert "poll" in ref["properties"]["cadence"]["enum"]

    def test_mcp_server_schema_documents_triggers_and_connection_count(self):
        from kater.openapi_spec import generate_spec

        spec = generate_spec()
        props = spec["components"]["schemas"]["McpServer"]["properties"]
        for key in ("triggers", "connection_count", "trigger_count"):
            assert key in props, f"{key} missing from McpServer schema: {list(props)}"
        assert props["connection_count"]["type"] == "integer"
        assert props["triggers"]["type"] == "array"
        assert props["triggers"]["items"]["$ref"] == "#/components/schemas/TriggerRef"
        assert props["trigger_count"]["type"] == "integer"


class TestDriftGuard:
    """Verify that every route registered in the ROUTER appears in the spec."""

    def test_all_router_routes_in_spec(self):
        from kater.api import ROUTER

        paths = _build_paths()
        for route in ROUTER._routes:
            pattern = route.pattern
            # Normalize: strip trailing slash for comparison.
            normalized = pattern.rstrip("/") or "/"
            assert normalized in paths, f"Route {route.method} {pattern} not in OpenAPI spec"


def test_catalog_request_paths_exist() -> None:
    from kater.openapi_spec import generate_spec

    spec = generate_spec()
    paths = spec["paths"]
    assert "/api/catalog/request" in paths
    assert "/api/catalog/requests" in paths
    post = paths["/api/catalog/request"]["post"]
    assert "201" in post["responses"]
    get = paths["/api/catalog/requests"]["get"]
    assert "200" in get["responses"]
    assert "403" in get["responses"]


def test_toolkit_request_schemas_documented() -> None:
    from kater.openapi_spec import generate_spec

    spec = generate_spec()
    schemas = spec["components"]["schemas"]
    expected = (
        "ToolkitRequest",
        "ToolkitRequestAck",
        "ToolkitRequestList",
        "ToolkitRequestListItem",
    )
    for name in expected:
        assert name in schemas, f"{name} missing"
    assert schemas["ToolkitRequest"]["required"] == ["name"]
    assert schemas["ToolkitRequest"]["properties"]["name"]["maxLength"] == 64
