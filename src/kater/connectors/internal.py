"""In-process handler registry for ``internal`` connectors.

An ``internal`` connector is served by native Kater code (the gateway itself, a
Computer guest, …) rather than an outbound transport. Modules opt in by calling
``register_internal_handler`` at import time. If no handler is registered for a
connector, invoke fails closed with a specific error instead of pretending the
connector is reachable.

This registry is deliberately small: it exists so the connector *type model* is
complete and testable, not to add a speculative subsystem. Nothing is persisted
here — handlers live only in the running process.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

from kater.connectors.errors import ConnectorUnavailableError
from kater.connectors.models import ConnectorRecord

# A handler receives the resolved record, the requested capability id, and the
# (route-stripped) arguments, and returns a JSON-serializable result mapping.
InternalHandler = Callable[[ConnectorRecord, str, dict[str, Any]], dict[str, Any]]

_lock = threading.RLock()
_handlers: dict[str, InternalHandler] = {}


def register_internal_handler(connector_id: str, handler: InternalHandler) -> None:
    """Bind a native handler to an internal connector id (idempotent overwrite)."""
    with _lock:
        _handlers[connector_id] = handler


def unregister_internal_handler(connector_id: str) -> None:
    """Drop a handler binding (used by tests and hot reloads)."""
    with _lock:
        _handlers.pop(connector_id, None)


def has_internal_handler(connector_id: str) -> bool:
    with _lock:
        return connector_id in _handlers


def invoke(
    record: ConnectorRecord,
    capability_id: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Dispatch to the registered native handler, or fail closed."""
    with _lock:
        handler = _handlers.get(record.id)
    if handler is None:
        raise ConnectorUnavailableError(
            f"internal connector {record.id!r} has no registered handler",
            connector_id=record.id,
            code="no_internal_handler",
        )
    payload = {key: value for key, value in dict(arguments or {}).items() if key != "_kater_route"}
    result = handler(record, capability_id, payload)
    return result if isinstance(result, dict) else {"result": result}
