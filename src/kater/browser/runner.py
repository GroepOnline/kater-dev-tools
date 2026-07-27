"""Single-thread executor for thread-affine browser drivers.

Playwright's sync API is bound to the thread that created it, while Kater
serves HTTP/MCP requests from a thread pool. Every provider call is therefore
funnelled through one dedicated worker thread via this runner.

If a job exceeds its timeout the worker is abandoned (it may still be blocked
inside Playwright) and a fresh worker is started so later calls are not
poisoned by the wedged thread.
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
        self._generation = 0
        self._restarts = 0

    @property
    def running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    @property
    def restarts(self) -> int:
        return self._restarts

    @property
    def generation(self) -> int:
        return self._generation

    def start(self) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._spawn_worker_unlocked()

    def submit(self, fn: Callable[[], T], *, timeout: float | None = None) -> T:
        """Execute ``fn`` on the worker thread and return its result.

        Raises ``TimeoutError`` when the call does not finish in ``timeout``
        seconds. The wedged worker is abandoned and replaced so later submits
        are not stuck behind it.
        """
        self.start()
        future: Future[T] = Future()
        with self._lock:
            generation = self._generation
            self._queue.put((fn, future))
        try:
            return future.result(timeout=timeout)
        except TimeoutError:
            with self._lock:
                if generation == self._generation:
                    self._replace_worker_unlocked()
            raise

    def replace_worker(self) -> None:
        """Abandon the current worker (if any) and start a fresh one."""
        with self._lock:
            self._replace_worker_unlocked()

    def stop(self, *, timeout: float = 10.0) -> None:
        with self._lock:
            thread = self._thread
            q = self._queue
            self._thread = None
            # Invalidate in-flight submit() generations so a late TimeoutError
            # after stop cannot resurrect a worker via _replace_worker_unlocked.
            self._generation += 1
        if thread is None:
            return
        q.put(None)
        thread.join(timeout=timeout)

    def _spawn_worker_unlocked(self) -> None:
        self._queue = queue.Queue()
        q = self._queue
        thread = threading.Thread(
            target=self._loop, args=(q,), name=self._name, daemon=True
        )
        self._thread = thread
        thread.start()

    def _replace_worker_unlocked(self) -> None:
        # Leave the old thread alone: it may be blocked inside ``fn``, so
        # putting None on its queue would not run until the call returns.
        # Daemon threads are abandoned; Playwright objects bound to them must
        # be dropped by the provider (see PlaywrightProvider._invalidate_after_timeout).
        self._generation += 1
        self._restarts += 1
        self._spawn_worker_unlocked()

    def _loop(self, q: queue.Queue[_Job | None]) -> None:
        # Bind the queue at thread start so a later replace_worker() cannot
        # make this abandoned worker drain the new queue.
        while True:
            job = q.get()
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
