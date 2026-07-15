from __future__ import annotations

import io
import json
import urllib.error
from datetime import UTC, datetime, timedelta

from kater.capabilities.computer import (
    VENDORED_CONTRACT,
    ComputerConnector,
    load_computer_manifests,
    register_computer_contract,
)
from kater.capabilities.models import LifecycleState
from kater.capabilities.registry import CapabilityRegistry
from kater.capabilities.store import (
    get_capability,
    set_capability_lifecycle,
    upsert_capability,
)

IDS = {
    "computer_session_id": "csess_" + "a" * 32,
    "machine_id": "mach_" + "b" * 32,
    "workspace_id": "ws_" + "c" * 32,
}


class _Response:
    def __init__(self, payload: dict) -> None:
        self._raw = json.dumps(payload).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def read(self) -> bytes:
        return self._raw


def _arguments(capability_id: str, arguments: dict, *, mutation: bool = False) -> dict:
    value = {
        **IDS,
        "workspace_generation": 1,
        "deadline_at": (datetime.now(UTC) + timedelta(seconds=30)).isoformat(),
        "arguments": arguments,
    }
    if mutation:
        value["idempotency_key"] = "idem_" + "d" * 32
    return value


def _connector(opener) -> ComputerConnector:
    manifests = load_computer_manifests(VENDORED_CONTRACT)
    registry = CapabilityRegistry()
    for manifest in manifests:
        registry.register(manifest)
    return ComputerConnector(
        manifests,
        registry,
        base_url="http://127.0.0.1:1",
        auth_token="acceptance-bearer",
        opener=opener,
    )


def test_contract_refresh_keeps_persisted_revoke_non_invocable(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = load_computer_manifests(VENDORED_CONTRACT)[0]
    upsert_capability(manifest)
    set_capability_lifecycle(manifest.capability_id, manifest.version, LifecycleState.REVOKED)
    registry = CapabilityRegistry()

    register_computer_contract(VENDORED_CONTRACT, registry)

    assert (
        get_capability(manifest.capability_id, manifest.version).lifecycle_state
        is LifecycleState.REVOKED
    )  # type: ignore[union-attr]
    assert registry.is_invocable(manifest.capability_id)[0] is False


def test_read_retries_one_predispatch_connection_failure_with_same_request_id() -> None:
    calls: list[dict] = []

    def opener(request, *, timeout):
        del timeout
        calls.append(json.loads(request.data))
        if len(calls) == 1:
            raise urllib.error.URLError(ConnectionRefusedError("not listening yet"))
        return _Response(
            {
                "protocol_version": "0.1.0-m0",
                "status": "succeeded",
                "request_id": calls[0]["request_id"],
                "result": {
                    "content": "ready",
                    "size": 5,
                    "truncated": False,
                    "workspace_generation": 1,
                },
                "artifacts": [],
            }
        )

    result = _connector(opener).call(
        "filesystem.read", _arguments("filesystem.read", {"path": "proof.txt"})
    )

    assert result["status"] == "succeeded"
    assert [call["attempt"] for call in calls] == [1, 2]
    assert calls[0]["request_id"] == calls[1]["request_id"]
    assert calls[0]["deadline_at"] == calls[1]["deadline_at"]


def test_guest_http_denial_body_is_preserved_as_canonical_result() -> None:
    denial = {
        "protocol_version": "0.1.0-m0",
        "status": "denied",
        "request_id": "req_" + "e" * 32,
        "error": {
            "code": "authentication_failed",
            "message": "missing or invalid bearer token",
            "retryable": False,
        },
    }

    def opener(request, *, timeout):
        del timeout
        request_id = json.loads(request.data)["request_id"]
        denial["request_id"] = request_id
        raise urllib.error.HTTPError(
            "http://127.0.0.1:1/filesystem/read",
            401,
            "Unauthorized",
            {},
            io.BytesIO(json.dumps(denial).encode()),
        )

    result = _connector(opener).call(
        "filesystem.read", _arguments("filesystem.read", {"path": "proof.txt"})
    )

    assert result["status"] == "denied"
    assert result["error"]["code"] == "authentication_failed"
