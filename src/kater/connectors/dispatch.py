"""Configurable, stateless-by-default backend dispatch for MCP connectors.

The connector control plane always presents Kater's 17 native tools as a
*stateless* surface to Cursor. This module governs only how Kater reaches
*outbound* MCP backends when invoking a connector:

- ``stateless`` (default): open a fresh backend for each call and stop it right
  after. Nothing is kept between calls besides the SQLite catalog.
- ``pooled``: reuse a warm backend within a TTL to avoid paying MCP
  ``initialize`` cost on every call. This is an outbound-only optimization and
  is force-disabled on public / company-control (``--no-proxy``) deploys via
  ``KaterSettings.connector_invocation``.

Even in ``pooled`` mode the caller-visible contract is unchanged: a
``BaseBackend`` is yielded, used for one ``call_tool``/``list_tools``, and the
pool owns lifecycle. Callers never assume state carries across invocations.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass

from kater.connectors.models import ConnectorRecord
from kater.proxy.base import BaseBackend
from kater.settings import load_settings


@dataclass
class _PooledBackend:
    backend: BaseBackend
    last_used: float


class _BackendPool:
    """Thread-safe pool of warm backends keyed by connector id, with a TTL."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: dict[str, _PooledBackend] = {}
        self._invocation_locks: dict[str, threading.RLock] = {}

    def acquire(
        self,
        connector_id: str,
        factory: Callable[[], BaseBackend],
        *,
        ttl_seconds: float,
    ) -> BaseBackend:
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(connector_id)
            if entry is not None:
                expired = (now - entry.last_used) > ttl_seconds
                if expired or not entry.backend.is_healthy():
                    self._drop_locked(connector_id)
                    entry = None
            if entry is None:
                backend = factory()
                backend.start()
                if not backend.is_healthy():
                    # Do not pool an unhealthy backend; hand it back so the caller
                    # surfaces the redacted error, and make sure it is stopped.
                    with _suppress():
                        backend.stop()
                    return backend
                entry = _PooledBackend(backend=backend, last_used=now)
                self._entries[connector_id] = entry
            entry.last_used = now
            return entry.backend

    def invocation_lock(self, connector_id: str) -> threading.RLock:
        """Return the stable per-connector lock that serializes use of a warm backend."""
        with self._lock:
            lock = self._invocation_locks.get(connector_id)
            if lock is None:
                lock = threading.RLock()
                self._invocation_locks[connector_id] = lock
            return lock

    def _drop_locked(self, connector_id: str) -> None:
        entry = self._entries.pop(connector_id, None)
        if entry is not None:
            with _suppress():
                entry.backend.stop()

    def drop(self, connector_id: str) -> None:
        with self._lock:
            self._drop_locked(connector_id)

    def reset(self) -> None:
        """Stop and clear every pooled backend (used by tests and reloads)."""
        with self._lock:
            for connector_id in list(self._entries):
                self._drop_locked(connector_id)


class _suppress:
    """Small context manager that swallows backend stop() failures."""

    def __enter__(self) -> None:
        return None

    def __exit__(self, *exc: object) -> bool:
        return True


_POOL = _BackendPool()


def reset_pool() -> None:
    """Drop all warm backends. Call from tests and on catalog reloads."""
    _POOL.reset()


@contextmanager
def provide_backend(
    record: ConnectorRecord,
    factory: Callable[[], BaseBackend],
) -> Iterator[BaseBackend]:
    """Yield a ready backend according to the connector's invocation mode.

    ``factory`` builds a fresh, unstarted backend. In ``stateless`` mode the
    backend is started here and stopped in ``finally``. In ``pooled`` mode the
    pool owns start/stop and the backend stays warm until its TTL elapses.
    """
    settings = load_settings()
    mode = settings.connector_invocation(record.id)
    if mode == "pooled":
        # One warm MCP session may not support overlapping tools/call exchanges. Keep
        # pooling for setup latency, but serialize leases per connector so responses
        # from concurrent requests cannot interleave on the same backend transport.
        with _POOL.invocation_lock(record.id):
            backend = _POOL.acquire(
                record.id,
                factory,
                ttl_seconds=settings.connector_pool_ttl_seconds,
            )
            try:
                yield backend
            except Exception:
                # A failure may mean the warm session is now poisoned; drop it so the
                # next call rebuilds instead of reusing a broken backend.
                _POOL.drop(record.id)
                raise
        return
    # Stateless (default): fresh backend per call, always stopped.
    backend = factory()
    try:
        backend.start()
        yield backend
    finally:
        with _suppress():
            backend.stop()
