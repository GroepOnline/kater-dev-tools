"""Janitor cadence: light ticks vs sparse heavy sweeps."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from kater.runtime import (
    _HEAVY_EVERY_N_TICKS,
    _HEAVY_INTERVAL,
    _TICK_INTERVAL,
    KaterRuntime,
    _should_run_heavy,
)
from kater.settings import ListenConfig


def test_should_run_heavy_every_nth_tick_or_elapsed() -> None:
    assert _should_run_heavy(0) is False
    assert _should_run_heavy(1) is False
    assert _should_run_heavy(_HEAVY_EVERY_N_TICKS - 1) is False
    assert _should_run_heavy(_HEAVY_EVERY_N_TICKS) is True
    assert _should_run_heavy(_HEAVY_EVERY_N_TICKS * 2) is True
    assert _should_run_heavy(3, elapsed_since_heavy=_HEAVY_INTERVAL) is True
    assert _should_run_heavy(3, elapsed_since_heavy=_HEAVY_INTERVAL - 0.1) is False


def test_tick_interval_is_shorter_than_heavy_cadence() -> None:
    assert _TICK_INTERVAL < _HEAVY_INTERVAL
    assert _TICK_INTERVAL * _HEAVY_EVERY_N_TICKS == _HEAVY_INTERVAL


def test_maintenance_loop_runs_light_more_often_than_heavy(monkeypatch) -> None:
    runtime = KaterRuntime(
        profile="core",
        listen=ListenConfig(host="127.0.0.1", api_port=29391, mcp_port=29390, ws_port=29392),
    )
    light_calls: list[int] = []
    heavy_calls: list[int] = []
    wakes = {"n": 0}
    target_wakes = _HEAVY_EVERY_N_TICKS + 2

    def fake_wait(_timeout: float) -> bool:
        wakes["n"] += 1
        if wakes["n"] > target_wakes:
            runtime._shutdown_event.set()
            return True
        return False

    monkeypatch.setattr(runtime._shutdown_event, "wait", fake_wait)
    monkeypatch.setattr(
        runtime,
        "_run_light_janitor",
        lambda: light_calls.append(wakes["n"]),
    )
    monkeypatch.setattr(
        runtime,
        "_run_heavy_janitor",
        lambda: heavy_calls.append(wakes["n"]),
    )
    # Patch the module reference only; setattr on kater.runtime.time.monotonic
    # would mutate the shared stdlib module for every thread in the process.
    monkeypatch.setattr("kater.runtime.time", SimpleNamespace(monotonic=lambda: 0.0))

    runtime._maintenance_loop()

    assert len(light_calls) == target_wakes
    assert len(heavy_calls) == 1
    assert heavy_calls[0] == _HEAVY_EVERY_N_TICKS
    assert len(light_calls) > len(heavy_calls)


def test_runtime_start_still_spawns_janitor(monkeypatch, tmp_path) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("kater.migrations.ensure_migrated", lambda *_a, **_k: None)
    monkeypatch.setattr("kater.api.create_api_server", lambda *_a, **_k: MagicMock())
    monkeypatch.setattr("kater.websocket.create_ws_server", lambda *_a, **_k: MagicMock())
    monkeypatch.setattr("kater.mcp_server.build_sse_app", lambda *_a, **_k: MagicMock())

    class _FakeUvicornServer:
        def __init__(self, _config) -> None:
            self.should_exit = False

        def run(self) -> None:
            return None

    monkeypatch.setattr("uvicorn.Server", _FakeUvicornServer)
    monkeypatch.setattr("uvicorn.Config", lambda *_a, **_k: MagicMock())

    runtime = KaterRuntime(
        profile="core",
        listen=ListenConfig(host="127.0.0.1", api_port=29491, mcp_port=29490, ws_port=29492),
    )
    try:
        runtime.start()
        assert runtime._maintenance_thread is not None
        assert runtime._maintenance_thread.is_alive()
    finally:
        runtime.stop()
