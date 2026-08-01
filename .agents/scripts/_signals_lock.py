"""Advisory file lock shared by the signals.yaml writers.

`taste-signal.py` and `eval-score.py --write-refresh-signal` both do a
load-append-save cycle on `.agents/registry/signals.yaml`. Without a lock two
concurrent writers (e.g. the scheduled eval and a human signal) read the same
snapshot and the last writer silently drops the other's entry. Both scripts wrap
their whole read-modify-write in `file_lock(SIGNALS)` so they serialize instead.

The lock is an OS advisory lock on a sidecar `<name>.lock` file, so it is
released automatically if a writer crashes (no stale lock files to reap).
"""
from __future__ import annotations

import contextlib
import os
from collections.abc import Iterator
from pathlib import Path

try:  # POSIX
    import fcntl
except ImportError:  # pragma: no cover - Windows
    fcntl = None  # type: ignore[assignment]

try:  # Windows
    import msvcrt
except ImportError:  # pragma: no cover - POSIX
    msvcrt = None  # type: ignore[assignment]


@contextlib.contextmanager
def file_lock(target: Path) -> Iterator[None]:
    """Hold an exclusive lock for the duration of a read-modify-write on ``target``."""
    lock_path = target.with_name(target.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_RDWR | os.O_CREAT)
    try:
        if fcntl is not None:
            fcntl.flock(fd, fcntl.LOCK_EX)
        elif msvcrt is not None:  # pragma: no cover - Windows
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(fd, fcntl.LOCK_UN)
            elif msvcrt is not None:  # pragma: no cover - Windows
                with contextlib.suppress(OSError):
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    finally:
        os.close(fd)
