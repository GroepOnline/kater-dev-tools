"""Cross-process Computer acceptance harness."""

from __future__ import annotations

import json
import os
import shutil
import signal
import socket
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@dataclass(frozen=True, slots=True)
class ProcessSpec:
    name: str
    command: tuple[str, ...]
    state_dir: Path
    env: dict[str, str] = field(default_factory=dict)
    cwd: Path | None = None


@dataclass
class ComputerAcceptanceHarness:
    """Own three real OS process groups and preserve diagnostics on failure."""

    udo_checkout: Path
    processes: tuple[ProcessSpec, ...]
    _children: list[tuple[ProcessSpec, subprocess.Popen[str]]] = field(
        default_factory=list, init=False
    )

    @classmethod
    def from_environment(cls) -> ComputerAcceptanceHarness:
        raw = os.environ.get("KATER_UDO_CHECKOUT")
        if not raw:
            raise RuntimeError("KATER_UDO_CHECKOUT is required for the real acceptance lane")
        checkout = Path(raw).resolve()
        if not checkout.is_dir() or not (checkout / ".git").exists():
            raise RuntimeError(f"invalid UDO checkout: {checkout}")
        return cls(checkout, ())

    def start(self, names: tuple[str, ...] | None = None) -> None:
        selected = (
            self.processes
            if names is None
            else tuple(spec for spec in self.processes if spec.name in names)
        )
        if names is None and len(self.processes) != 3:
            raise RuntimeError(
                "acceptance harness requires controller, guest, and Kater process specs"
            )
        for spec in selected:
            if any(existing.name == spec.name for existing, _ in self._children):
                continue
            spec.state_dir.mkdir(parents=True, exist_ok=True)
            env = {**os.environ, **spec.env}
            with (
                (spec.state_dir / "stdout.log").open("w", encoding="utf-8") as stdout,
                (spec.state_dir / "stderr.log").open("w", encoding="utf-8") as stderr,
            ):
                child = subprocess.Popen(
                    spec.command,
                    cwd=spec.cwd or self.udo_checkout,
                    env=env,
                    stdout=stdout,
                    stderr=stderr,
                    text=True,
                    start_new_session=True,
                )
            self._children.append((spec, child))
            (spec.state_dir / "process.pid").write_text(str(child.pid), encoding="utf-8")

    @staticmethod
    def _diagnostics(child: subprocess.Popen[str], state_dir: Path) -> str:
        _ = child
        stdout_path = state_dir / "stdout.log"
        stderr_path = state_dir / "stderr.log"
        stdout = (
            stdout_path.read_text(encoding="utf-8", errors="replace")
            if stdout_path.exists()
            else ""
        )
        stderr = (
            stderr_path.read_text(encoding="utf-8", errors="replace")
            if stderr_path.exists()
            else ""
        )
        return f"stdout:\n{stdout[-8000:]}\nstderr:\n{stderr[-12000:]}"

    def wait_http(self, url: str, *, timeout: float = 20.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            for spec, child in self._children:
                if child.poll() is not None:
                    raise AssertionError(
                        f"{spec.name} exited with {child.returncode}\n"
                        f"{self._diagnostics(child, spec.state_dir)}"
                    )
            try:
                with urlopen(url, timeout=0.5) as response:
                    if response.status < 500:
                        return
            except HTTPError as error:
                if error.code < 500:
                    return
                time.sleep(0.05)
            except (OSError, URLError):
                time.sleep(0.05)
        details = "\n\n".join(
            f"{spec.name}: pid={child.pid} returncode={child.poll()}\n"
            f"{self._diagnostics(child, spec.state_dir)}"
            for spec, child in self._children
        )
        raise AssertionError(f"timed out waiting for {url}\n{details}")

    def stop(self, name: str, *, preserve_state: bool = True) -> None:
        matches = [(spec, child) for spec, child in self._children if spec.name == name]
        if not matches:
            raise AssertionError(f"acceptance process is not running: {name}")
        for spec, child in reversed(matches):
            if child.poll() is None:
                try:
                    os.killpg(child.pid, signal.SIGTERM)
                    child.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    try:
                        os.killpg(child.pid, signal.SIGKILL)
                    except OSError:
                        pass
                    child.wait(timeout=5)
            self._children.remove((spec, child))
            if not preserve_state:
                shutil.rmtree(spec.state_dir, ignore_errors=True)

    def wait_stopped(self, name: str, *, timeout: float = 10.0) -> None:
        match = next(
            ((spec, child) for spec, child in self._children if spec.name == name),
            None,
        )
        if match is None:
            raise AssertionError(f"acceptance process is unknown: {name}")
        spec, child = match
        try:
            child.wait(timeout=timeout)
        except subprocess.TimeoutExpired as error:
            raise AssertionError(
                f"{name} did not stop after controller cleanup\n"
                f"{self._diagnostics(child, spec.state_dir)}"
            ) from error

    def close(self) -> None:
        for spec, _child in tuple(reversed(self._children)):
            self.stop(spec.name)
        self.assert_clean()
        for spec in self.processes:
            shutil.rmtree(spec.state_dir, ignore_errors=True)
        self._children.clear()

    def assert_clean(self) -> None:
        leaked = [(spec.name, child.pid) for spec, child in self._children if child.poll() is None]
        if leaked:
            raise AssertionError(f"acceptance child processes leaked: {leaked}")

    def __enter__(self) -> ComputerAcceptanceHarness:
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.close()


def json_request(
    url: str,
    method: str = "GET",
    body: dict[str, object] | None = None,
    token: str | None = None,
) -> dict[str, object]:
    headers = {"Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        url,
        method=method,
        headers=headers,
        data=None if body is None else json.dumps(body).encode(),
    )
    with urlopen(request, timeout=10) as response:
        payload = json.loads(response.read().decode())
    if not isinstance(payload, dict):
        raise AssertionError(f"expected JSON object from {url}, got {payload!r}")
    return payload
