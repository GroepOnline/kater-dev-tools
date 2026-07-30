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
    if not raw:
        return frozenset()
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


def _truthy(raw: str | None) -> bool:
    return (raw or "").strip().lower() in {"1", "true", "yes", "on"}


def _identity_owns_context(identity: RequestIdentity, record: Any) -> bool:
    """Ownership gate for remote-context records.

    An absent principal (no scoped context token: a trusted/admin API-key or
    ``auth=none`` caller) is unrestricted. A scoped caller may only touch
    records whose ``principal_id`` matches its own.
    """
    if identity.principal_id is None:
        return True
    return record.principal_id == identity.principal_id


def _body_str_set(value: Any) -> frozenset[str]:
    """Parse a scope/capability list from a JSON body the way the store does."""
    if value is None:
        return frozenset()
    if isinstance(value, str):
        return _csv_set(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return frozenset(str(item) for item in value if str(item))
    raise ValueError("expected a list of strings")


def _attenuate_creation(
    identity: RequestIdentity,
    *,
    principal_id: str,
    scopes: frozenset[str],
    capabilities: frozenset[str],
) -> tuple[frozenset[str], frozenset[str]] | Response:
    """Keep a created context's authority within the creating caller's.

    An absent principal (admin API-key or ``auth=none``) may create anything.
    A scoped caller may only create contexts for its own principal, and never
    with scopes or capabilities it does not itself hold: otherwise a token
    denied a capability could mint a child token that is allowed it. Omitted
    fields inherit the caller's authority rather than widening to unrestricted.
    """
    if identity.principal_id is None:
        return scopes, capabilities
    if principal_id != identity.principal_id:
        return Response.json(
            403,
            {"error": "a scoped context may only create contexts for its own principal"},
        )
    if not scopes:
        scopes = frozenset(identity.scopes)
    elif not scopes <= identity.scopes:
        return Response.json(
            403,
            {"error": f"scopes exceed the caller's: {sorted(scopes - identity.scopes)}"},
        )
    allowed = identity.allowed_capabilities
    if allowed is not None:
        # An empty request means unrestricted once stored, so inherit instead.
        if not capabilities:
            capabilities = frozenset(allowed)
        else:
            excess = sorted(n for n in capabilities if not capability_allowed(n, allowed))
            if excess:
                return Response.json(
                    403,
                    {"error": f"allowed_capabilities exceed the caller's: {excess}"},
                )
    return scopes, capabilities


def _identity_can_delegate_record(identity: RequestIdentity, record: Any) -> bool:
    """Ensure a scoped caller cannot mint a broader same-principal context."""
    if identity.principal_id is None:
        return True
    if not record.scopes <= identity.scopes:
        return False
    allowed = identity.allowed_capabilities
    if allowed is None:
        return True
    if not record.allowed_capabilities:
        return False
    return all(
        capability_allowed(capability, allowed)
        for capability in record.allowed_capabilities
    )


def _discovered_payload(item: Any) -> dict[str, Any]:
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
    capability_id = req.params["capability_id"]
    manifest = get_default_registry().get(capability_id)
    if manifest is None:
        return Response.json(404, {"error": "capability not found"})
    return Response.json(200, _manifest_payload(manifest))


@route("GET", "/api/contexts")
def _contexts_list(req: Request) -> Response:
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
    identity = resolve_request_identity(req)
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
        scopes = _body_str_set(body.get("scopes"))
        capabilities = _body_str_set(body.get("allowed_capabilities"))
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    attenuated = _attenuate_creation(
        identity,
        principal_id=principal_id,
        scopes=scopes,
        capabilities=capabilities,
    )
    if isinstance(attenuated, Response):
        return attenuated
    scopes, capabilities = attenuated
    try:
        record = remote_contexts.create_context(
            principal_id=principal_id,
            label=body.get("label"),
            profile=str(body.get("profile") or "core"),
            scopes=scopes,
            repository=body.get("repository"),
            environment=body.get("environment"),
            allowed_capabilities=capabilities,
            ttl_seconds=ttl_seconds,
            metadata=metadata,
        )
    except ValueError as exc:
        return Response.json(400, {"error": str(exc)})
    return Response.json(201, record.to_dict())


@route("GET", "/api/contexts/{context_id}")
def _contexts_get(req: Request) -> Response:
    identity = resolve_request_identity(req)
    record = remote_contexts.get_context(req.params["context_id"])
    if record is None or not _identity_owns_context(identity, record):
        return Response.json(404, {"error": "context not found"})
    return Response.json(200, record.to_dict())


@route("POST", "/api/contexts/{context_id}/revoke")
def _contexts_revoke(req: Request) -> Response:
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
    identity = resolve_request_identity(req)
    context_id = req.params["context_id"]
    record = remote_contexts.get_context(context_id)
    if record is None or not _identity_owns_context(identity, record):
        return Response.json(404, {"error": "context not found"})
    if not _identity_can_delegate_record(identity, record):
        return Response.json(403, {"error": "context authority exceeds caller authority"})
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
    except remote_contexts.ContextNotActiveError:
        return Response.json(404, {"error": "context not found"})
    except ValueError as exc:
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
