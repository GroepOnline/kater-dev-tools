"""HTTP fabric routes: capability discovery and remote contexts.

Importing this module registers endpoints into ``models.ROUTER`` via
``@route``. Keep this file free of computer/browser handlers so parallel
agents can own those surfaces without merge fights.
"""

from __future__ import annotations

from typing import Any

from kater.api.models import Request, Response, route
from kater.authgate import RequestIdentity, capability_allowed, resolve_request_identity
from kater.capabilities.audit import query_capability_audit
from kater.capabilities.discovery import discover
from kater.capabilities.models import CapabilityManifest, DiscoveryContext, RiskClass
from kater.capabilities.registry import get_default_registry
from kater.control_plane import contexts as remote_contexts
from kater.control_plane.tokens import token_expires_at

# OpenAPI path fragments merged by ``openapi_spec._build_paths``.
FABRIC_OPENAPI_PATHS: dict[str, Any] = {
    "/api/capabilities": {
        "get": {
            "summary": "Discover capabilities",
            "parameters": [
                {
                    "name": "profile",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string", "default": "core"},
                    "description": "Comma-separated profile ids to match.",
                },
                {
                    "name": "intent",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                    "description": "Free-text task intent used to boost matches.",
                },
                {
                    "name": "max_risk",
                    "in": "query",
                    "required": False,
                    "schema": {
                        "type": "string",
                        "default": "external_write",
                        "enum": [r.value for r in RiskClass],
                    },
                },
            ],
            "responses": {
                "200": {
                    "description": "Discoverable capabilities for the context.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "400": {
                    "description": "Invalid query",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                    },
                },
            },
        }
    },
    "/api/capabilities/{capability_id}": {
        "get": {
            "summary": "Get a capability manifest",
            "parameters": [
                {
                    "name": "capability_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
            "responses": {
                "200": {
                    "description": "Capability manifest.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "404": {
                    "description": "Not found",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                    },
                },
            },
        }
    },
    "/api/contexts": {
        "get": {
            "summary": "List remote contexts",
            "parameters": [
                {
                    "name": "principal_id",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                },
                {
                    "name": "include_revoked",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "boolean", "default": False},
                },
            ],
            "responses": {
                "200": {
                    "description": "Remote contexts.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                }
            },
        },
        "post": {
            "summary": "Create a remote context",
            "requestBody": {
                "required": True,
                "content": {"application/json": {"schema": {"type": "object"}}},
            },
            "responses": {
                "201": {
                    "description": "Created context.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "400": {
                    "description": "Invalid body",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                    },
                },
            },
        },
    },
    "/api/contexts/{context_id}": {
        "get": {
            "summary": "Get a remote context",
            "parameters": [
                {
                    "name": "context_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
            "responses": {
                "200": {
                    "description": "Remote context.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "404": {
                    "description": "Not found",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                    },
                },
            },
        },
        "delete": {
            "summary": "Revoke a remote context",
            "parameters": [
                {
                    "name": "context_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
            "responses": {
                "200": {
                    "description": "Revoked context.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "404": {
                    "description": "Not found",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                    },
                },
            },
        },
    },
    "/api/contexts/{context_id}/revoke": {
        "post": {
            "summary": "Revoke a remote context",
            "parameters": [
                {
                    "name": "context_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
            "responses": {
                "200": {
                    "description": "Revoked context.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "404": {
                    "description": "Not found",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                    },
                },
            },
        }
    },
    "/api/contexts/{context_id}/token": {
        "post": {
            "summary": "Issue a signed context token",
            "parameters": [
                {
                    "name": "context_id",
                    "in": "path",
                    "required": True,
                    "schema": {"type": "string"},
                }
            ],
            "requestBody": {
                "required": False,
                "content": {"application/json": {"schema": {"type": "object"}}},
            },
            "responses": {
                "200": {
                    "description": "Signed token and expiry.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                },
                "400": {
                    "description": "Invalid body",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                    },
                },
                "404": {
                    "description": "Not found or inactive",
                    "content": {
                        "application/json": {"schema": {"$ref": "#/components/schemas/Error"}}
                    },
                },
            },
        }
    },
    "/api/audit/capabilities": {
        "get": {
            "summary": "List recent capability invoke audit rows",
            "parameters": [
                {
                    "name": "limit",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "integer", "default": 100},
                },
                {
                    "name": "capability_id",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                },
                {
                    "name": "context_id",
                    "in": "query",
                    "required": False,
                    "schema": {"type": "string"},
                },
            ],
            "responses": {
                "200": {
                    "description": "Recent capability audit rows.",
                    "content": {"application/json": {"schema": {"type": "object"}}},
                }
            },
        }
    },
}


def _csv_set(raw: str | None) -> frozenset[str]:
    """
    Convert a comma-separated string into a set of trimmed, non-empty values.

    Parameters:
        raw (str | None): The comma-separated input string.

    Returns:
        frozenset[str]: The unique, trimmed values, or an empty set when the input is empty.
    """
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _truthy(raw: str | None) -> bool:
    """Determine whether a string represents a true value.

    Parameters:
        raw (str | None): The value to interpret.

    Returns:
        bool: `true` if the trimmed, case-insensitive value is "1", "true", "yes", or "on"; `false`
            otherwise.
    """
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _identity_owns_context(identity: RequestIdentity, record: Any) -> bool:
    """
    Determine whether an identity may access a remote-context record.

    Parameters:
        identity (RequestIdentity): Identity requesting access.
        record (Any): Remote-context record to check.

    Returns:
        bool: `true` if the identity is unrestricted or owns the record, `false` otherwise.
    """
    if identity.principal_id is None:
        return True
    return record.principal_id == identity.principal_id


def _discovered_payload(item: Any) -> dict[str, Any]:
    """
    Builds the serialized payload for a discovered capability.

    Parameters:
        item (Any): Discovered capability data to serialize.

    Returns:
        dict[str, Any]: Capability identifiers, metadata, schemas, required scopes, approval status,
            and health status.
    """
    return {
        "capability_id": item.capability_id,
        "version": item.version,
        "digest": item.digest,
        "description": item.description,
        "risk_class": item.risk_class.value,
        "lifecycle_state": item.lifecycle_state.value,
        "required_scopes": sorted(item.required_scopes),
        "input_schema": item.input_schema,
        "approval_expected": item.approval_expected,
        "health_ok": item.health_ok,
    }


def _manifest_payload(manifest: CapabilityManifest) -> dict[str, Any]:
    """
    Build the API payload for a capability manifest.

    Parameters:
        manifest (CapabilityManifest): Capability manifest to serialize.

    Returns:
        dict[str, Any]: Manifest fields formatted for an API response.
    """
    return {
        "capability_id": manifest.capability_id,
        "package_id": manifest.package_id,
        "publisher_id": manifest.publisher_id,
        "version": manifest.version,
        "digest": manifest.digest,
        "transport": manifest.transport.value,
        "description": manifest.description,
        "input_schema": manifest.input_schema,
        "output_schema": manifest.output_schema,
        "required_scopes": sorted(manifest.required_scopes),
        "risk_class": manifest.risk_class.value,
        "data_classification": manifest.data_classification,
        "profiles": sorted(manifest.profiles),
        "healthcheck_capability_id": manifest.healthcheck_capability_id,
        "lifecycle_state": manifest.lifecycle_state.value,
        "rollback_version": manifest.rollback_version,
        "network_targets": list(manifest.network_targets),
        "tags": sorted(manifest.tags),
    }


@route("GET", "/api/capabilities")
def _capabilities_discover(req: Request) -> Response:
    """
    Discover capabilities matching the requested profiles, intent, and risk limit.

    Parameters:
        req (Request): HTTP request containing discovery filters and caller identity.

    Returns:
        Response: JSON response containing the effective discovery context and matching
            capabilities, or an error when `max_risk` is invalid.
    """
    profile = req.query1("profile", "core") or "core"
    intent = req.query1("intent", "") or ""
    max_risk_raw = req.query1("max_risk", RiskClass.EXTERNAL_WRITE.value) or (
        RiskClass.EXTERNAL_WRITE.value
    )
    try:
        max_risk = RiskClass(max_risk_raw)
    except ValueError:
        return Response.json(
            400,
            {
                "error": (
                    f"invalid max_risk {max_risk_raw!r}; "
                    f"expected one of {[r.value for r in RiskClass]}"
                )
            },
        )
    identity = resolve_request_identity(req)
    principal = identity.principal_id or "anonymous"
    context = DiscoveryContext(
        principal_id=principal,
        profile_ids=_csv_set(profile) or frozenset({"core"}),
        task_intent=intent,
        max_risk=max_risk,
    )
    results = discover(context)
    if identity.allowed_capabilities is not None:
        results = [
            item
            for item in results
            if capability_allowed(item.capability_id, identity.allowed_capabilities)
        ]
    return Response.json(
        200,
        {
            "context": {
                "profile_ids": sorted(context.profile_ids),
                "task_intent": context.task_intent,
                "max_risk": context.max_risk.value,
                "principal_id": context.principal_id,
                "context_id": identity.context_id,
                "allowed_capabilities": (
                    sorted(identity.allowed_capabilities)
                    if identity.allowed_capabilities is not None
                    else None
                ),
            },
            "total": len(results),
            "capabilities": [_discovered_payload(item) for item in results],
        },
    )


@route("GET", "/api/capabilities/{capability_id}")
def _capabilities_get(req: Request) -> Response:
    """Retrieve the manifest for a capability.

    Parameters:
        req (Request): Request containing the capability identifier in its path parameters.

    Returns:
        Response: A capability manifest, or a 404 error if the capability is not found.
    """
    capability_id = req.params["capability_id"]
    manifest = get_default_registry().get(capability_id)
    if manifest is None:
        return Response.json(404, {"error": "capability not found"})
    return Response.json(200, _manifest_payload(manifest))


@route("GET", "/api/contexts")
def _contexts_list(req: Request) -> Response:
    """
    List remote contexts visible to the requesting identity.

    Parameters:
        req (Request): The HTTP request containing optional principal and revoked-context filters.

    Returns:
        Response: A JSON response containing the total number of matching contexts and their
            serialized records.
    """
    identity = resolve_request_identity(req)
    principal_id = req.query1("principal_id") or None
    # Scoped callers may only ever see their own principal's contexts; ignore
    # any principal_id query override for them. Absent principal = admin.
    if identity.principal_id is not None:
        principal_id = identity.principal_id
    include_revoked = _truthy(req.query1("include_revoked", ""))
    rows = remote_contexts.list_contexts(
        principal_id=principal_id,
        include_revoked=include_revoked,
    )
    return Response.json(
        200,
        {
            "total": len(rows),
            "contexts": [row.to_dict() for row in rows],
        },
    )


@route("POST", "/api/contexts")
def _contexts_create(req: Request) -> Response:
    """Create a remote context from the request body.

    Parameters:
        req (Request): Request containing the context configuration.

    Returns:
        Response: A 201 response with the created context, or a 400 response when the request body
            or context configuration is invalid.
    """
    try:
        body = req.json
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    principal_id = str(body.get("principal_id") or "").strip()
    if not principal_id:
        return Response.json(400, {"error": "principal_id is required"})
    ttl_raw = body.get("ttl_seconds")
    try:
        ttl_seconds = float(ttl_raw) if ttl_raw is not None else None
    except (TypeError, ValueError):
        return Response.json(400, {"error": "ttl_seconds must be a number"})
    metadata = body.get("metadata")
    if metadata is not None and not isinstance(metadata, dict):
        return Response.json(400, {"error": "metadata must be an object"})
    try:
        record = remote_contexts.create_context(
            principal_id=principal_id,
            label=body.get("label"),
            profile=str(body.get("profile") or "core"),
            scopes=body.get("scopes"),
            repository=body.get("repository"),
            environment=body.get("environment"),
            allowed_capabilities=body.get("allowed_capabilities"),
            ttl_seconds=ttl_seconds,
            metadata=metadata,
        )
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    return Response.json(201, record.to_dict())


@route("GET", "/api/contexts/{context_id}")
def _contexts_get(req: Request) -> Response:
    """Retrieve a remote context when it exists and is accessible to the requesting identity.

    Parameters:
        req (Request): Request containing the context identifier and caller identity.

    Returns:
        Response: A JSON response containing the context, or a 404 error when the context is missing
            or inaccessible.
    """
    identity = resolve_request_identity(req)
    record = remote_contexts.get_context(req.params["context_id"])
    if record is None or not _identity_owns_context(identity, record):
        return Response.json(404, {"error": "context not found"})
    return Response.json(200, record.to_dict())


@route("POST", "/api/contexts/{context_id}/revoke")
def _contexts_revoke(req: Request) -> Response:
    """Revoke a remote context owned by the requesting identity.

    Parameters:
        req (Request): The request containing the context identifier and caller identity.

    Returns:
        Response: The revoked context, or a 404 response when the context is missing, inaccessible,
            or cannot be revoked.
    """
    identity = resolve_request_identity(req)
    record = remote_contexts.get_context(req.params["context_id"])
    if record is None or not _identity_owns_context(identity, record):
        return Response.json(404, {"error": "context not found"})
    revoked = remote_contexts.revoke_context(req.params["context_id"])
    if revoked is None:
        return Response.json(404, {"error": "context not found"})
    return Response.json(200, revoked.to_dict())


@route("DELETE", "/api/contexts/{context_id}")
def _contexts_delete(req: Request) -> Response:
    """Revoke a remote context and return its updated record.

    Returns:
        The revoked context record, or a not-found error response when the
        context does not exist, is not owned by the caller, or cannot be revoked.
    """
    identity = resolve_request_identity(req)
    record = remote_contexts.get_context(req.params["context_id"])
    if record is None or not _identity_owns_context(identity, record):
        return Response.json(404, {"error": "context not found"})
    revoked = remote_contexts.revoke_context(req.params["context_id"])
    if revoked is None:
        return Response.json(404, {"error": "context not found"})
    return Response.json(200, revoked.to_dict())


@route("POST", "/api/contexts/{context_id}/token")
def _contexts_issue_token(req: Request) -> Response:
    """Issue a signed token for an active remote context.

    Parameters:
        req (Request): Request containing the context identifier and optional token lifetime.

    Returns:
        Response: A JSON response containing the token, expiration time, and context identifier, or
            an error response if the context is unavailable or the request is invalid.
    """
    identity = resolve_request_identity(req)
    context_id = req.params["context_id"]
    record = remote_contexts.get_context(context_id)
    if record is None or not _identity_owns_context(identity, record):
        return Response.json(404, {"error": "context not found"})
    try:
        body = req.json
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    ttl_raw = body.get("ttl_seconds", 3600)
    try:
        ttl_seconds = int(ttl_raw)
    except (TypeError, ValueError):
        return Response.json(400, {"error": "ttl_seconds must be an integer"})
    try:
        token, record = remote_contexts.mint_context_token(
            context_id,
            ttl_seconds=ttl_seconds,
        )
    except ValueError as exc:
        if str(exc) == "context is not active":
            return Response.json(404, {"error": "context not found"})
        return Response.json(400, {"error": str(exc)})
    expires_at = token_expires_at(token)
    return Response.json(
        200,
        {
            "token": token,
            "expires_at": expires_at,
            "context_id": record.context_id,
        },
    )


@route("GET", "/api/audit/capabilities")
def _capability_audit_list(req: Request) -> Response:
    """
    List capability audit events with optional capability and context filters.

    Parameters:
        req (Request): The HTTP request containing query parameters.

    Returns:
        Response: A JSON response containing the matching audit events, or a 400 response if `limit`
            is not an integer.
    """
    limit_raw = req.query1("limit", "100") or "100"
    try:
        limit = int(limit_raw)
    except ValueError:
        return Response.json(400, {"error": "limit must be an integer"})
    capability_id = req.query1("capability_id") or None
    context_id = req.query1("context_id") or None
    rows = query_capability_audit(
        capability_id=capability_id,
        context_id=context_id,
        limit=limit,
    )
    return Response.json(200, {"total": len(rows), "events": rows})


# Register usage ledger routes without a circular ``from kater.api import …``.
import kater.api.usage_routes as _usage_routes  # noqa: E402, F401
