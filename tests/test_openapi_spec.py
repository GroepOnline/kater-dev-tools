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
