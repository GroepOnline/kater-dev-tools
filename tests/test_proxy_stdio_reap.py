"""Regression tests for the zombie-leak fix in StdioBackend._disconnect.

When an MCP child process dies before stop()/disconnect() is called, the
previous implementation's `except OSError: pass` branch in _disconnect would
swallow the ProcessLookupError from terminate() and skip wait(), leaving the
defunct child as a zombie. The kater serve process (the long-lived parent
of 7-8 npm exec wrappers) accumulates one zombie per dead child until it
itself exits.

These tests pin the fix by:
- Spawning a real subprocess via _connect.
- Killing it from outside the proxy.
- Confirming the child is a zombie pre-disconnect.
- Calling _disconnect and asserting the zombie was reaped (no /proc/<pid>).
- Confirming the standard alive-then-stop path still works.
"""

import os
import signal
import time

import pytest

from kater.proxy.stdio_backend import StdioBackend


def _child_state(pid: int) -> str | None:
    """Return the State line from /proc/<pid>/status, or None if the PID is gone."""
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("State:"):
                    return line.split()[1]  # R, S, D, Z, T, X, I
    except FileNotFoundError:
        return None
    return None


def _pid_alive(pid: int) -> bool:
    """True if the PID is still visible to the kernel."""
    try:
        os.kill(pid, 0)
    except (OSError, ProcessLookupError):
        return False
    return True


def test_disconnect_reaps_already_dead_child():
    """Killing the child externally must not leak a zombie after _disconnect."""
    backend = StdioBackend(name="reap", command="sleep", args=["60"])
    backend._connect()
    pid = backend._proc.pid
    assert pid > 0
    assert _pid_alive(pid)

    # Kill the child from outside the proxy.
    os.kill(pid, signal.SIGKILL)
    # Give the kernel a moment to mark it defunct.
    for _ in range(50):
        state = _child_state(pid)
        if state == "Z":
            break
        time.sleep(0.02)
    else:
        pytest.fail(
            f"child {pid} did not become a zombie within 1s; state={state!r}"
        )

    # Now disconnect — this is the call under test.
    backend._disconnect()

    # After _disconnect, the zombie must be reaped: /proc/<pid> is gone
    # and the PID is no longer visible to the kernel.
    assert _child_state(pid) is None, f"zombie {pid} still in /proc after reap"
    assert not _pid_alive(pid), f"PID {pid} still alive after reap"


def test_disconnect_terminates_alive_child():
    """Standard path: a living child is terminated and reaped cleanly."""
    backend = StdioBackend(name="alive", command="sleep", args=["60"])
    backend._connect()
    pid = backend._proc.pid
    assert _pid_alive(pid)

    backend._disconnect()

    # Give the kernel a moment to deliver SIGTERM and reap.
    deadline = time.time() + 2.0
    while time.time() < deadline and _pid_alive(pid):
        time.sleep(0.05)
    assert not _pid_alive(pid), f"PID {pid} still alive after _disconnect"


def test_disconnect_idempotent_when_already_disconnected():
    """Calling _disconnect twice must not raise and must not leak a zombie."""
    backend = StdioBackend(name="idem", command="sleep", args=["60"])
    backend._connect()
    pid = backend._proc.pid

    backend._disconnect()
    # Second call: self._proc is None, so _disconnect is a no-op.
    backend._disconnect()

    assert not _pid_alive(pid)


def test_stop_after_external_kill_does_not_leak_zombie():
    """Full start()/stop() lifecycle where the child dies between start and stop."""
    backend = StdioBackend(name="lifecycle", command="sleep", args=["60"])
    backend._connect()
    pid = backend._proc.pid

    # External kill before any graceful stop.
    os.kill(pid, signal.SIGKILL)
    for _ in range(50):
        if _child_state(pid) == "Z":
            break
        time.sleep(0.02)

    # Public stop() should clean up without leaking a zombie.
    backend.stop()

    assert _child_state(pid) is None
    assert not _pid_alive(pid)
