"""Restore ordering tests with opaque DB bytes and a fake migrator; no SQL runs."""
from __future__ import annotations

import hashlib
import io
import json
import tarfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from kater import backup, migrations


def _state_bytes(state: Path) -> dict[str, bytes]:
    return {str(p.relative_to(state)): p.read_bytes() for p in state.rglob("*") if p.is_file()}


def _bundle(path: Path, files: dict[str, bytes]) -> None:
    manifest = {
        "bundle_version": 1,
        "schema_version": 1,
        "files": [
            {"name": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
            for name, data in files.items()
        ],
    }
    with tarfile.open(path, "w:gz") as archive:
        for name, data in {"manifest.json": json.dumps(manifest).encode(), **files}.items():
            info = tarfile.TarInfo(name)
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))


@pytest.fixture
def restore_case(tmp_path, monkeypatch):
    root = tmp_path / "project"
    state = root / ".kater"
    state.mkdir(parents=True)
    original = {"kater.db": b"original-database", "settings.json": b"{}", "marker": b"keep"}
    for name, data in original.items():
        (state / name).write_bytes(data)
    bundle = tmp_path / "restore.tar.gz"
    _bundle(bundle, {"kater.db": b"candidate-database", "settings.json": b'{"version": 2}'})

    def safety_copy(path, *, project_dir):
        assert project_dir == root
        assert _state_bytes(state) == original
        path.write_bytes(b"safety-backup-fixture")

    safety = Mock(side_effect=safety_copy)
    monkeypatch.setattr(backup, "create_backup", safety)
    monkeypatch.setattr(
        migrations, "run_migrations", Mock(side_effect=AssertionError("real migration forbidden"))
    )
    monkeypatch.setattr(
        backup.sqlite3, "connect", Mock(side_effect=AssertionError("database access forbidden"))
    )
    return root, state, original, bundle, safety


def test_rejected_staging_leaves_existing_state_unchanged(restore_case, monkeypatch):
    root, state, original, bundle, safety = restore_case
    migrator = Mock(side_effect=migrations.MigrationError("fixture rejection"))
    monkeypatch.setattr(migrations, "run_migrations", migrator)

    with pytest.raises(backup.BackupError) as error:
        backup.restore_backup(bundle, project_dir=root, force=True)

    assert _state_bytes(state) == original
    safety.assert_not_called()
    assert "failed migration before install" in str(error.value)
    staged_db = migrator.call_args.args[0]
    assert staged_db != state / backup.DB_NAME
    assert staged_db.parent.parent.parent == root
    assert not staged_db.parent.parent.exists()


def test_malformed_staging_database_is_reported_without_replacing_state(
    restore_case, monkeypatch
):
    root, state, original, bundle, safety = restore_case
    migrator = Mock(side_effect=backup.sqlite3.DatabaseError("file is not a database"))
    monkeypatch.setattr(migrations, "run_migrations", migrator)

    with pytest.raises(backup.BackupError, match="failed migration before install") as error:
        backup.restore_backup(bundle, project_dir=root, force=True)

    assert "file is not a database" in str(error.value)
    assert _state_bytes(state) == original
    safety.assert_not_called()
    staged_db = migrator.call_args.args[0]
    assert staged_db != state / backup.DB_NAME
    assert not staged_db.parent.parent.exists()


def test_success_installs_the_validated_staging_copy(restore_case, monkeypatch):
    root, state, original, bundle, safety = restore_case

    def migrate_staging(path):
        assert path.parent.name == "state"
        assert path.parent.parent.parent == root
        assert path != state / backup.DB_NAME
        assert _state_bytes(state) == original
        safety.assert_not_called()
        path.write_bytes(b"validated-candidate")
        return [
            SimpleNamespace(version=2, status="applied"),
            SimpleNamespace(version=1, status="skipped"),
        ]

    migrator = Mock(side_effect=migrate_staging)
    monkeypatch.setattr(migrations, "run_migrations", migrator)
    result = backup.restore_backup(bundle, project_dir=root, force=True)
    migrator.assert_called_once()
    safety.assert_called_once()
    assert (state / backup.DB_NAME).read_bytes() == b"validated-candidate"
    assert not (state / "marker").exists()
    assert result.migrations_applied == (2,)
    assert result.safety_backup is not None
    assert result.safety_backup.read_bytes() == b"safety-backup-fixture"
    assert list(root.glob(".kater-restore-*")) == []


def test_rejected_staging_does_not_create_new_state(restore_case, monkeypatch):
    root, _state, _original, bundle, safety = restore_case
    empty_root = root / "empty-install"
    monkeypatch.setattr(
        migrations,
        "run_migrations",
        Mock(side_effect=migrations.MigrationError("fixture rejection")),
    )
    with pytest.raises(backup.BackupError, match="failed migration before install"):
        backup.restore_backup(bundle, project_dir=empty_root)
    assert not (empty_root / ".kater").exists()
    assert list(empty_root.glob(".kater-restore-*")) == []
    safety.assert_not_called()


def test_bundle_without_db_does_not_invoke_migrator(restore_case):
    root, state, _original, bundle, _safety = restore_case
    _bundle(bundle, {"config.json": b'{"version": 1}'})
    result = backup.restore_backup(bundle, project_dir=root, force=True)
    migrations.run_migrations.assert_not_called()
    assert result.migrations_applied == ()
    assert not (state / backup.DB_NAME).exists()


def test_safety_backup_failure_after_validation_keeps_original(restore_case, monkeypatch):
    root, state, original, bundle, safety = restore_case
    migrator = Mock(return_value=[])
    monkeypatch.setattr(migrations, "run_migrations", migrator)
    safety.side_effect = backup.BackupError("fixture safety failure")
    with pytest.raises(backup.BackupError, match="safety backup failed"):
        backup.restore_backup(bundle, project_dir=root, force=True)
    migrator.assert_called_once()
    assert _state_bytes(state) == original
    assert list(root.glob(".kater-restore-*")) == []
