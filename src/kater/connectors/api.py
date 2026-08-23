"""Generic HTTP/API connector invoke path (stdlib urllib, no per-vendor routers)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from kater.adapters.external import _resolve_env, _substitute_env_vars
from kater.connectors.auth import redact_text
from kater.connectors.errors import (
    ConnectorAuthError,
    ConnectorCapabilityError,
    ConnectorUnavailableError,
    ConnectorValidationError,
)
from kater.connectors.models import (
    AuthBindingKind,
    ConnectorCapability,
    ConnectorRecord,
    ConnectorType,
)

DEFAULT_CLICKHOUSE_OPERATIONS: dict[str, dict[str, Any]] = {
    "clickhouse.ping": {"method": "GET", "path": "/ping", "mutation": False},
    "clickhouse.query": {
        "method": "POST",
        "path": "/",
        "mutation": False,
    },
}


def _operations_for(record: ConnectorRecord) -> dict[str, dict[str, Any]]:
    ops = dict(record.metadata.get("operations") or {})
    shape = str(record.metadata.get("shape") or record.id)
    if shape == "clickhouse" or record.id == "clickhouse":
        merged = dict(DEFAULT_CLICKHOUSE_OPERATIONS)
        merged.update(ops)
        return merged
    return ops


def discover(record: ConnectorRecord) -> list[ConnectorCapability]:
    if record.type is not ConnectorType.API:
        raise ConnectorValidationError(
            "discover applies to API connectors only",
            connector_id=record.id,
        )
    capabilities: list[ConnectorCapability] = []
    for cap_id, op in _operations_for(record).items():
        capabilities.append(
            ConnectorCapability(
                id=cap_id,
                description=str(op.get("description") or cap_id),
                mutation=bool(op.get("mutation", False)),
                input_schema=dict(op.get("input_schema") or {}),
                discovered=False,
            )
        )
    return capabilities


def _substitute_path(path: str, arguments: dict[str, Any]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in arguments:
            raise ConnectorValidationError(f"missing path argument: {key}")
        return urllib.parse.quote(str(arguments[key]), safe="")

    return re.sub(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}", repl, path)


def _resolve_headers(record: ConnectorRecord) -> dict[str, str]:
    transport = record.transport
    headers = _resolve_env(transport.headers_template, include_secrets=True)
    for key, value in transport.headers_template.items():
        if key not in headers and "${" in value:
            headers[key] = _substitute_env_vars(value, include_secrets=True)
    binding = record.auth_binding
    if binding.kind is AuthBindingKind.ENV and binding.ref:
        token_names = [name.strip() for name in binding.ref.split(",") if name.strip()]
        if token_names:
            token = os.environ.get(token_names[0], "")
            if not token:
                raise ConnectorAuthError(
                    f"missing auth env: {token_names[0]}",
                    connector_id=record.id,
                )
            if "Authorization" not in headers:
                headers["Authorization"] = f"Bearer {token}"
    return headers


def _operation_mutation(capability_id: str, op: dict[str, Any], arguments: dict[str, Any]) -> bool:
    if capability_id == "clickhouse.query":
        query = str(arguments.get("query") or "").strip()
        upper = query.upper()
        if upper.startswith(("INSERT", "ALTER", "DROP")):
            return True
        return False
    return bool(op.get("mutation", False))


def invoke(
    record: ConnectorRecord,
    capability_id: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if record.transport.kind != "http":
        raise ConnectorValidationError(
            "API connector requires http transport",
            connector_id=record.id,
        )
    endpoint = (record.transport.endpoint or "").strip()
    if not endpoint:
        raise ConnectorValidationError(
            "API connector requires an endpoint",
            connector_id=record.id,
        )
    operations = _operations_for(record)
    if capability_id not in operations:
        raise ConnectorCapabilityError(
            f"capability {capability_id!r} not found on connector {record.id!r}",
            connector_id=record.id,
        )
    op = operations[capability_id]
    method = str(op.get("method") or "GET").upper()
    path = _substitute_path(str(op.get("path") or "/"), dict(arguments or {}))
    url = urllib.parse.urljoin(endpoint.rstrip("/") + "/", path.lstrip("/"))
    headers = _resolve_headers(record)
    body: bytes | None = None
    if method in {"POST", "PUT", "PATCH"}:
        if capability_id == "clickhouse.query" and "query" in (arguments or {}):
            body = str(arguments["query"]).encode()
        else:
            body = json.dumps(arguments or {}).encode()
        headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(  # noqa: S310 - operator-configured endpoint
        url, data=body, headers=headers, method=method
    )
    timeout = record.transport.timeout_seconds
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            raw = resp.read().decode()
            return {
                "status": resp.status,
                "body": raw,
                "mutation": _operation_mutation(capability_id, op, arguments or {}),
            }
    except urllib.error.HTTPError as exc:
        err_headers = redact_text(str(dict(exc.headers.items()) if exc.headers else {}))
        detail = redact_text(exc.read().decode(errors="replace") if exc.fp else str(exc))
        raise ConnectorUnavailableError(
            f"HTTP {exc.code}: {detail} (headers={err_headers})",
            connector_id=record.id,
        ) from exc
    except ConnectorAuthError:
        raise
    except Exception as exc:
        raise ConnectorUnavailableError(
            redact_text(str(exc)),
            connector_id=record.id,
        ) from exc
