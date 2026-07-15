"""Schema-driven Computer connector primitives owned by Kater.

The JSON catalog is a temporary digest-checked seam until the sibling UDO checkout
publishes its generated contract artifact.  Kater does not define a second contract.
"""

from __future__ import annotations

import hashlib
import json
import secrets
import urllib.error
import urllib.request
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from threading import RLock
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from kater.capabilities.models import (
    CapabilityManifest,
    CapabilityTransport,
    LifecycleState,
    RiskClass,
)
from kater.profiles import McpServerConfig, RiskLevel, ToolSource, Transport

GENERATED_CONTRACT_DIGEST = (
    "sha256:0d66b7a51ce1e6b8c23912e0d583e6fec608057d34c51aa4d1da8e81c66eef44"
)
VENDORED_CONTRACT = Path(__file__).with_name("generated") / "computer-capabilities.generated.json"
COMPUTER_ID_PREFIXES = ("computer.", "filesystem.", "git.", "terminal.", "artifact.")
_LIFECYCLE_GATE = RLock()

_SCHEMA_DIR = VENDORED_CONTRACT.parent
_SCHEMA_FILENAMES = (
    "staged-artifact.schema.json",
    "guest-invocation.schema.json",
    "guest-invocation-result.schema.json",
    "error-envelope.json",
)


def _load_schema_registry() -> Registry:
    registry = Registry()
    for filename in _SCHEMA_FILENAMES:
        try:
            schema = json.loads((_SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ContractDigestError(f"cannot load vendored schema {filename}: {exc}") from exc
        if not isinstance(schema, dict) or not isinstance(schema.get("$id"), str):
            raise ContractDigestError(f"vendored schema {filename} must contain a string $id")
        resource = Resource.from_contents(schema)
        registry = registry.with_resource(schema["$id"], resource)
        registry = registry.with_resource(filename, resource)
        registry = registry.with_resource(
            "https://onlinechefgroep.nl/schemas/computer-acceptance/" + filename,
            resource,
        )
    return registry


class ContractDigestError(ValueError):
    """Raised when a contract artifact is missing or has drifted."""


def _read_contract(path: Path, *, expected_digest: str | None = None) -> dict[str, Any]:
    try:
        raw = path.read_bytes()
        payload = json.loads(raw)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractDigestError(f"cannot load Computer contract: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("capabilities"), list):
        raise ContractDigestError("Computer contract must contain capabilities")
    source_digest = payload.get("source_digest")
    if source_digest != GENERATED_CONTRACT_DIGEST:
        raise ContractDigestError(f"Computer contract source_digest mismatch: {source_digest}")
    if expected_digest is not None and expected_digest != source_digest:
        raise ContractDigestError(f"Computer contract does not match UDO digest: {source_digest}")
    return payload


def _generated_ids() -> tuple[str, ...]:
    payload = _read_contract(VENDORED_CONTRACT, expected_digest=GENERATED_CONTRACT_DIGEST)
    return tuple(item["capability_id"] for item in payload["capabilities"])


def _validator(schema: dict[str, Any]) -> Draft202012Validator:
    validator = Draft202012Validator(schema, registry=_SCHEMA_REGISTRY)
    validator.check_schema(schema)
    return validator


COMPUTER_CAPABILITY_IDS = _generated_ids()
_SCHEMA_REGISTRY = _load_schema_registry()


class ComputerConnector:
    """Small proxy-facing connector; transport wiring is supplied by its caller."""

    def __init__(
        self,
        manifests: tuple[CapabilityManifest, ...],
        registry: Any,
        *,
        source: ToolSource | None = None,
        profile: str = "core",
        max_risk: RiskLevel = RiskLevel.MEDIUM,
        base_url: str | None = None,
        auth_token: str | None = None,
        opener: Callable[..., Any] = urllib.request.urlopen,
    ) -> None:
        self._manifests = {item.capability_id: item for item in manifests}
        self.registry = registry
        self.source = source or computer_tool_source()
        self.profile = profile
        self.max_risk = max_risk
        self.base_url = (base_url or "").rstrip("/")
        self.auth_token = auth_token
        self._opener = opener

    def source_allowed(self, *, profile: str, max_risk: RiskLevel) -> bool:
        """Apply the source gate before a reserved ID can reach generic routing."""
        risk_order = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2}
        return (
            self.source.name == "computer"
            and self.source.transport is Transport.HTTP
            and profile in self.source.profiles
            and risk_order[self.source.risk] <= risk_order[max_risk]
        )

    @staticmethod
    def is_reserved(capability_id: str) -> bool:
        return capability_id.startswith(COMPUTER_ID_PREFIXES)

    def list_tools(self) -> list[dict[str, Any]]:
        with _LIFECYCLE_GATE:
            if not self.source_allowed(profile=self.profile, max_risk=self.max_risk):
                return []
            snapshot = self.registry.snapshot()
            active = {item.capability_id: item for item in snapshot.manifests}
            return [
                {
                    "name": item.capability_id,
                    "description": item.description,
                    "inputSchema": item.input_schema,
                }
                for item in self._manifests.values()
                if item.capability_id in active
            ]

    def call(self, capability_id: str, arguments: dict[str, Any]) -> dict[str, Any]:
        manifest = self._manifests.get(capability_id)
        if (
            not self.source_allowed(profile=self.profile, max_risk=self.max_risk)
            or manifest is None
        ):
            return make_invocation_result(
                {"protocol_version": "0.1.0-m0", "request_id": "req_" + secrets.token_hex(16)},
                status="denied",
                error_code="capability_denied",
            )
        request_id = "req_" + secrets.token_hex(16)
        try:
            with _LIFECYCLE_GATE:
                dispatch_manifest = self.registry.invocable_manifest(capability_id)
                if dispatch_manifest is None or dispatch_manifest.digest != manifest.digest:
                    raise PermissionError("capability lifecycle is not invocable")
                validate_schema(arguments.get("arguments", {}), manifest.input_schema, "input")
                request = build_invocation_request(
                    capability_id=capability_id,
                    computer_session_id=arguments["computer_session_id"],
                    machine_id=arguments["machine_id"],
                    workspace_id=arguments["workspace_id"],
                    workspace_generation=arguments["workspace_generation"],
                    arguments=arguments.get("arguments", {}),
                    deadline_at=arguments["deadline_at"],
                    idempotency_key=arguments.get("idempotency_key"),
                    request_id=request_id,
                )
                result = self._dispatch(dispatch_manifest, request)
                validate_invocation_envelope(result)
                if result["request_id"] != request["request_id"]:
                    raise ValueError("guest response request_id mismatch")
                if result["status"] == "succeeded":
                    validate_schema(result["result"], dispatch_manifest.output_schema, "output")
                return result
        except PermissionError:
            return make_invocation_result(
                {"protocol_version": "0.1.0-m0", "request_id": request_id},
                status="denied",
                error_code="capability_denied",
            )
        except (
            KeyError,
            ValueError,
            urllib.error.URLError,
            urllib.error.HTTPError,
            OSError,
        ) as exc:
            return make_invocation_result(
                {"protocol_version": "0.1.0-m0", "request_id": request_id},
                status="failed",
                error_code=f"dispatch_failed: {exc}",
            )

    def _dispatch(self, manifest: CapabilityManifest, request: dict[str, Any]) -> dict[str, Any]:
        if not self.base_url or not self.auth_token:
            raise ValueError("authenticated Computer HTTP endpoint is not configured")
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.auth_token}",
            "Content-Type": "application/json",
        }
        if manifest.idempotency_required:
            headers["Idempotency-Key"] = request["idempotency_key"]
        wire_request = dict(request)
        while True:
            req = urllib.request.Request(  # noqa: S310 - operator-configured endpoint
                self.base_url + (manifest.path or ""),
                data=json.dumps(wire_request).encode("utf-8"),
                headers=headers,
                method=manifest.method,
            )
            deadline = datetime.fromisoformat(wire_request["deadline_at"].replace("Z", "+00:00"))
            if deadline.tzinfo is None:
                raise ValueError("deadline_at must include a timezone")
            remaining = (deadline - datetime.now(UTC)).total_seconds()
            if remaining <= 0:
                raise ValueError("deadline_at has expired")
            timeout = min(manifest.timeout_seconds or remaining, remaining)
            try:
                with self._opener(req, timeout=timeout) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as error:
                try:
                    payload = json.loads(error.read().decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise error from None
            except urllib.error.URLError:
                if manifest.mutation or wire_request["attempt"] != 1:
                    raise
                wire_request["attempt"] = 2
                continue
            if not isinstance(payload, dict):
                raise ValueError("Computer response must be an object")
            return payload


def validate_schema(value: Any, schema: dict[str, Any], label: str) -> None:
    """Validate generated input/output with Draft 2020-12 and local refs."""
    errors = sorted(_validator(schema).iter_errors(value), key=lambda error: list(error.path))
    if errors:
        raise ValueError(f"{label} does not match generated schema: {errors[0].message}")


def _manifest(data: dict[str, Any]) -> CapabilityManifest:
    digest = data.get("digest") or (
        "sha256:"
        + hashlib.sha256(
            json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )
    return CapabilityManifest(
        capability_id=data["capability_id"],
        package_id="computer",
        publisher_id="udo",
        version=data.get("version", "1.0.0"),
        digest=digest,
        transport=CapabilityTransport.HTTP,
        description=data.get("description", "Computer guest capability"),
        input_schema=data["input_schema"],
        output_schema=data["output_schema"],
        required_scopes=frozenset(data["required_scopes"]),
        risk_class=RiskClass(data["risk_class"]),
        data_classification="workspace",
        profiles=frozenset({"core"}),
        lifecycle_state=LifecycleState(data.get("lifecycle_state", "active")),
        method=data["method"],
        path=data["path"],
        timeout_seconds=float(data["timeout_seconds"]),
        mutation=bool(data["mutation"]),
        idempotency_required=bool(data["idempotency_required"]),
    )


def load_computer_manifests(
    path: Path, *, expected_digest: str | None = None
) -> tuple[CapabilityManifest, ...]:
    payload = _read_contract(path, expected_digest=expected_digest)
    manifests = tuple(_manifest(item) for item in payload["capabilities"])
    if tuple(item.capability_id for item in manifests) != _generated_ids():
        raise ContractDigestError("Computer contract capability IDs do not match M0")
    return manifests


def load_computer_manifests_from_udo(
    checkout: Path, *, expected_digest: str | None = None
) -> tuple[CapabilityManifest, ...]:
    """Load the generated catalog from an explicitly supplied UDO checkout."""
    if not checkout.is_dir() or not (checkout / ".git").exists():
        raise ContractDigestError(f"invalid UDO checkout: {checkout}")
    contract = checkout / (
        "platform/agent-control-plane/packages/protocol/generated/"
        "computer-capabilities.generated.json"
    )
    if not contract.is_file():
        raise ContractDigestError(f"generated Computer contract missing: {contract}")
    if expected_digest is None:
        raise ContractDigestError("expected generated Computer digest is required")
    return load_computer_manifests(contract, expected_digest=expected_digest)


def computer_tool_source() -> ToolSource:
    """Return the single transport-only source used by the acceptance connector."""
    return ToolSource(
        name="computer",
        description="Computer guest acceptance connector",
        transport=Transport.HTTP,
        risk=RiskLevel.MEDIUM,
        profiles={"core"},
        default_enabled=False,
        mcp=McpServerConfig(),
    )


def register_computer_contract(path: Path, registry: Any) -> tuple[CapabilityManifest, ...]:
    """Load and register the digest-checked catalog, preserving SQLite lifecycle overlays."""
    from kater.capabilities.store import get_capability, upsert_capability

    manifests = load_computer_manifests(path)
    for manifest in manifests:
        upsert_capability(manifest)
        registry.register(get_capability(manifest.capability_id, manifest.version) or manifest)
    return manifests


def revoke_computer_capability(registry: Any, capability_id: str, version: str) -> None:
    """Commit the SQLite transition before publishing the in-process snapshot change."""
    from kater.capabilities.store import set_capability_lifecycle

    with _LIFECYCLE_GATE:
        set_capability_lifecycle(capability_id, version, LifecycleState.REVOKED)
        registry.revoke(capability_id, version)


def build_invocation_request(
    *,
    capability_id: str,
    computer_session_id: str,
    machine_id: str,
    workspace_id: str,
    workspace_generation: int,
    arguments: dict[str, Any],
    request_id: str | None = None,
    attempt: int = 1,
    deadline_at: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    for name, value, prefix in (
        ("computer_session_id", computer_session_id, "csess_"),
        ("machine_id", machine_id, "mach_"),
        ("workspace_id", workspace_id, "ws_"),
    ):
        if (
            not isinstance(value, str)
            or not value.startswith(prefix)
            or len(value[len(prefix) :]) != 32
            or any(char not in "0123456789abcdef" for char in value[len(prefix) :])
        ):
            raise ValueError(f"invalid {name}")
    if not isinstance(workspace_generation, int) or workspace_generation < 1:
        raise ValueError("workspace_generation must be a positive integer")
    if not isinstance(deadline_at, str) or not deadline_at:
        raise ValueError("deadline_at is required")
    if idempotency_key is not None:
        if not idempotency_key.startswith("idem_"):
            raise ValueError("invalid idempotency_key")
        if len(idempotency_key[5:]) != 32 or any(
            char not in "0123456789abcdef" for char in idempotency_key[5:]
        ):
            raise ValueError("invalid idempotency_key")
    if not isinstance(attempt, int) or attempt < 1:
        raise ValueError("attempt must be a positive integer")
    request = {
        "protocol_version": "0.1.0-m0",
        "request_id": request_id or "req_" + secrets.token_hex(16),
        "computer_session_id": computer_session_id,
        "machine_id": machine_id,
        "workspace_id": workspace_id,
        "workspace_generation": workspace_generation,
        "capability_id": capability_id,
        "attempt": attempt,
        "deadline_at": deadline_at,
        "arguments": arguments,
    }
    if idempotency_key is not None:
        request["idempotency_key"] = idempotency_key
    return request


def make_invocation_result(
    request: dict[str, Any],
    *,
    status: str,
    result: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    envelope: dict[str, Any] = {
        "protocol_version": request["protocol_version"],
        "status": status,
        "request_id": request["request_id"],
    }
    if status == "succeeded":
        envelope["result"] = result or {}
        envelope["artifacts"] = []
    else:
        envelope["error"] = {
            "code": error_code or "internal_error",
            "message": error_code or "failed",
            "retryable": False,
            "details": {},
        }
    return envelope


def validate_invocation_envelope(value: dict[str, Any]) -> None:
    """Validate the guest's already-canonical invocation result."""
    validate_schema(value, _guest_invocation_result_schema(), "invocation result")


def _guest_invocation_result_schema() -> dict[str, Any]:
    return json.loads(
        (_SCHEMA_DIR / "guest-invocation-result.schema.json").read_text(encoding="utf-8")
    )
