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
    backend = MockBackend(
        tools=[{"name": "ping"}],
        responses={"ping": {"result": "ok"}},
    )
    manager = ProxyManager()
    manager.register_backend("mock", backend)

    result = manager.call_tool("mock__ping", {})
    assert result.get("result") == "ok"
    assert manager.statuses()[0].breaker_state == "closed"


def test_proxy_manager_breaker_trips_on_failures():
    backend = MockBackend(
        tools=[{"name": "crash"}],
    )
    backend.start()
    backend.call_tool = lambda name, args: (_ for _ in ()).throw(
        RuntimeError("boom")
    )

    manager = ProxyManager()
    manager.register_backend("mock", backend)

    for _ in range(5):
        manager.call_tool("mock__crash", {})

    assert manager.statuses()[0].breaker_state == "open"
    result = manager.call_tool("mock__crash", {})
    assert "error" in result


def test_proxy_manager_health_check():
    backend = MockBackend(tools=[{"name": "ping"}])
    manager = ProxyManager()
    manager.register_backend("mock", backend)

    health = manager.health_check()
    assert "mock" in health
    assert health["mock"] is True


def test_proxy_statuses_include_breaker():
    backend = MockBackend(tools=[{"name": "ping"}])
    manager = ProxyManager()
    manager.register_backend("mock", backend)

    statuses = manager.statuses()
    assert len(statuses) == 1
    assert statuses[0].breaker_state == "closed"
    assert statuses[0].to_dict()["breaker_state"] == "closed"
