from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

import pytest

from kater.runtime import KaterRuntime
from kater.settings import ListenConfig


def test_runtime_start_stop_health() -> None:
    listen = ListenConfig(
        host="127.0.0.1",
        api_port=19091,
        mcp_port=19090,
        ws_port=19092,
    )
    runtime = KaterRuntime(profile="core", listen=listen)
    health_url = f"http://{listen.host}:{listen.api_port}/health"

    try:
        runtime.start()
        time.sleep(0.5)

        deadline = time.monotonic() + 2.0
        last_error: Exception | None = None
        while time.monotonic() < deadline:
            try:
                with urllib.request.urlopen(health_url, timeout=0.5) as response:
                    payload = json.loads(response.read().decode())
                assert payload["status"] == "ok"
                break
            except (urllib.error.URLError, OSError) as exc:
                last_error = exc
                time.sleep(0.05)
        else:
            pytest.fail(f"API health check never succeeded: {last_error}")

        runtime.stop()

        with pytest.raises((urllib.error.URLError, OSError)):
            urllib.request.urlopen(health_url, timeout=0.5)
    finally:
        runtime.stop()
