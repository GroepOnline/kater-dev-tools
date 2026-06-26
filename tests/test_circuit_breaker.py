from __future__ import annotations

import shutil
import time
from pathlib import Path

import pytest

from kater.proxy.base import MockBackend
from kater.proxy.manager import CircuitBreaker, ProxyManager

KATER_DIR = Path.cwd() / ".kater"


@pytest.fixture(autouse=True)
def clean_storage():
    from kater.storage import reset_db_cache

    reset_db_cache()
    if KATER_DIR.exists():
        shutil.rmtree(KATER_DIR)
    yield
    reset_db_cache()
    if KATER_DIR.exists():
        shutil.rmtree(KATER_DIR)


def test_circuit_breaker_starts_closed():
    cb = CircuitBreaker()
    assert cb.state == "closed"
    assert cb.can_call() is True


def test_circuit_breaker_trips_after_threshold():
    cb = CircuitBreaker(failure_threshold=3)
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "closed"
    cb.record_failure()
    assert cb.state == "open"
    assert cb.can_call() is False


def test_circuit_breaker_half_open_after_timeout():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
    cb.record_failure()
    assert cb.state == "open"
    time.sleep(0.15)
    assert cb.can_call() is True
    assert cb.state == "half_open"


def test_circuit_breaker_closes_on_success():
    cb = CircuitBreaker(failure_threshold=1)
    cb.record_failure()
    assert cb.state == "open"
    time.sleep(0.15)
    cb.record_success()
    assert cb.state == "closed"
    assert cb.can_call() is True


def test_circuit_breaker_stays_open_on_half_open_failure():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.1)
    cb.record_failure()
    time.sleep(0.15)
    assert cb.state == "half_open"
    cb.record_failure()
    assert cb.state == "open"


def test_circuit_breaker_resets_on_success():
    cb = CircuitBreaker(failure_threshold=5)
    for _ in range(3):
        cb.record_failure()
    assert cb.state == "closed"
    cb.record_success()
    cb.record_failure()
    cb.record_failure()
    cb.record_failure()
    assert cb.state == "closed"


def test_proxy_manager_call_with_breaker():
    from kater.proxy.aggregator import Aggregator
    from kater.proxy.router import Router

    backend = MockBackend(
        tools=[{"name": "ping"}],
        responses={"ping": {"result": "ok"}},
    )
    backend.start()
    agg = Aggregator()
    agg.add_backend_tools("mock", backend.list_tools())
    router = Router(agg)

    manager = ProxyManager()
    manager._backends["mock"] = backend
    manager._aggregator = agg
    manager._router = router
    from kater.proxy.manager import CircuitBreaker

    manager._breakers["mock"] = CircuitBreaker()

    result = manager.call_tool("mock__ping", {})
    assert result.get("result") == "ok"
    assert manager._breakers["mock"].state == "closed"


def test_proxy_manager_breaker_trips_on_failures():
    from kater.proxy.aggregator import Aggregator
    from kater.proxy.base import MockBackend
    from kater.proxy.router import Router

    backend = MockBackend(
        tools=[{"name": "crash"}],
    )
    backend.start()
    backend.call_tool = lambda name, args: (_ for _ in ()).throw(
        RuntimeError("boom")
    )

    agg = Aggregator()
    agg.add_backend_tools("mock", backend.list_tools())
    router = Router(agg)

    manager = ProxyManager()
    manager._backends["mock"] = backend
    manager._aggregator = agg
    manager._router = router
    from kater.proxy.manager import CircuitBreaker

    manager._breakers["mock"] = CircuitBreaker(failure_threshold=3)

    for _ in range(3):
        manager.call_tool("mock__crash", {})

    assert manager._breakers["mock"].state == "open"
    result = manager.call_tool("mock__crash", {})
    assert "error" in result


def test_proxy_manager_health_check():
    from kater.proxy.base import MockBackend
    from kater.proxy.manager import CircuitBreaker

    backend = MockBackend(tools=[{"name": "ping"}])
    backend.start()

    manager = ProxyManager()
    manager._backends["mock"] = backend
    manager._breakers["mock"] = CircuitBreaker()

    health = manager.health_check()
    assert "mock" in health
    assert health["mock"] is True


def test_proxy_statuses_include_breaker():
    from kater.proxy.base import MockBackend
    from kater.proxy.manager import CircuitBreaker

    backend = MockBackend(tools=[{"name": "ping"}])
    backend.start()

    manager = ProxyManager()
    manager._backends["mock"] = backend
    manager._breakers["mock"] = CircuitBreaker()

    statuses = manager.statuses()
    assert len(statuses) == 1
    assert hasattr(statuses[0], "breaker_state") or "breaker" in statuses[0].to_dict()
