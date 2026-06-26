from __future__ import annotations

from typing import Any

OPENAPI_VERSION = "3.1.0"
API_TITLE = "Kater MCP Gateway API"
API_VERSION = "0.5.0"
DEFAULT_SERVER = "http://localhost:9091"

_JSON = {"application/json": {}}


def _ref(name: str) -> dict[str, str]:
    return {"$ref": f"#/components/schemas/{name}"}


def _response(
    summary: str,
    schema: dict[str, Any],
    description: str = "OK",
) -> dict[str, Any]:
    return {
        "summary": summary,
        "responses": {
            "200": {
                "description": description,
                "content": {"application/json": {"schema": schema}},
            }
        },
    }


def _ok() -> dict[str, Any]:
    return {
        "description": "Successful operation",
        "content": {"application/json": {"schema": {"type": "object"}}},
    }


def _error_ref() -> dict[str, Any]:
    return {
        "description": "Error response",
        "content": {"application/json": {"schema": _ref("Error")}},
    }


def _build_paths() -> dict[str, Any]:
    paths: dict[str, Any] = {}

    paths["/health"] = {
        "get": _response(
            "Health check",
            _ref("Health"),
            "Service health and version information.",
        )
    }

    paths["/api/profiles"] = {
        "get": _response(
            "List profiles",
            _ref("Profiles"),
            "Available tool profiles.",
        )
    }

    paths["/api/tools"] = {
        "get": {
            "summary": "List tools",
            "parameters": [_profile_query()],
            "responses": {"200": _ok()},
        }
    }

    paths["/api/adapters"] = {
        "get": {
            "summary": "List adapters",
            "parameters": [_profile_query()],
            "responses": {"200": _ok()},
        }
    }

    paths["/api/doctor"] = {
        "get": _response(
            "Run diagnostics",
            _ref("DoctorReport"),
            "Diagnostic findings and fix actions.",
        )
    }

    paths["/api/chains"] = {
        "get": _response(
            "List chains",
            _ref("Chains"),
            "Defined chains for the active profile.",
        )
    }

    paths["/api/chains/run"] = {
        "post": {
            "summary": "Run a chain",
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": _ref("ChainRunRequest")}},
            },
            "responses": {
                "200": {
                    "description": "Chain executed.",
                    "content": {"application/json": {"schema": _ref("ChainRunResult")}},
                },
                "404": _error_ref(),
            },
        }
    }

    paths["/api/mcp/servers"] = {
        "get": _response(
            "List MCP servers",
            _ref("McpServerList"),
            "All known MCP servers.",
        )
    }

    paths["/api/mcp/servers/{name}"] = {
        "get": {
            "summary": "Get MCP server detail",
            "parameters": [_name_param()],
            "responses": {
                "200": {
                    "description": "Server detail.",
                    "content": {"application/json": {"schema": _ref("McpServer")}},
                },
                "404": _error_ref(),
            },
        }
    }

    paths["/api/mcp/servers/{name}/{action}"] = {
        "post": {
            "summary": "Enable, disable, or toggle a server",
            "parameters": [_name_param(), _action_param()],
            "responses": {
                "200": {
                    "description": "Server state updated.",
                    "content": {"application/json": {"schema": _ref("ServerToggle")}},
                },
                "404": _error_ref(),
            },
        }
    }

    paths["/api/settings"] = {
        "get": _response("Get settings", _ref("Settings")),
        "post": {
            "summary": "Update settings",
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": _ref("SettingsUpdate")}},
            },
            "responses": {
                "200": {
                    "description": "Updated settings.",
                    "content": {"application/json": {"schema": _ref("Settings")}},
                }
            },
        },
    }

    paths["/api/status"] = {
        "get": _response(
            "Instance status overview",
            _ref("Status"),
            "High-level instance status.",
        )
    }

    paths["/api/telemetry"] = {
        "get": _response(
            "Raw telemetry events",
            _ref("Telemetry"),
            "Raw recorded telemetry events.",
        )
    }

    paths["/api/evals"] = {
        "get": _response(
            "Aggregated eval metrics",
            _ref("Evals"),
            "Aggregated evaluation metrics.",
        )
    }

    paths["/api/deploy"] = {
        "get": _response(
            "List deployment formats",
            _ref("DeployFormats"),
            "Supported deployment output formats.",
        )
    }

    paths["/api/deploy/{format}"] = {
        "get": {
            "summary": "Render deployment config",
            "parameters": [_format_param()],
            "responses": {
                "200": _ok(),
                "404": _error_ref(),
            },
        }
    }

    paths["/api/catalog"] = {
        "get": {
            "summary": "Search and filter MCP servers",
            "parameters": [
                {
                    "name": "q",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Free-text search query.",
                },
                {
                    "name": "profile",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Filter by profile membership.",
                },
                {
                    "name": "transport",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Filter by transport type.",
                },
                {
                    "name": "risk",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Filter by risk level.",
                },
            ],
            "responses": {
                "200": {
                    "description": "Matching servers.",
                    "content": {"application/json": {"schema": _ref("McpServerList")}},
                }
            },
        }
    }

    paths["/api/spec"] = {
        "get": {
            "summary": "This OpenAPI specification",
            "responses": {
                "200": {
                    "description": "OpenAPI 3.1 document.",
                    "content": _JSON,
                }
            },
        }
    }

    paths["/api/export"] = {
        "get": _response(
            "Export sanitized config",
            {"type": "object"},
            "Sanitized instance configuration.",
        )
    }

    paths["/api/tunnel/{provider}/start"] = {
        "post": {
            "summary": "Start a tunnel for the given provider",
            "parameters": [_provider_param()],
            "responses": {
                "200": _ok(),
                "400": _error_ref(),
            },
        }
    }

    return paths


def _profile_query() -> dict[str, Any]:
    return {
        "name": "profile",
        "in": "query",
        "required": False,
        "schema": {"type": "string", "default": "core"},
        "description": "Profile to scope the response.",
    }


def _name_param() -> dict[str, Any]:
    return {
        "name": "name",
        "in": "path",
        "required": True,
        "schema": {"type": "string"},
        "description": "Server name.",
    }


def _action_param() -> dict[str, Any]:
    return {
        "name": "action",
        "in": "path",
        "required": True,
        "schema": {"type": "string", "enum": ["enable", "disable", "toggle"]},
        "description": "Action to apply to the server.",
    }


def _format_param() -> dict[str, Any]:
    return {
        "name": "format",
        "in": "path",
        "required": True,
        "schema": {"type": "string"},
        "description": "Deployment output format.",
    }


def _provider_param() -> dict[str, Any]:
    return {
        "name": "provider",
        "in": "path",
        "required": True,
        "schema": {"type": "string", "enum": ["cloudflare", "tailscale"]},
        "description": "Tunnel provider.",
    }


def _build_schemas() -> dict[str, Any]:
    return {
        "Health": {
            "type": "object",
            "required": ["status", "version", "auth_mode"],
            "properties": {
                "status": {"type": "string"},
                "version": {"type": "string"},
                "auth_mode": {"type": "string"},
            },
        },
        "Profiles": {
            "type": "object",
            "required": ["profiles"],
            "properties": {"profiles": {"type": "array", "items": {"type": "string"}}},
        },
        "Chains": {
            "type": "object",
            "required": ["chains"],
            "properties": {"chains": {"type": "array", "items": {"type": "object"}}},
        },
        "ChainRunRequest": {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {"type": "string"},
                "profile": {"type": "string", "default": "core"},
            },
        },
        "ChainRunResult": {
            "type": "object",
            "properties": {
                "chain": {"type": "string"},
                "description": {"type": "string"},
                "profile": {"type": "string"},
                "steps": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step": {"type": "integer"},
                            "tool": {"type": "string"},
                            "reason": {"type": "string"},
                        },
                    },
                },
            },
        },
        "McpServer": {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "description": {"type": "string"},
                "transport": {"type": "string"},
                "risk": {"type": "string"},
                "profiles": {"type": "array", "items": {"type": "string"}},
                "env_required": {"type": "array", "items": {"type": "string"}},
                "env_configured": {"type": "boolean"},
                "homepage": {"type": ["string", "null"]},
                "mcp": {},
                "enabled": {"type": "boolean"},
            },
        },
        "McpServerList": {
            "type": "object",
            "required": ["total", "servers"],
            "properties": {
                "total": {"type": "integer"},
                "servers": {
                    "type": "array",
                    "items": {"$ref": "#/components/schemas/McpServer"},
                },
            },
        },
        "ServerToggle": {
            "type": "object",
            "required": ["name", "enabled"],
            "properties": {
                "name": {"type": "string"},
                "enabled": {"type": "boolean"},
            },
        },
        "AuthConfig": {
            "type": "object",
            "properties": {
                "mode": {"type": "string"},
                "api_keys": {"type": "array", "items": {"type": "string"}},
                "oauth_issuer": {"type": ["string", "null"]},
                "oauth_audience": {"type": ["string", "null"]},
                "oauth_jwks_url": {"type": ["string", "null"]},
            },
        },
        "Settings": {
            "type": "object",
            "properties": {
                "version": {"type": "integer"},
                "default_profile": {"type": "string"},
                "auth": {"$ref": "#/components/schemas/AuthConfig"},
                "cors_origins": {"type": "array", "items": {"type": "string"}},
                "rate_limit_per_min": {"type": "integer"},
                "api_port": {"type": "integer"},
                "mcp_port": {"type": "integer"},
                "storage_backend": {"type": "string"},
                "db_path": {"type": "string"},
            },
        },
        "SettingsUpdate": {
            "type": "object",
            "additionalProperties": True,
            "description": "Partial settings patch.",
            "properties": {
                "auth": {"$ref": "#/components/schemas/AuthConfig"},
                "cors_origins": {"type": "array", "items": {"type": "string"}},
                "rate_limit_per_min": {"type": "integer"},
                "default_profile": {"type": "string"},
            },
        },
        "DoctorReport": {
            "type": "object",
            "required": ["profiles", "sources"],
            "properties": {
                "profiles": {"type": "array", "items": {"type": "string"}},
                "sources": {"type": "array", "items": {"type": "object"}},
                "findings": {"type": "array", "items": {"type": "object"}},
                "fix_actions": {"type": "array", "items": {"type": "object"}},
            },
        },
        "Status": {
            "type": "object",
            "additionalProperties": True,
            "description": "Instance status overview.",
        },
        "Telemetry": {
            "type": "object",
            "required": ["total", "events"],
            "properties": {
                "total": {"type": "integer"},
                "events": {"type": "array", "items": {"type": "object"}},
            },
        },
        "Evals": {
            "type": "object",
            "additionalProperties": True,
            "description": "Aggregated evaluation metrics.",
        },
        "DeployFormats": {
            "type": "object",
            "required": ["formats"],
            "properties": {"formats": {"type": "array", "items": {"type": "string"}}},
        },
        "Error": {
            "type": "object",
            "required": ["error"],
            "properties": {"error": {"type": "string"}},
        },
    }


def generate_spec() -> dict[str, Any]:
    try:
        from kater import __version__ as api_version
    except Exception:
        api_version = API_VERSION
    return {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": API_TITLE,
            "version": api_version,
            "description": (
                "REST API for the Kater MCP Gateway. Provides profiles, tools, "
                "adapters, chains, MCP server management, diagnostics, "
                "telemetry, and deployment rendering."
            ),
            "license": {"name": "MIT"},
        },
        "servers": [{"url": DEFAULT_SERVER, "description": "Local gateway"}],
        "paths": _build_paths(),
        "components": {"schemas": _build_schemas()},
    }
