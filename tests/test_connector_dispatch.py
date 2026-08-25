from __future__ import annotations

from unittest.mock import patch

import pytest

from kater.connectors import dispatch
from kater.connectors.models import (
    ConnectorRecord,
    ConnectorStatus,
    ConnectorTransport,
    ConnectorType,
)
from kater.proxy.base import MockBackend
from kater.settings import KaterSettings, ServerOverride, save_settings


def _mcp_record(connector_id: str = "poolmcp") -> ConnectorRecord:
    return ConnectorRecord(
        id=connector_id,
        display_name="Pool MCP",
        type=ConnectorType.MCP,
        version="1.0.0",
        transport=ConnectorTransport(kind="stdio", command="echo", args=("mcp",)),
        status=ConnectorStatus.ENABLED,
    )


class _CountingBackend(MockBackend):
    """MockBackend that records how many times it was started and stopped."""

    def __init__(self) -> None:
        super().__init__(tools=[{"name": "echo"}])
        self.starts = 0
        self.stops = 0

    def start(self) -> None:
        super().start()
        self.starts += 1

    def stop(self) -> None:
        super().stop()
        self.stops += 1


@pytest.fixture(autouse=True)
def reset_pool_and_env(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    dispatch.reset_pool()
    yield
    dispatch.reset_pool()


def test_stateless_starts_and_stops_a_fresh_backend_each_call(tmp_path, monkeypatch):
    save_settings(KaterSettings(connector_invocation_mode="stateless"), tmp_path)
    record = _mcp_record()
    made: list[_CountingBackend] = []

    def factory() -> _CountingBackend:
        backend = _CountingBackend()
        made.append(backend)
        return backend

    for _ in range(3):
        with dispatch.provide_backend(record, factory) as backend:
            assert backend.is_healthy()

    assert len(made) == 3
    assert all(b.starts == 1 and b.stops == 1 for b in made)


def test_pooled_reuses_one_warm_backend(tmp_path, monkeypatch):
    save_settings(KaterSettings(connector_invocation_mode="pooled"), tmp_path)
    record = _mcp_record()
    made: list[_CountingBackend] = []

    def factory() -> _CountingBackend:
        backend = _CountingBackend()
        made.append(backend)
        return backend

    for _ in range(3):
        with dispatch.provide_backend(record, factory) as backend:
            assert backend.is_healthy()

    assert len(made) == 1
    assert made[0].starts == 1
    assert made[0].stops == 0


def test_pooled_backend_expires_after_ttl(tmp_path, monkeypatch):
    save_settings(
        KaterSettings(connector_invocation_mode="pooled", connector_pool_ttl_seconds=30.0),
        tmp_path,
    )
    record = _mcp_record()
    made: list[_CountingBackend] = []

    def factory() -> _CountingBackend:
        backend = _CountingBackend()
        made.append(backend)
        return backend

    clock = {"t": 1000.0}
    monkeypatch.setattr(dispatch.time, "monotonic", lambda: clock["t"])

    with dispatch.provide_backend(record, factory):
        pass
    clock["t"] += 31.0  # push past the TTL
    with dispatch.provide_backend(record, factory):
        pass

    assert len(made) == 2
    assert made[0].stops == 1  # expired backend was stopped


def test_poisoned_pooled_backend_is_dropped_on_error(tmp_path):
    save_settings(KaterSettings(connector_invocation_mode="pooled"), tmp_path)
    record = _mcp_record()
    made: list[_CountingBackend] = []

    def factory() -> _CountingBackend:
        backend = _CountingBackend()
        made.append(backend)
        return backend

    with pytest.raises(RuntimeError):
        with dispatch.provide_backend(record, factory):
            raise RuntimeError("boom")

    # Next call must build a new backend, not reuse the poisoned one.
    with dispatch.provide_backend(record, factory):
        pass

    assert len(made) == 2
    assert made[0].stops == 1


def test_public_mode_forces_stateless_even_when_pooled_configured(tmp_path, monkeypatch):
    monkeypatch.setenv("KATER_PUBLIC", "1")
    save_settings(KaterSettings(connector_invocation_mode="pooled"), tmp_path)
    record = _mcp_record()
    made: list[_CountingBackend] = []

    def factory() -> _CountingBackend:
        backend = _CountingBackend()
        made.append(backend)
        return backend

    for _ in range(2):
        with dispatch.provide_backend(record, factory):
            pass

    assert len(made) == 2
    assert all(b.stops == 1 for b in made)


def test_per_connector_override_beats_global_default(tmp_path):
    save_settings(
        KaterSettings(
            connector_invocation_mode="stateless",
            server_overrides={"poolmcp": ServerOverride(invocation_mode="pooled")},
        ),
        tmp_path,
    )
    record = _mcp_record("poolmcp")
    made: list[_CountingBackend] = []

    def factory() -> _CountingBackend:
        backend = _CountingBackend()
        made.append(backend)
        return backend

    for _ in range(2):
        with dispatch.provide_backend(record, factory):
            pass

    assert len(made) == 1  # pooled override reused the warm backend


def test_invoke_uses_dispatch_and_leaves_native_surface_at_seventeen(tmp_path, monkeypatch):
    monkeypatch.delenv("KATER_EXTENSIONS_MODULE", raising=False)
    monkeypatch.delenv("KATER_PUBLIC", raising=False)
    from kater.connectors import mcp_lifecycle
    from kater.connectors.models import ConnectorCapability
    from kater.registry import build_native_tools

    save_settings(KaterSettings(connector_invocation_mode="pooled"), tmp_path)
    before = [tool.name for tool in build_native_tools()]
    record = _mcp_record()
    data = record.as_dict()
    data["capabilities"] = [
        ConnectorCapability(id="poolmcp.echo", description="echo", discovered=True).as_dict()
    ]
    record = ConnectorRecord.from_mapping(data)
    backend = MockBackend(
        tools=[{"name": "echo", "description": "echo"}],
        responses={"echo": {"content": [{"type": "text", "text": "ok"}]}},
    )

    with patch.object(mcp_lifecycle, "_create_backend", return_value=backend):
        result = mcp_lifecycle.invoke(record, "poolmcp.echo", {"message": "hi"})

    after = [tool.name for tool in build_native_tools()]
    assert before == after
    assert len(before) == 17
    assert result["content"][0]["text"] == "ok"
