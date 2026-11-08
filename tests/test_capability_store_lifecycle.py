from __future__ import annotations

from dataclasses import replace

from kater.capabilities.builtins import BUILTIN_CAPABILITIES
from kater.capabilities.models import LifecycleState
from kater.capabilities.store import (
    clear_capability_state,
    get_capability,
    set_capability_lifecycle,
    upsert_capability,
)


def test_manifest_refresh_preserves_persisted_revocation(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    manifest = replace(
        BUILTIN_CAPABILITIES[0],
        capability_id="filesystem.read",
        package_id="computer",
        lifecycle_state=LifecycleState.ACTIVE,
    )
    upsert_capability(manifest)
    set_capability_lifecycle(manifest.capability_id, manifest.version, LifecycleState.REVOKED)

    upsert_capability(manifest)

    persisted = get_capability(manifest.capability_id, manifest.version)
    assert persisted is not None
    assert persisted.lifecycle_state is LifecycleState.REVOKED
    clear_capability_state()


def test_register_file_preserves_http_fields(tmp_path, monkeypatch) -> None:
    import json

    from typer.testing import CliRunner

    from kater.capabilities.cli import app

    monkeypatch.chdir(tmp_path)
    document = {
        "capability_id": "domain.search.hybrid",
        "package_id": "domain",
        "publisher_id": "overlay",
        "version": "1.2.3",
        "transport": "http",
        "method": "POST",
        "path": "/search",
        "timeout_seconds": 4.5,
        "mutation": True,
        "idempotency_required": True,
    }
    manifest_file = tmp_path / "manifest.json"
    manifest_file.write_text(json.dumps(document))

    result = CliRunner().invoke(app, ["register", "--file", str(manifest_file)])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    for key in ("method", "path", "timeout_seconds", "mutation", "idempotency_required"):
        assert payload[key] == document[key], key
    persisted = get_capability("domain.search.hybrid", "1.2.3")
    assert persisted is not None
    assert persisted.method == "POST"
    assert persisted.path == "/search"
    assert persisted.timeout_seconds == 4.5
    assert persisted.mutation is True
    assert persisted.idempotency_required is True
    clear_capability_state()
