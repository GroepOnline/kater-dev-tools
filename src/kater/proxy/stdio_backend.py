from __future__ import annotations

import json
import os
import subprocess
import threading
import time
from typing import Any

from kater.proxy.base import BackendOperationalError, BaseBackend


class StdioBackend(BaseBackend):
    _SAFE_ENV_PASSTHROUGH = frozenset(
        {
            "PATH",
            "HOME",
            "LANG",
            "LC_ALL",
            "LC_CTYPE",
            "TMPDIR",
            "TERM",
            "SystemRoot",
            "PATHEXT",
            "USERPROFILE",
        }
    )

    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
        timeout: float = 30.0,
    ) -> None:
        super().__init__()
        self.name = name
        self._command = command
        self._args = args or []
        self._env = self._build_safe_env(env)
        self._timeout = timeout
        self._proc: subprocess.Popen[bytes] | None = None
        self._next_id = 1
        self._stderr_thread: threading.Thread | None = None

    @classmethod
    def _build_safe_env(cls, env: dict[str, str] | None) -> dict[str, str]:
        safe = {key: os.environ[key] for key in cls._SAFE_ENV_PASSTHROUGH if key in os.environ}
        safe.update(env or {})
        return safe

    def _connect(self) -> None:
        self._proc = subprocess.Popen(
            [self._command, *self._args],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=self._env,
        )
        self._start_stderr_drain()

    def _disconnect(self) -> None:
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
                self._proc.wait(timeout=2)
            except OSError:
                pass
            self._proc = None
        self._stderr_thread = None

    def _start_stderr_drain(self) -> None:
        if not self._proc or not self._proc.stderr:
            return

        def _drain() -> None:
            try:
                proc = self._proc
                if not proc or not proc.stderr:
                    return
                for _line in iter(proc.stderr.readline, b""):
                    pass
            except (OSError, ValueError):
                pass

        self._stderr_thread = threading.Thread(target=_drain, daemon=True)
        self._stderr_thread.start()

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        proc = self._proc
        if not proc or not proc.stdin or not proc.stdout:
            error = "backend not started"
            self._status.error = error
            self._status.healthy = False
            raise BackendOperationalError(error, fallback_safe=True)
        stdin = proc.stdin
        stdout = proc.stdout

        # MCP notifications (method starts with "notifications/") carry no id
        # and expect no response — fire and forget, otherwise we'd block until
        # timeout waiting for a reply that never comes.
        if method.startswith("notifications/"):
            msg: dict[str, Any] = {"jsonrpc": "2.0", "method": method}
            if params:
                msg["params"] = params
            with self._lock:
                try:
                    stdin.write((json.dumps(msg) + "\n").encode())
                    stdin.flush()
                except OSError as exc:
                    self._status.error = str(exc)
                    self._status.healthy = False
                    raise BackendOperationalError(str(exc), fallback_safe=False) from exc
            return {"result": {}}

        msg = {
            "jsonrpc": "2.0",
            "id": self._next_id,
            "method": method,
        }
        if params:
            msg["params"] = params
        self._next_id += 1

        with self._lock:
            try:
                stdin.write((json.dumps(msg) + "\n").encode())
                stdin.flush()

                deadline = time.time() + self._timeout
                while time.time() < deadline:
                    line = stdout.readline()
                    if not line:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    data = json.loads(line.decode())
                    if not isinstance(data, dict):
                        raise ValueError("unexpected malformed stdio response")
                    if data.get("id") == msg["id"]:
                        if data.get("jsonrpc") != "2.0" or (
                            "result" not in data and "error" not in data
                        ):
                            raise ValueError("unexpected malformed stdio response")
                        return data
                error = "timeout waiting for response"
                self._status.error = error
                self._status.healthy = False
                raise BackendOperationalError(error, fallback_safe=False)
            except BackendOperationalError:
                raise
            except (OSError, ValueError) as exc:
                self._status.error = str(exc)
                self._status.healthy = False
                raise BackendOperationalError(str(exc), fallback_safe=False) from exc
