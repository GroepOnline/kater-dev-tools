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
