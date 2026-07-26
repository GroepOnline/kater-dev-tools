"""Single-thread executor for thread-affine browser drivers.

Playwright's sync API is bound to the thread that created it, while Kater
serves HTTP/MCP requests from a thread pool. Every provider call is therefore
funnelled through one dedicated worker thread via this runner.
"""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from concurrent.futures import Future
from typing import Any, TypeVar

T = TypeVar("T")

_Job = tuple[Callable[[], Any], "Future[Any]"]


class CallRunner:
    """Run submitted callables on one long-lived worker thread, in order."""

    def __init__(self, name: str = "kater-browser") -> None:
        self._name = name
        self._queue: queue.Queue[_Job | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._queue = queue.Queue()
            thread = threading.Thread(target=self._loop, name=self._name, daemon=True)
            self._thread = thread
            thread.start()

    def submit(self, fn: Callable[[], T], *, timeout: float | None = None) -> T:
        """Execute ``fn`` on the worker thread and return its result.

        Raises ``TimeoutError`` when the call does not finish in ``timeout``
        seconds; the job itself keeps running and later jobs queue behind it.
        """
        self.start()
        future: Future[T] = Future()
        self._queue.put((fn, future))
        return future.result(timeout=timeout)

    def stop(self, *, timeout: float = 10.0) -> None:
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is None:
            return
        self._queue.put(None)
        thread.join(timeout=timeout)

    def _loop(self) -> None:
        while True:
            job = self._queue.get()
            if job is None:
                return
            fn, future = job
            if not future.set_running_or_notify_cancel():
                continue
            try:
                future.set_result(fn())
            except Exception as exc:
                future.set_exception(exc)
            except BaseException as exc:
                # Interpreter-level signals still have to unblock the caller.
                future.set_exception(exc)
                raise
