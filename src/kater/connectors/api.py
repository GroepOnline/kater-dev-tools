"""Generic HTTP/API connector invoke path (stdlib urllib, no per-vendor routers)."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from kater.adapters.external import _resolve_env, _substitute_env_vars
from kater.connectors.auth import redact_text, resolve_auth_values
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
            resolved = _substitute_env_vars(value, include_secrets=True)
            if "${" not in resolved:
                headers[key] = resolved
    binding = record.auth_binding
    if binding.kind is not AuthBindingKind.NONE and binding.ref and "Authorization" not in headers:
        token_names = [name.strip() for name in binding.ref.split(",") if name.strip()]
        values = resolve_auth_values(binding, connector_id=record.id)
        missing = [name for name in token_names if name not in values]
        if missing:
            raise ConnectorAuthError(
                f"missing auth refs: {', '.join(missing)}",
                connector_id=record.id,
            )
        if len(token_names) > 1:
            raise ConnectorAuthError(
                "multiple auth refs require an explicit Authorization header template",
                connector_id=record.id,
            )
        if token_names:
            headers["Authorization"] = f"Bearer {values[token_names[0]]}"
    return headers


# Statements we can positively prove are read-only. Everything else is treated
# as mutating and requires WRITE. Fail closed.
_CLICKHOUSE_READ_ONLY_STARTS = (
    "SELECT",
    "WITH",
    "SHOW",
    "DESCRIBE",
    "DESC",
    "EXPLAIN",
    "EXISTS",
    "CHECK",
)


def _clickhouse_statements(query: str) -> list[str]:
    """Split SQL statements while ignoring comments and quoted semicolons.

    This is deliberately a small conservative scanner, not a SQL parser. It only
    needs to distinguish top-level statement separators from content inside
    ClickHouse string/identifier quotes. Unterminated quotes fail closed by
    returning an extra sentinel statement.
    """
    text = str(query or "")
    statements: list[str] = []
    current: list[str] = []
    quote: str | None = None
    i = 0
    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""
        if quote is not None:
            current.append(ch)
            if ch == "\\" and i + 1 < len(text):
                current.append(text[i + 1])
                i += 2
                continue
            if ch == quote:
                if i + 1 < len(text) and text[i + 1] == quote:
                    current.append(text[i + 1])
                    i += 2
                    continue
                quote = None
            i += 1
            continue
        if ch in {"'", '"', "`"}:
            quote = ch
            current.append(ch)
            i += 1
            continue
        if ch == "-" and nxt == "-":
            i += 2
            while i < len(text) and text[i] != "\n":
                i += 1
            current.append(" ")
            continue
        if ch == "/" and nxt == "*":
            end = text.find("*/", i + 2)
            if end < 0:
                return ["", "unterminated-comment"]
            current.append(" ")
            i = end + 2
            continue
        if ch == ";":
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    if quote is not None:
        return ["", "unterminated-quote"]
    statement = "".join(current).strip()
    if statement:
        statements.append(statement)
    return statements


def clickhouse_query_is_mutation(query: str) -> bool:
    """Fail closed unless there is exactly one positively identified read statement."""
    statements = _clickhouse_statements(query)
    if len(statements) != 1:
        return True
    first = statements[0].split(None, 1)[0].upper().rstrip("(")
    return first not in _CLICKHOUSE_READ_ONLY_STARTS


def _operation_mutation(capability_id: str, op: dict[str, Any], arguments: dict[str, Any]) -> bool:
    if capability_id == "clickhouse.query":
        return clickhouse_query_is_mutation(str(arguments.get("query") or ""))
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
            body = str(arguments["query"]).encode("utf-8")
            headers["Content-Type"] = "text/plain; charset=utf-8"
        else:
            body = json.dumps(arguments or {}).encode("utf-8")
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
        detail = redact_text(exc.read().decode(errors="replace") if exc.fp else str(exc))
        raise ConnectorUnavailableError(
            f"HTTP {exc.code}: {detail}",
            connector_id=record.id,
        ) from exc
    except ConnectorAuthError:
        raise
    except Exception as exc:
        raise ConnectorUnavailableError(
            redact_text(str(exc)),
            connector_id=record.id,
        ) from exc
