from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated, Any

import typer

from kater.capabilities.discovery import discover
from kater.capabilities.models import (
    CapabilityManifest,
    CapabilityTransport,
    DiscoveryContext,
    LifecycleState,
    RiskClass,
)
from kater.capabilities.registry import get_default_registry, reset_default_registry
from kater.capabilities.store import (
    capability_overview,
    get_capability,
    list_capabilities,
    set_capability_lifecycle,
    upsert_capability,
)

app = typer.Typer(help="Manage capability manifests, lifecycle state and task-scoped discovery.")


def _print(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _csv_set(raw: str) -> frozenset[str]:
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def _manifest_payload(manifest: CapabilityManifest) -> dict[str, Any]:
    return {
        "capability_id": manifest.capability_id,
        "package_id": manifest.package_id,
        "publisher_id": manifest.publisher_id,
        "version": manifest.version,
        "digest": manifest.digest,
        "transport": manifest.transport.value,
        "description": manifest.description,
        "input_schema": manifest.input_schema,
        "output_schema": manifest.output_schema,
        "required_scopes": sorted(manifest.required_scopes),
        "risk_class": manifest.risk_class.value,
        "data_classification": manifest.data_classification,
        "profiles": sorted(manifest.profiles),
        "healthcheck_capability_id": manifest.healthcheck_capability_id,
        "lifecycle_state": manifest.lifecycle_state.value,
        "rollback_version": manifest.rollback_version,
        "network_targets": list(manifest.network_targets),
        "tags": sorted(manifest.tags),
    }


def _manifest_from_mapping(data: dict[str, Any]) -> CapabilityManifest:
    def _as_set(key: str) -> frozenset[str]:
        value = data.get(key, [])
        if isinstance(value, str):
            return _csv_set(value)
        if value is None:
            return frozenset()
        return frozenset(str(item) for item in value)

    def _as_tuple(key: str) -> tuple[str, ...]:
        value = data.get(key, [])
        if isinstance(value, str):
            return tuple(item.strip() for item in value.split(",") if item.strip())
        if value is None:
            return ()
        return tuple(str(item) for item in value)

    transport = data.get("transport", CapabilityTransport.NATIVE.value)
    risk = data.get("risk_class", RiskClass.READ.value)
    lifecycle = data.get("lifecycle_state", LifecycleState.ACTIVE.value)
    input_schema = data.get("input_schema") or {}
    output_schema = data.get("output_schema") or {}
    if not isinstance(input_schema, dict) or not isinstance(output_schema, dict):
        raise typer.BadParameter("input_schema and output_schema must be objects")
    return CapabilityManifest(
        capability_id=str(data["capability_id"]),
        package_id=str(data["package_id"]),
        publisher_id=str(data["publisher_id"]),
        version=str(data["version"]),
        digest=str(data.get("digest") or ""),
        transport=CapabilityTransport(transport),
        description=str(data.get("description") or ""),
        input_schema=input_schema,
        output_schema=output_schema,
        required_scopes=_as_set("required_scopes"),
        risk_class=RiskClass(risk),
        data_classification=str(data.get("data_classification") or "internal"),
        profiles=_as_set("profiles") or frozenset({"core"}),
        healthcheck_capability_id=(
            str(data["healthcheck_capability_id"])
            if data.get("healthcheck_capability_id")
            else None
        ),
        lifecycle_state=LifecycleState(lifecycle),
        rollback_version=(str(data["rollback_version"]) if data.get("rollback_version") else None),
        network_targets=_as_tuple("network_targets"),
        tags=_as_set("tags"),
    )


def _persist_and_register(manifest: CapabilityManifest) -> None:
    upsert_capability(manifest)
    registry = get_default_registry()
    try:
        registry.register(manifest)
    except ValueError:
        # Same id@version already present with a different digest — force refresh.
        reset_default_registry()
        get_default_registry().register(manifest)
    else:
        # Keep lifecycle in sync when re-registering an existing digest.
        try:
            registry.set_lifecycle(
                manifest.capability_id, manifest.version, manifest.lifecycle_state
            )
        except KeyError:
            pass


@app.command("register")
def register_capability(
    file: Annotated[
        Path | None,
        typer.Option("--file", help="Path to a CapabilityManifest JSON document"),
    ] = None,
    capability_id: Annotated[str | None, typer.Option("--capability-id")] = None,
    package_id: Annotated[str | None, typer.Option("--package-id")] = None,
    publisher_id: Annotated[str | None, typer.Option("--publisher-id")] = None,
    version: Annotated[str | None, typer.Option("--version")] = None,
    digest: Annotated[str, typer.Option("--digest")] = "",
    transport: Annotated[
        CapabilityTransport, typer.Option("--transport")
    ] = CapabilityTransport.NATIVE,
    description: Annotated[str, typer.Option("--description")] = "",
    scopes: Annotated[str, typer.Option("--scopes")] = "",
    risk_class: Annotated[RiskClass, typer.Option("--risk-class")] = RiskClass.READ,
    data_classification: Annotated[str, typer.Option("--data-classification")] = "internal",
    profiles: Annotated[str, typer.Option("--profiles")] = "core",
    tags: Annotated[str, typer.Option("--tags")] = "",
    lifecycle_state: Annotated[LifecycleState, typer.Option("--lifecycle")] = LifecycleState.ACTIVE,
    healthcheck_capability_id: Annotated[str | None, typer.Option("--healthcheck")] = None,
    rollback_version: Annotated[str | None, typer.Option("--rollback-version")] = None,
    network_targets: Annotated[str, typer.Option("--network-targets")] = "",
) -> None:
    """Register a capability from a JSON file or minimal inline flags."""
    if file is not None:
        try:
            payload = json.loads(file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise typer.BadParameter(f"cannot read manifest file: {exc}") from exc
        if not isinstance(payload, dict):
            raise typer.BadParameter("manifest file must contain a JSON object")
        try:
            manifest = _manifest_from_mapping(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise typer.BadParameter(f"invalid manifest: {exc}") from exc
    else:
        missing = [
            name
            for name, value in (
                ("--capability-id", capability_id),
                ("--package-id", package_id),
                ("--publisher-id", publisher_id),
                ("--version", version),
            )
            if not value
        ]
        if missing:
            raise typer.BadParameter("provide --file or required flags: " + ", ".join(missing))
        try:
            manifest = CapabilityManifest(
                capability_id=capability_id or "",
                package_id=package_id or "",
                publisher_id=publisher_id or "",
                version=version or "",
                digest=digest,
                transport=transport,
                description=description,
                input_schema={},
                output_schema={},
                required_scopes=_csv_set(scopes),
                risk_class=risk_class,
                data_classification=data_classification,
                profiles=_csv_set(profiles) or frozenset({"core"}),
                healthcheck_capability_id=healthcheck_capability_id,
                lifecycle_state=lifecycle_state,
                rollback_version=rollback_version,
                network_targets=tuple(
                    item.strip() for item in network_targets.split(",") if item.strip()
                ),
                tags=_csv_set(tags),
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

    _persist_and_register(manifest)
    _print({"saved": True, **_manifest_payload(manifest)})


@app.command("list")
def list_cmd(
    as_json: Annotated[bool, typer.Option("--json")] = False,
    include_all: Annotated[
        bool, typer.Option("--all", help="Include non-active lifecycle states")
    ] = False,
) -> None:
    """List persisted capabilities (active/canary by default)."""
    _ = as_json  # output is always structured JSON (matches kater-routes style)
    manifests = list_capabilities(include_non_active=include_all)
    _print(
        {
            "total": len(manifests),
            "capabilities": [_manifest_payload(item) for item in manifests],
        }
    )


@app.command("get")
def get_cmd(
    capability_id: str,
    version: Annotated[str | None, typer.Option("--version")] = None,
) -> None:
    """Fetch one capability from the store (latest preferred when version omitted)."""
    manifest = get_capability(capability_id, version)
    if manifest is None:
        _print({"found": False, "capability_id": capability_id, "version": version})
        raise typer.Exit(code=1)
    _print({"found": True, **_manifest_payload(manifest)})


@app.command("set-lifecycle")
def set_lifecycle_cmd(
    capability_id: str,
    version: str,
    state: LifecycleState,
) -> None:
    """Update lifecycle in the store and the default in-memory registry."""
    try:
        manifest = set_capability_lifecycle(capability_id, version, state)
    except KeyError as exc:
        _print({"updated": False, "error": str(exc)})
        raise typer.Exit(code=1) from exc
    registry = get_default_registry()
    try:
        registry.set_lifecycle(capability_id, version, state)
    except KeyError:
        # Not present in-memory yet; store remains authoritative.
        pass
    _print({"updated": True, **_manifest_payload(manifest)})


@app.command("discover")
def discover_cmd(
    profile: Annotated[str, typer.Option("--profile")] = "core",
    intent: Annotated[str, typer.Option("--intent")] = "",
    max_risk: Annotated[RiskClass, typer.Option("--max-risk")] = RiskClass.EXTERNAL_WRITE,
    tags: Annotated[str, typer.Option("--tags")] = "",
    as_json: Annotated[bool, typer.Option("--json")] = False,
) -> None:
    """Compile the minimal discoverable capability set for a context."""
    context = DiscoveryContext(
        profile_ids=_csv_set(profile) or frozenset({"core"}),
        task_intent=intent,
        max_risk=max_risk,
        tags_any=_csv_set(tags),
    )
    _ = as_json  # output is always structured JSON
    results = discover(context)
    _print(
        {
            "context": {
                "profile_ids": sorted(context.profile_ids),
                "task_intent": context.task_intent,
                "max_risk": context.max_risk.value,
                "tags_any": sorted(context.tags_any),
            },
            "total": len(results),
            "capabilities": [
                {
                    "capability_id": item.capability_id,
                    "version": item.version,
                    "digest": item.digest,
                    "description": item.description,
                    "risk_class": item.risk_class.value,
                    "lifecycle_state": item.lifecycle_state.value,
                    "required_scopes": sorted(item.required_scopes),
                    "input_schema": item.input_schema,
                    "approval_expected": item.approval_expected,
                    "health_ok": item.health_ok,
                }
                for item in results
            ],
        }
    )


@app.command("overview")
def overview_cmd() -> None:
    """Show persisted capability counts by lifecycle state."""
    _print(capability_overview())


if __name__ == "__main__":
    app()
