from __future__ import annotations

import hashlib
import io
import json
import os
import shutil
import sqlite3
import stat
import sys
import tarfile
from pathlib import Path

import pytest

from kater import backup, migrations
from kater.backup import BackupError
from kater.settings import AuthConfig, KaterSettings, ServerOverride, save_settings

API_KEY = "kat_topsecret"
BACKEND_TOKEN = "ghp_backendsecret"


def _seed_project(root: Path, *, migrate: bool = True) -> None:
    """
    Create a representative `.kater` state directory under `root`, including settings, credentials, configuration, and an events database.
    
    Parameters:
        root (Path): Project root in which to create the `.kater` directory.
        migrate (bool): Whether to initialize the database with the latest schema migrations.
    """
    kater = root / ".kater"
    kater.mkdir(parents=True, exist_ok=True)
    settings = KaterSettings(auth=AuthConfig(mode="apikey", api_keys=[API_KEY]))
    settings.server_overrides["github"] = ServerOverride(
        enabled=True, env={"GITHUB_TOKEN": BACKEND_TOKEN}
    )
    save_settings(settings, root)
    (kater / "oauth.json").write_text(
        json.dumps({"clients": {"kater-dashboard": {"client_secret": "shh"}}}),
        encoding="utf-8",
    )
    (kater / ".env").write_text(f"GITHUB_TOKEN={BACKEND_TOKEN}\n", encoding="utf-8")
    (kater / "config.json").write_text(
        json.dumps({"version": 1, "default_profile": "ops"}), encoding="utf-8"
    )

    db = kater / "kater.db"
    if migrate:
        migrations.run_migrations(db)
    conn = sqlite3.connect(db)
    try:
        if not migrate:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS events (
                       id INTEGER PRIMARY KEY AUTOINCREMENT,
                       type TEXT NOT NULL,
                       name TEXT NOT NULL,
                       timestamp REAL NOT NULL,
                       duration_ms REAL DEFAULT 0,
                       success INTEGER DEFAULT 1,
                       profile TEXT,
                       metadata TEXT
                   )"""
            )
        conn.execute(
            "INSERT INTO events (type, name, timestamp, metadata) VALUES (?, ?, ?, ?)",
            ("tool_call", "github__search", 1234.5, "{}"),
        )
        conn.commit()
    finally:
        conn.close()


def _events(root: Path) -> list[tuple[str, str]]:
    """Retrieve event types and names from the project's Kater database.
    
    Parameters:
    	root (Path): Project root containing the `.kater/kater.db` database.
    
    Returns:
    	list[tuple[str, str]]: Event type and name pairs."""
    conn = sqlite3.connect(root / ".kater" / "kater.db")
    try:
        return [tuple(row) for row in conn.execute("SELECT type, name FROM events")]
    finally:
        conn.close()


def _member_bytes(path: Path, name: str) -> bytes:
    """
    Read the contents of a named file from a gzip-compressed tar archive.
    
    Parameters:
    	path (Path): Path to the tar archive.
    	name (str): Name of the archive member to read.
    
    Returns:
    	bytes: Contents of the specified archive member.
    """
    with tarfile.open(path, "r:gz") as tar:
        handle = tar.extractfile(name)
        assert handle is not None
        return handle.read()


def _rewrite_tar(source: Path, dest: Path, *, mutate: dict[str, bytes]) -> None:
    """
    Rewrite a gzip-compressed tar archive, optionally replacing selected member contents.
    
    Parameters:
    	source (Path): Path to the source archive.
    	dest (Path): Path where the rewritten archive is created.
    	mutate (dict[str, bytes]): Mapping of member names to replacement contents.
    """
    with tarfile.open(source, "r:gz") as src, tarfile.open(dest, "w:gz") as out:
        for member in src.getmembers():
            handle = src.extractfile(member)
            assert handle is not None
            data = mutate.get(member.name, handle.read())
            member.size = len(data)
            out.addfile(member, io.BytesIO(data))


def _write_tar(
    path: Path,
    entries: list[tuple[str, bytes]],
    *,
    symlinks: tuple[tuple[str, str], ...] = (),
) -> None:
    """
    Create a gzip-compressed tar archive containing regular files and optional symbolic links.
    
    Parameters:
    	path (Path): Destination archive path.
    	entries (list[tuple[str, bytes]]): File names and contents to add.
    	symlinks (tuple[tuple[str, str], ...]): Link names and their targets to add.
    """
    with tarfile.open(path, "w:gz") as tar:
        for name, data in entries:
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        for name, target in symlinks:
            info = tarfile.TarInfo(name)
            info.type = tarfile.SYMTYPE
            info.linkname = target
            tar.addfile(info)


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    _seed_project(root)
    return root


def test_backup_restore_round_trip(project, tmp_path) -> None:
    bundle = tmp_path / "bundle.tar.gz"
    result = backup.create_backup(bundle, project_dir=project)

    assert result.path == bundle
    assert result.bytes > 0
    assert set(result.files) == {
        "kater.db",
        "settings.json",
        "config.json",
        "oauth.json",
        ".env",
    }
    assert result.schema_version == migrations.latest_version()

    shutil.rmtree(project / ".kater")
    restored = backup.restore_backup(bundle, project_dir=project)

    assert set(restored.restored_files) == set(result.files)
    assert restored.safety_backup is None
    assert restored.migrations_applied == ()
    assert _events(project) == [("tool_call", "github__search")]
    settings = json.loads((project / ".kater" / "settings.json").read_text(encoding="utf-8"))
    assert settings["auth"]["api_keys"] == [API_KEY]
    assert settings["server_overrides"]["github"]["env"] == {"GITHUB_TOKEN": BACKEND_TOKEN}
    assert (project / ".kater" / "oauth.json").is_file()
    assert (project / ".kater" / ".env").read_text(encoding="utf-8").strip().endswith(BACKEND_TOKEN)


def test_default_destination_lands_in_the_backups_directory(project) -> None:
    result = backup.create_backup(project_dir=project)

    assert result.path.parent == project / ".kater" / "backups"
    assert result.path.name.startswith("kater-backup-")
    assert result.path.name.endswith(".tar.gz")
    assert result.path.is_file()


def test_include_secrets_false_omits_and_masks(project, tmp_path) -> None:
    bundle = tmp_path / "safe.tar.gz"
    result = backup.create_backup(bundle, project_dir=project, include_secrets=False)

    assert set(result.files) == {"kater.db", "settings.json", "config.json"}
    assert result.include_secrets is False
    with tarfile.open(bundle, "r:gz") as tar:
        names = set(tar.getnames())
    assert ".env" not in names
    assert "oauth.json" not in names

    settings = json.loads(_member_bytes(bundle, "settings.json").decode("utf-8"))
    assert settings["auth"]["api_keys"] == 1
    assert settings["server_overrides"]["github"]["env"] == {"GITHUB_TOKEN": "***"}
    assert BACKEND_TOKEN not in _member_bytes(bundle, "settings.json").decode("utf-8")

    assert backup.inspect_backup(bundle)["include_secrets"] is False


def test_inspect_backup_reports_manifest_and_detects_corruption(project, tmp_path) -> None:
    bundle = tmp_path / "bundle.tar.gz"
    backup.create_backup(bundle, project_dir=project)

    report = backup.inspect_backup(bundle)
    assert report["ok"] is True
    assert report["bundle_version"] == backup.BUNDLE_VERSION
    assert report["schema_version"] == migrations.latest_version()
    assert {entry["name"] for entry in report["files"]} == {
        "kater.db",
        "settings.json",
        "config.json",
        "oauth.json",
        ".env",
    }
    assert report["missing"] == []
    assert report["mismatches"] == []

    corrupt = tmp_path / "corrupt.tar.gz"
    _rewrite_tar(bundle, corrupt, mutate={"settings.json": b'{"version": 2}\n'})

    corrupt_report = backup.inspect_backup(corrupt)
    assert corrupt_report["ok"] is False
    assert corrupt_report["mismatches"] == ["settings.json"]

    with pytest.raises(BackupError, match="checksum mismatch"):
        backup.restore_backup(corrupt, project_dir=tmp_path / "empty")


def test_inspect_rejects_a_bundle_without_a_manifest(tmp_path) -> None:
    bogus = tmp_path / "bogus.tar.gz"
    _write_tar(bogus, [("settings.json", b"{}")])

    with pytest.raises(BackupError, match="not a Kater backup"):
        backup.inspect_backup(bogus)


def test_restore_requires_force_and_writes_a_safety_backup(project, tmp_path) -> None:
    bundle = tmp_path / "bundle.tar.gz"
    backup.create_backup(bundle, project_dir=project)

    (project / ".kater" / "marker.txt").write_text("local state", encoding="utf-8")

    with pytest.raises(BackupError, match="force=True"):
        backup.restore_backup(bundle, project_dir=project)
    assert (project / ".kater" / "marker.txt").is_file()

    result = backup.restore_backup(bundle, project_dir=project, force=True)

    assert result.safety_backup is not None
    assert result.safety_backup.is_file()
    assert result.safety_backup.parent == project / ".kater" / "backups"
    # The bundle did not contain marker.txt, so the force restore replaced state.
    assert not (project / ".kater" / "marker.txt").exists()
    safety = backup.inspect_backup(result.safety_backup)
    assert safety["ok"] is True


def test_restore_rejects_path_traversal_and_link_members(tmp_path) -> None:
    root = tmp_path / "target"
    root.mkdir()
    payload = b'{"version": 2}\n'
    manifest = {
        "bundle_version": 1,
        "kater_version": "1.0.0",
        "created_at": "2026-01-01T00:00:00+00:00",
        "schema_version": 1,
        "include_secrets": True,
        "files": [
            {
                "name": "settings.json",
                "sha256": hashlib.sha256(payload).hexdigest(),
                "bytes": len(payload),
            }
        ],
    }
    manifest_bytes = json.dumps(manifest).encode("utf-8")

    traversal = tmp_path / "traversal.tar.gz"
    _write_tar(
        traversal,
        [
            ("manifest.json", manifest_bytes),
            ("settings.json", payload),
            ("../../evil", b"pwned"),
        ],
    )
    with pytest.raises(BackupError, match="unsafe archive member"):
        backup.restore_backup(traversal, project_dir=root)

    linked = tmp_path / "linked.tar.gz"
    _write_tar(
        linked,
        [("manifest.json", manifest_bytes), ("settings.json", payload)],
        symlinks=(("oauth.json", "/etc/passwd"),),
    )
    with pytest.raises(BackupError, match="non-regular archive member"):
        backup.restore_backup(linked, project_dir=root)

    declared_evil = tmp_path / "declared.tar.gz"
    evil_manifest = dict(manifest)
    evil_manifest["files"] = [{"name": "../../evil", "sha256": "0" * 64, "bytes": 0}]
    _write_tar(
        declared_evil,
        [("manifest.json", json.dumps(evil_manifest).encode("utf-8"))],
    )
    with pytest.raises(BackupError, match="unsafe file name"):
        backup.restore_backup(declared_evil, project_dir=root)

    assert not (tmp_path / "evil").exists()
    assert not (tmp_path.parent / "evil").exists()
    assert not (root / ".kater").exists()
    assert list(root.iterdir()) == []


def test_restore_migrates_a_bundle_from_an_older_schema(tmp_path) -> None:
    root = tmp_path / "legacy"
    root.mkdir()
    _seed_project(root, migrate=False)

    bundle = tmp_path / "legacy.tar.gz"
    result = backup.create_backup(bundle, project_dir=root)
    assert result.schema_version == 0

    shutil.rmtree(root / ".kater")
    restored = backup.restore_backup(bundle, project_dir=root)

    assert restored.schema_version == 0
    assert restored.migrations_applied == tuple(m.version for m in migrations.MIGRATIONS)
    status = migrations.schema_status(root / ".kater" / "kater.db")
    assert status["current_version"] == migrations.latest_version()
    assert status["pending"] == []
    assert _events(root) == [("tool_call", "github__search")]


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_restore_sets_tight_permissions(project, tmp_path) -> None:
    bundle = tmp_path / "bundle.tar.gz"
    backup.create_backup(bundle, project_dir=project)
    shutil.rmtree(project / ".kater")

    backup.restore_backup(bundle, project_dir=project)

    kater = project / ".kater"
    assert stat.S_IMODE(kater.stat().st_mode) == 0o700
    for name in ("settings.json", "oauth.json", ".env", "kater.db"):
        assert stat.S_IMODE((kater / name).stat().st_mode) == 0o600


def test_create_backup_without_state_is_an_error(tmp_path) -> None:
    empty = tmp_path / "nothing"
    empty.mkdir()

    with pytest.raises(BackupError, match="no Kater state"):
        backup.create_backup(project_dir=empty)


def _minimal_bundle(path: Path, members: dict[str, bytes]) -> None:
    """
    Create a minimal backup archive containing a manifest and the specified members.
    
    Parameters:
    	path (Path): Destination path for the gzip-compressed tar archive.
    	members (dict[str, bytes]): Archive member names mapped to their contents.
    """
    files = [
        {
            "name": name,
            "sha256": hashlib.sha256(data).hexdigest(),
            "bytes": len(data),
        }
        for name, data in members.items()
    ]
    manifest = {
        "bundle_version": 1,
        "kater_version": "1.0.0",
        "created_at": "2026-01-01T00:00:00+00:00",
        "schema_version": 1,
        "include_secrets": True,
        "files": files,
    }
    entries = [("manifest.json", json.dumps(manifest).encode("utf-8"))]
    entries.extend(members.items())
    _write_tar(path, entries)


def test_digest_stream_enforces_member_and_total_caps() -> None:
    payload = b"x" * 20
    with pytest.raises(BackupError, match="member exceeds size cap"):
        backup._digest_stream(io.BytesIO(payload), max_member_bytes=10)

    sink = io.BytesIO()
    with pytest.raises(BackupError, match="total size cap"):
        backup._digest_stream(
            io.BytesIO(payload),
            sink,
            max_member_bytes=100,
            total_so_far=15,
            max_total_bytes=30,
        )


def test_extract_enforces_custom_size_caps(tmp_path) -> None:
    bundle = tmp_path / "capped.tar.gz"
    _minimal_bundle(
        bundle,
        {
            "settings.json": b'{"version": 1}\n',
            "config.json": b'{"version": 1}\n',
        },
    )
    staging = tmp_path / "staging"
    staging.mkdir()

    with tarfile.open(bundle, "r:gz") as archive:
        manifest = backup._read_manifest(archive)
        with pytest.raises(BackupError, match="member exceeds size cap"):
            backup._extract_verified(
                archive,
                manifest,
                staging,
                max_member_bytes=5,
                max_total_bytes=10_000,
            )

    staging2 = tmp_path / "staging2"
    staging2.mkdir()
    with tarfile.open(bundle, "r:gz") as archive:
        manifest = backup._read_manifest(archive)
        with pytest.raises(BackupError, match="total size cap"):
            backup._extract_verified(
                archive,
                manifest,
                staging2,
                max_member_bytes=10_000,
                max_total_bytes=20,
            )


def test_read_manifest_rejects_oversized_manifest(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(backup, "MAX_MANIFEST_BYTES", 64)
    bundle = tmp_path / "huge_manifest.tar.gz"
    oversized = json.dumps({"bundle_version": 1, "files": [], "pad": "x" * 512}).encode("utf-8")
    _write_tar(bundle, [("manifest.json", oversized)])
    with pytest.raises(BackupError, match="manifest cap"):
        backup.inspect_backup(bundle)


def test_restore_rolls_back_from_retired_when_partial(project, tmp_path, monkeypatch) -> None:
    bundle = tmp_path / "bundle.tar.gz"
    backup.create_backup(bundle, project_dir=project)
    marker = project / ".kater" / "marker.txt"
    marker.write_text("local-only", encoding="utf-8")
    before_settings = (project / ".kater" / "settings.json").read_text(encoding="utf-8")

    real_replace = os.replace
    member_swaps = {"count": 0}

    def flaky_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        dst_path = Path(dst)
        if dst_path.parent.name == ".kater" and dst_path.name in backup.ALLOWED_MEMBERS:
            member_swaps["count"] += 1
            if member_swaps["count"] >= 2:
                raise OSError("simulated mid-swap failure")
        real_replace(src, dst)

    monkeypatch.setattr(backup.os, "replace", flaky_replace)

    with pytest.raises(BackupError, match="rolled back"):
        backup.restore_backup(bundle, project_dir=project, force=True)

    assert marker.is_file()
    assert marker.read_text(encoding="utf-8") == "local-only"
    assert (project / ".kater" / "settings.json").read_text(encoding="utf-8") == before_settings
    assert member_swaps["count"] >= 2
