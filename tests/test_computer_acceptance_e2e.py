"""Named, real cross-process Kater x UDO Computer acceptance test."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from jsonschema import Draft202012Validator, FormatChecker

from kater.capabilities.computer import (
    GENERATED_CONTRACT_DIGEST,
    VENDORED_CONTRACT,
    load_computer_manifests_from_udo,
)
from tests.acceptance.computer_lane import (
    ComputerAcceptanceHarness,
    ProcessSpec,
    free_port,
    json_request,
)


def _invoke(
    kater_url: str,
    token: str,
    capability_id: str,
    ids: dict[str, object],
    arguments: dict[str, object],
) -> dict[str, object]:
    body = {
        "name": capability_id,
        "arguments": {
            **ids,
            "arguments": arguments,
            "deadline_at": (datetime.now(UTC) + timedelta(minutes=15))
            .isoformat()
            .replace("+00:00", "Z"),
            "idempotency_key": "idem_"
            + hashlib.sha256(
                json.dumps([capability_id, arguments], sort_keys=True).encode()
            ).hexdigest()[:32],
        },
    }
    return json_request(f"{kater_url}/tools/call", "POST", body, token)


def test_computer_acceptance_cross_process(tmp_path: Path) -> None:
    """Exercise canonical controller, real guest, and production Kater routing together."""
    checkout = Path(os.environ.get("KATER_UDO_CHECKOUT", "")).resolve()
    assert os.environ.get("KATER_UDO_CHECKOUT"), "KATER_UDO_CHECKOUT is required"
    assert checkout.is_dir() and (checkout / ".git").exists(), f"invalid UDO checkout: {checkout}"
    manifests = load_computer_manifests_from_udo(
        checkout, expected_digest=GENERATED_CONTRACT_DIGEST
    )
    assert manifests, "UDO generated contract is empty"
    generated = checkout / "platform/agent-control-plane/packages/protocol/generated"
    for filename in (
        "computer-capabilities.generated.json",
        "error-envelope.json",
        "guest-invocation-result.schema.json",
        "guest-invocation.schema.json",
        "staged-artifact.schema.json",
    ):
        udo_path = (
            generated / filename
            if filename == "computer-capabilities.generated.json"
            else generated / "contracts" / filename
        )
        assert (VENDORED_CONTRACT.parent / filename).read_bytes() == udo_path.read_bytes()

    controller_port, guest_port, kater_port = free_port(), free_port(), free_port()
    controller_token = "controller-acceptance-token"
    session_id = "csess_" + "a" * 32
    machine_id = "mach_" + "b" * 32
    workspace_id = "ws_" + "c" * 32
    owner_hash = "d" * 64
    guest_root = tmp_path / "workspace"
    guest_root.mkdir()
    subprocess.run(["git", "init", "-q", str(guest_root)], check=True)
    subprocess.run(
        ["git", "-C", str(guest_root), "config", "user.email", "acceptance@example.test"],
        check=True,
    )
    subprocess.run(["git", "-C", str(guest_root), "config", "user.name", "Acceptance"], check=True)

    controller_url = f"http://127.0.0.1:{controller_port}"
    guest_url = f"http://127.0.0.1:{guest_port}"
    kater_url = f"http://127.0.0.1:{kater_port}"
    controller_dir, guest_dir, kater_dir = (
        tmp_path / name for name in ("controller", "guest", "kater")
    )
    base_env = {
        "GENERATED_CONTRACT_DIGEST": GENERATED_CONTRACT_DIGEST,
        "PYTHONUNBUFFERED": "1",
    }
    controller = ProcessSpec(
        "controller",
        (
            str(
                checkout
                / "platform/agent-control-plane/apps/session-controller/node_modules/.bin/tsx"
            ),
            str(
                checkout / "platform/agent-control-plane/apps/session-controller/test/fixtures/"
                "acceptance-controller.ts"
            ),
        ),
        controller_dir,
        {
            **base_env,
            "CONTROLLER_TOKEN": controller_token,
            "GUEST_ORIGIN": guest_url,
            "GUEST_PID_FILE": str(guest_dir / "process.pid"),
            "PORT": str(controller_port),
        },
    )
    guest = None
    kater = None
    harness = ComputerAcceptanceHarness(checkout, (controller,))
    harness.processes = (controller,)
    harness.start(("controller",))
    try:
        harness.wait_http(f"{controller_url}/v1/computer-sessions/{session_id}/events")
        spec = {
            "computerSessionId": session_id,
            "machineId": machine_id,
            "workspaceId": workspace_id,
            "workspaceGeneration": 1,
            "ownerHash": owner_hash,
            "ownerSub": "acceptance-operator",
            "namespace": "agent-sessions",
            "image": "registry/acceptance@sha256:" + "e" * 64,
            "maxRuntimeSeconds": 900,
        }
        created = json_request(
            f"{controller_url}/v1/computer-sessions/{session_id}", "PUT", spec, controller_token
        )
        assert created["session"]["state"] == "running"  # type: ignore[index]
        credential = json_request(
            f"{controller_url}/v1/computer-sessions/{session_id}/credentials",
            "POST",
            {"capabilityIds": [item.capability_id for item in manifests], "ttlSeconds": 600},
            controller_token,
        )
        guest_token = str(credential["plaintextToken"])
        descriptor = credential["descriptor"]
        assert isinstance(descriptor, dict) and "token" not in descriptor

        guest = ProcessSpec(
            "guest",
            (
                sys.executable,
                "-m",
                "computer_guest_agent",
                "serve",
                "--host",
                "127.0.0.1",
                "--port",
                str(guest_port),
            ),
            guest_dir,
            {
                **base_env,
                "PYTHONPATH": str(checkout / "platform/agent-control-plane/apps/guest-agent/src"),
                "SESSION_ID": session_id,
                "MACHINE_ID": machine_id,
                "GUEST_AGENT_CREDENTIAL_DESCRIPTOR": json.dumps(descriptor),
                "GUEST_WORKSPACE_ROOT": str(guest_root),
                "GUEST_AGENT_STATE_DIR": str(guest_dir / "state"),
            },
        )
        kater = ProcessSpec(
            "kater",
            (sys.executable, "-m", "tests.acceptance.kater_server"),
            kater_dir,
            {
                **base_env,
                "PYTHONPATH": str(Path.cwd() / "src") + os.pathsep + str(Path.cwd()),
                "KATER_UDO_CHECKOUT": str(checkout),
                "GUEST_ORIGIN": guest_url,
                "GUEST_AGENT_TOKEN": guest_token,
                "KATER_PORT": str(kater_port),
            },
            cwd=kater_dir,
        )
        harness.processes = (controller, guest, kater)
        harness.start(("guest", "kater"))
        harness.wait_http(f"{guest_url}/healthz")
        harness.wait_http(f"{kater_url}/tools/list")
        ids = {
            "computer_session_id": session_id,
            "machine_id": machine_id,
            "workspace_id": workspace_id,
            "workspace_generation": 1,
        }
        listed = json_request(f"{kater_url}/tools/list")
        names = {item["name"] for item in listed["tools"]}  # type: ignore[index]
        assert {item.capability_id for item in manifests} <= names

        written = _invoke(
            kater_url,
            guest_token,
            "filesystem.write",
            ids,
            {"path": "acceptance.txt", "content": "cross-process\n"},
        )
        assert written["status"] == "succeeded"
        generation = int(written["result"]["workspace_generation"])  # type: ignore[index]
        ids["workspace_generation"] = generation
        read = _invoke(kater_url, guest_token, "filesystem.read", ids, {"path": "acceptance.txt"})
        assert read["status"] == "succeeded" and read["result"]["content"] == "cross-process\n"  # type: ignore[index]
        status = _invoke(kater_url, guest_token, "git.status", ids, {})
        assert status["status"] == "succeeded"

        opened = _invoke(kater_url, guest_token, "terminal.open", ids, {"shell": "/bin/sh"})
        terminal_id = str(opened["result"]["terminal_id"])  # type: ignore[index]
        _invoke(
            kater_url,
            guest_token,
            "terminal.input",
            ids,
            {"terminal_id": terminal_id, "data": "printf acceptance-terminal\\n\n"},
        )
        output = ""
        offset = 0
        for _ in range(30):
            polled = _invoke(
                kater_url,
                guest_token,
                "terminal.read",
                ids,
                {"terminal_id": terminal_id, "offset": offset},
            )
            output += str(polled["result"].get("data", ""))  # type: ignore[index]
            offset = int(polled["result"].get("offset", offset))  # type: ignore[index]
            if "acceptance-terminal" in output:
                break
            time.sleep(0.05)
        assert "acceptance-terminal" in output
        _invoke(kater_url, guest_token, "terminal.close", ids, {"terminal_id": terminal_id})

        exported = _invoke(
            kater_url,
            guest_token,
            "artifact.export",
            ids,
            {"artifact_name": "acceptance", "paths": ["acceptance.txt"]},
        )
        staged = exported["result"]
        assert isinstance(staged, dict) and staged["state"] == "staged"
        artifact_store = tmp_path / "artifact-store"
        artifact_store.mkdir()
        promotion_input = tmp_path / "promotion-input.json"
        promotion_input.write_text(
            json.dumps(
                {
                    "staged": staged,
                    "activeSession": {
                        "computerSessionId": session_id,
                        "workspaceId": workspace_id,
                        "workspaceGeneration": generation,
                    },
                    "guestBaseUrl": guest_url,
                    "token": guest_token,
                    "storeRoot": str(artifact_store),
                }
            ),
            encoding="utf-8",
        )
        promotion = subprocess.run(
            [
                str(
                    checkout
                    / "platform/agent-control-plane/apps/session-controller/node_modules/.bin/tsx"
                ),
                str(
                    checkout / "platform/agent-control-plane/apps/session-controller/test/fixtures/"
                    "promote-artifact.ts"
                ),
                str(promotion_input),
            ],
            cwd=checkout,
            check=True,
            capture_output=True,
            text=True,
        )
        promoted = json.loads(promotion.stdout)
        assert promoted["state"] == "ready"
        ready = artifact_store / promoted["store_key"]
        raw = ready.read_bytes()
        assert len(raw) == staged["size_bytes"]
        assert "sha256:" + hashlib.sha256(raw).hexdigest() == staged["content_sha256"]
        duplicate = subprocess.run(
            promotion.args,
            cwd=checkout,
            check=False,
            capture_output=True,
            text=True,
        )
        assert duplicate.returncode != 0
        assert "artifact_already_promoted" in duplicate.stderr
        assert ready.read_bytes() == raw

        cleaned = _invoke(
            kater_url,
            guest_token,
            "artifact.cleanup",
            ids,
            {"artifact_id": staged["artifact_id"]},
        )
        assert cleaned["status"] == "succeeded", cleaned
        pull = Request(
            f"{guest_url}/artifact/pull?artifact_id={staged['artifact_id']}",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        try:
            urlopen(pull, timeout=10)
        except HTTPError as error:
            assert error.code == 404
        else:
            raise AssertionError("cleaned staged artifact remained pullable")

        json_request(
            f"{kater_url}/capabilities/revoke",
            "POST",
            {"capability_id": "filesystem.read", "version": "1.0.0"},
        )
        persisted = json_request(
            f"{kater_url}/capabilities/status?capability_id=filesystem.read&version=1.0.0"
        )
        assert persisted["lifecycle_state"] == "revoked"
        harness.stop("kater")
        harness.start(("kater",))
        harness.wait_http(f"{kater_url}/tools/list")
        persisted_after_restart = json_request(
            f"{kater_url}/capabilities/status?capability_id=filesystem.read&version=1.0.0"
        )
        assert persisted_after_restart["lifecycle_state"] == "revoked"
        after_revoke = json_request(f"{kater_url}/tools/list")
        assert "filesystem.read" not in {item["name"] for item in after_revoke["tools"]}  # type: ignore[index]
        denied = _invoke(kater_url, guest_token, "filesystem.read", ids, {"path": "acceptance.txt"})
        assert denied["status"] == "denied" and denied["error"]["code"] == "capability_denied"  # type: ignore[index]

        json_request(
            f"{controller_url}/v1/computer-sessions/{session_id}",
            "DELETE",
            {"ownerHash": owner_hash},
            controller_token,
        )
        harness.wait_stopped("guest")
        events = json_request(
            f"{controller_url}/v1/computer-sessions/{session_id}/events", token=controller_token
        )
        assert [event["state"] for event in events["events"]] == [  # type: ignore[index]
            "requested",
            "allocating",
            "guest_connecting",
            "ready",
            "running",
            "deleting",
            "deleted",
        ]
        ready.unlink()
        assert not ready.exists()
        evidence = {
            "contract_digest": GENERATED_CONTRACT_DIGEST,
            "verified_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "status": "passed",
            "session": {
                "computer_session_id": session_id,
                "lifecycle": [event["state"] for event in events["events"]],  # type: ignore[index]
            },
            "calls": [
                {"capability_id": capability_id, "status": "succeeded"}
                for capability_id in (
                    "filesystem.write",
                    "filesystem.read",
                    "git.status",
                    "terminal.open",
                    "terminal.input",
                    "terminal.read",
                    "terminal.close",
                    "artifact.export",
                    "artifact.cleanup",
                )
            ],
            "artifact": {
                "artifact_id": staged["artifact_id"],
                "state": "ready",
                "content_sha256": staged["content_sha256"],
                "size_bytes": staged["size_bytes"],
                "workspace_generation": staged["workspace_generation"],
            },
            "control": {
                "revoked_capability_id": "filesystem.read",
                "discovery_omitted": True,
                "next_call_status": "denied",
                "error_code": "capability_denied",
                "persisted_after_restart": True,
            },
            "cleanup": {
                "session_state": "deleted",
                "guest_stopped": True,
                "staged_artifact_removed": True,
                "ready_artifact_removed": True,
            },
        }
        evidence_schema = json.loads(
            (
                checkout / "platform/agent-control-plane/packages/protocol/generated/contracts/"
                "computer-acceptance-evidence.schema.json"
            ).read_text(encoding="utf-8")
        )
        errors = list(
            Draft202012Validator(evidence_schema, format_checker=FormatChecker()).iter_errors(
                evidence
            )
        )
        assert not errors, errors
        if evidence_path := os.environ.get("COMPUTER_ACCEPTANCE_EVIDENCE"):
            Path(evidence_path).write_text(
                json.dumps(evidence, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
    finally:
        harness.close()
        shutil.rmtree(guest_root / ".guest-agent", ignore_errors=True)
    assert not any(path.exists() for path in (controller_dir, guest_dir, kater_dir))
    assert not (guest_root / ".guest-agent").exists()
