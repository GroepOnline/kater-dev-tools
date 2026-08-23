"""In-process MCP connector lifecycle (discover + invoke, no native tool registration)."""

from __future__ import annotations

import re
from typing import Any

from kater.adapters.external import _resolve_env, _substitute_env_vars
from kater.connectors.auth import redact_mapping, redact_text
from kater.connectors.errors import (
    ConnectorCapabilityError,
    ConnectorUnavailableError,
    ConnectorValidationError,
)
from kater.connectors.models import (
    ConnectorCapability,
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
)
from kater.proxy.base import BackendOperationalError, BaseBackend
from kater.proxy.sse_backend import SSEBackend
from kater.proxy.stdio_backend import StdioBackend
from kater.proxy.streamable_http_backend import StreamableHTTPBackend

_WRITE_HINTS = ("write", "create", "update", "delete", "merge", "admin", "mutate")
_CAPABILITY_CHARS = re.compile(r"[^a-z0-9._:-]+")


def _remote_launch_type(url: str) -> str:
    if url.rstrip("/").endswith("/mcp"):
        return "streamableHttp"
    return "sse"


def _resolve_transport_headers(transport: ConnectorTransport) -> dict[str, str]:
    resolved = _resolve_env(transport.headers_template, include_secrets=True)
    for key, value in transport.headers_template.items():
        if key not in resolved and "${" in value:
            resolved[key] = _substitute_env_vars(value, include_secrets=True)
    return resolved


def _resolve_transport_env(transport: ConnectorTransport) -> dict[str, str]:
    return _resolve_env(transport.env_template, include_secrets=True)


def _sanitize_capability_id(connector_id: str, tool_name: str) -> str:
    raw = f"{connector_id}.{tool_name}".lower()
    cleaned = _CAPABILITY_CHARS.sub(".", raw)
    while ".." in cleaned:
        cleaned = cleaned.replace("..", ".")
    return cleaned.strip(".")


def _infer_mutation(tool_name: str) -> bool:
    lowered = tool_name.lower().replace("-", "_").split("_")
    return any(hint in lowered for hint in _WRITE_HINTS)


def _map_tool(connector_id: str, tool: Any) -> ConnectorCapability:
    if isinstance(tool, dict):
        name = str(tool.get("name") or "")
        description = str(tool.get("description") or "")
        schema = dict(tool.get("inputSchema") or tool.get("input_schema") or {})
    else:
        name = str(getattr(tool, "name", "") or "")
        description = str(getattr(tool, "description", "") or "")
        schema = dict(getattr(tool, "input_schema", {}) or {})
    cap_id = _sanitize_capability_id(connector_id, name)
    return ConnectorCapability(
        id=cap_id,
        description=description,
        mutation=_infer_mutation(name),
        input_schema=dict(schema or {}),
        discovered=True,
    )


def _create_backend(record: ConnectorRecord) -> BaseBackend:
    transport = record.transport
    kind = transport.kind
    timeout = transport.timeout_seconds
    if kind == "stdio":
        if not transport.command:
            raise ConnectorValidationError(
                "stdio transport requires a command",
                connector_id=record.id,
            )
        return StdioBackend(
            record.id,
            transport.command,
            list(transport.args),
            _resolve_transport_env(transport),
            timeout,
        )
    if kind in {"http", "sse"}:
        endpoint = (transport.endpoint or "").strip()
        if not endpoint:
            raise ConnectorValidationError(
                f"{kind} transport requires an endpoint",
                connector_id=record.id,
            )
        headers = _resolve_transport_headers(transport)
        if kind == "sse" or _remote_launch_type(endpoint) == "sse":
            return SSEBackend(record.id, endpoint, headers, timeout)
        return StreamableHTTPBackend(record.id, endpoint, headers, timeout)
    raise ConnectorValidationError(
        f"unsupported MCP transport kind: {kind!r}",
        connector_id=record.id,
    )


def _tool_name_from_capability(record: ConnectorRecord, capability_id: str) -> str:
    prefix = f"{record.id}."
    if capability_id.startswith(prefix):
        return capability_id[len(prefix) :]
    cap = record.capability(capability_id)
    if cap and cap.discovered:
        if capability_id.startswith(prefix):
            return capability_id[len(prefix) :]
        parts = capability_id.split(".", 1)
        if len(parts) == 2:
            return parts[1]
    raise ConnectorCapabilityError(
        f"capability {capability_id!r} is not invokable on connector {record.id!r}",
        connector_id=record.id,
    )


def discover(record: ConnectorRecord) -> list[ConnectorCapability]:
    if record.type is not ConnectorType.MCP:
        raise ConnectorValidationError(
            "discover applies to MCP connectors only",
            connector_id=record.id,
        )
    backend = _create_backend(record)
    try:
        backend.start()
        if not backend.is_healthy():
            detail = redact_text(backend.status.error or "backend unhealthy")
            raise ConnectorUnavailableError(
                f"MCP discovery failed: {detail}",
                connector_id=record.id,
            )
        return [_map_tool(record.id, tool) for tool in backend.list_tools()]
    except ConnectorUnavailableError:
        raise
    except BackendOperationalError as exc:
        raise ConnectorUnavailableError(
            redact_text(str(exc)),
            connector_id=record.id,
        ) from exc
    except ConnectorValidationError:
        raise
    except Exception as exc:
        raise ConnectorUnavailableError(
            redact_text(str(exc)),
            connector_id=record.id,
        ) from exc
    finally:
        backend.stop()


def discover_mcp(transport: ConnectorTransport | dict[str, Any]) -> list[ConnectorCapability]:
    """Discover tools from a transport spec without persisting a connector."""
    if isinstance(transport, dict):
        transport_obj = ConnectorTransport.from_mapping(transport)
    else:
        transport_obj = transport
    probe = ConnectorRecord(
        id="_discover",
        display_name="discover",
        type=ConnectorType.MCP,
        version="0",
        transport=transport_obj,
        status=ConnectorStatus.REGISTERED,
    )
    return discover(probe)


def invoke(
    record: ConnectorRecord,
    capability_id: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if record.capability(capability_id) is None:
        raise ConnectorCapabilityError(
            f"capability {capability_id!r} not found on connector {record.id!r}",
            connector_id=record.id,
        )
    tool_name = _tool_name_from_capability(record, capability_id)
    payload = {key: value for key, value in dict(arguments or {}).items() if key != "_kater_route"}
    backend = _create_backend(record)
    try:
        backend.start()
        if not backend.is_healthy():
            detail = redact_text(backend.status.error or "backend unhealthy")
            raise ConnectorUnavailableError(
                f"MCP invoke failed: {detail}",
                connector_id=record.id,
            )
        result = backend.call_tool(tool_name, payload)
        if isinstance(result, dict) and "error" in result:
            raise ConnectorUnavailableError(
                redact_text(str(redact_mapping(result))),
                connector_id=record.id,
            )
        return result if isinstance(result, dict) else {"result": result}
    except ConnectorCapabilityError:
        raise
    except ConnectorUnavailableError:
        raise
    except BackendOperationalError as exc:
        raise ConnectorUnavailableError(
            redact_text(str(exc)),
            connector_id=record.id,
        ) from exc
    except Exception as exc:
        raise ConnectorUnavailableError(
            redact_text(str(exc)),
            connector_id=record.id,
        ) from exc
    finally:
        backend.stop()
