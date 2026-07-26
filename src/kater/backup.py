"""Backup and restore of the complete Kater state directory.

Kater keeps everything an install needs in ``.kater/``: the SQLite database
(telemetry, gate audit, routing state, capability registry), ``settings.json``,
the OAuth client/token store, and the ``.env`` holding backend credentials.
Moving an install between machines used to mean copying four files by hand and
hoping the WAL journal was checkpointed. This module bundles them into one
verifiable ``.tar.gz`` and restores them safely.

Two details matter:

* The database is copied with the **SQLite backup API**, not with the
  filesystem. A plain copy of a WAL database races the writer and can produce
  a torn file; ``Connection.backup`` produces a consistent snapshot even while
  ``kater serve`` is running.
* Restore treats the bundle as untrusted input. Every tar member is validated
  before a byte is written (no absolute paths, no ``..``, no links or device
  nodes, nothing outside the manifest), extracted to a temp directory and only
  then moved into place.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sqlite3
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import IO, Any

from kater import __version__ as kater_version
from kater import migrations
from kater.settings import KaterSettings, invalidate_settings_cache, load_settings
from kater.storage import reset_db_cache

_log = logging.getLogger("kater.backup")

BUNDLE_VERSION = 1

MANIFEST_NAME = "manifest.json"
DB_NAME = "kater.db"
SETTINGS_NAME = "settings.json"
CONFIG_NAME = "config.json"
OAUTH_NAME = "oauth.json"
ENV_NAME = ".env"

#: Bundled in manifest order. ``config.json`` is `kater init` scaffolding: not
#: secret, but carrying it keeps a moved install from needing a re-init.
BUNDLED_MEMBERS = (DB_NAME, SETTINGS_NAME, CONFIG_NAME, OAUTH_NAME, ENV_NAME)
#: Members a bundle may legitimately contain, beyond the manifest itself.
ALLOWED_MEMBERS = frozenset(BUNDLED_MEMBERS)
#: Restored files that must not be world- or group-readable.
SECRET_MEMBERS = frozenset({SETTINGS_NAME, OAUTH_NAME, ENV_NAME, DB_NAME})

_DIR_MODE = 0o700
_SECRET_MODE = 0o600
_READ_CHUNK = 1 << 20

#: Caps on untrusted archive members during inspect/extract. A single member
#: larger than 256 MiB, or more than 512 MiB of payload in total, is refused
#: before the restore swap so a hostile bundle cannot fill the disk.
MAX_MEMBER_BYTES = 256 * 1024 * 1024
MAX_TOTAL_BYTES = 512 * 1024 * 1024


class BackupError(RuntimeError):
    """Raised for any unusable bundle, destination or source state."""


@dataclass(frozen=True)
class BackupResult:
    path: Path
    bytes: int
    files: tuple[str, ...]
    schema_version: int
    include_secrets: bool


@dataclass(frozen=True)
class RestoreResult:
    restored_files: tuple[str, ...]
    schema_version: int
    safety_backup: Path | None
    migrations_applied: tuple[int, ...]


# ── Paths ──────────────────────────────────────────────────────────


def _root(project_dir: Path | None) -> Path:
    return (project_dir or Path.cwd()).resolve()


def state_dir(project_dir: Path | None = None) -> Path:
    return _root(project_dir) / ".kater"


def default_backup_dir(project_dir: Path | None = None) -> Path:
    return state_dir(project_dir) / "backups"


def _db_source(project_dir: Path | None) -> Path:
    root = _root(project_dir)
    configured = Path(load_settings(project_dir).db_path).expanduser()
    return configured if configured.is_absolute() else root / configured


def _digest_stream(
    reader: IO[bytes],
    sink: IO[bytes] | None = None,
    *,
    max_member_bytes: int | None = None,
    total_so_far: int = 0,
    max_total_bytes: int | None = None,
) -> tuple[str, int]:
    """Hash a stream in bounded chunks, optionally teeing it to ``sink``.

    When ``max_member_bytes`` / ``max_total_bytes`` are set, raise
    :class:`BackupError` as soon as the stream would exceed either cap.
    ``total_so_far`` is the byte count already accepted from earlier members.
    """
    digest = hashlib.sha256()
    size = 0
    while chunk := reader.read(_READ_CHUNK):
        digest.update(chunk)
        size += len(chunk)
        if max_member_bytes is not None and size > max_member_bytes:
            raise BackupError(
                f"archive member exceeds size cap of {max_member_bytes} bytes"
            )
        if max_total_bytes is not None and total_so_far + size > max_total_bytes:
            raise BackupError(
                f"archive payload exceeds total size cap of {max_total_bytes} bytes"
            )
        if sink is not None:
            sink.write(chunk)
    return digest.hexdigest(), size


def _sha256(path: Path) -> str:
    with path.open("rb") as handle:
        return _digest_stream(handle)[0]


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


# ── Backup ─────────────────────────────────────────────────────────


def _snapshot_db(source: Path, target: Path) -> int:
    """Copy the database through the SQLite backup API; returns schema version."""
    try:
        src = sqlite3.connect(f"file:{source}?mode=ro", uri=True, timeout=10.0)
    except sqlite3.Error as exc:
        raise BackupError(f"cannot open database {source}: {exc}") from exc
    try:
        dst = sqlite3.connect(target)
        try:
            src.backup(dst)
            dst.commit()
        finally:
            dst.close()
    except sqlite3.Error as exc:
        raise BackupError(f"sqlite backup of {source} failed: {exc}") from exc
    finally:
        src.close()
    snapshot = sqlite3.connect(target)
    try:
        return int(migrations.schema_status(snapshot)["current_version"])
    finally:
        snapshot.close()


def _stage_settings(source: Path, target: Path, *, include_secrets: bool) -> None:
    if include_secrets:
        shutil.copy2(source, target)
        return
    try:
        raw = json.loads(source.read_text(encoding="utf-8"))
        safe = KaterSettings.from_dict(raw).to_safe_dict()
    except (OSError, ValueError) as exc:
        raise BackupError(f"cannot read settings for masking: {exc}") from exc
    target.write_text(json.dumps(safe, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def create_backup(
    dest: Path | None = None,
    *,
    project_dir: Path | None = None,
    include_secrets: bool = True,
) -> BackupResult:
    """Bundle all Kater state into a ``.tar.gz`` and return where it landed."""
    kater_dir = state_dir(project_dir)
    db_path = _db_source(project_dir)
    if not kater_dir.is_dir() and not db_path.exists():
        raise BackupError(f"no Kater state to back up: {kater_dir} does not exist")

    if dest is None:
        dest = default_backup_dir(project_dir) / f"kater-backup-{_timestamp()}.tar.gz"
    dest = Path(dest)
    if dest.is_dir():
        dest = dest / f"kater-backup-{_timestamp()}.tar.gz"
    dest.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="kater-backup-") as tmp:
        staging = Path(tmp)
        schema_version = 0
        if db_path.exists():
            schema_version = _snapshot_db(db_path, staging / DB_NAME)

        settings_file = kater_dir / SETTINGS_NAME
        if settings_file.is_file():
            _stage_settings(settings_file, staging / SETTINGS_NAME, include_secrets=include_secrets)
        copied = [CONFIG_NAME, OAUTH_NAME, ENV_NAME] if include_secrets else [CONFIG_NAME]
        for name in copied:
            candidate = kater_dir / name
            if candidate.is_file():
                shutil.copy2(candidate, staging / name)

        staged = [staging / name for name in BUNDLED_MEMBERS if (staging / name).is_file()]
        # Describe the archive by what it actually contains: derive this flag
        # from the staged credential files rather than the request parameter so
        # no secret-named value is written into the clear-text manifest, and so
        # the manifest stays an honest description of the bundle's contents.
        manifest: dict[str, Any] = {
            "bundle_version": BUNDLE_VERSION,
            "kater_version": kater_version,
            "created_at": datetime.now(UTC).isoformat(),
            "schema_version": schema_version,
            "include_secrets": any(p.name in (OAUTH_NAME, ENV_NAME) for p in staged),
            "files": [
                {"name": p.name, "sha256": _sha256(p), "bytes": p.stat().st_size} for p in staged
            ],
        }
        (staging / MANIFEST_NAME).write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

        try:
            with tarfile.open(dest, "w:gz") as archive:
                for member in [staging / MANIFEST_NAME, *staged]:
                    info = archive.gettarinfo(str(member), arcname=member.name)
                    info.uid = info.gid = 0
                    info.uname = info.gname = ""
                    info.mode = _SECRET_MODE
                    with member.open("rb") as handle:
                        archive.addfile(info, handle)
        except OSError as exc:
            raise BackupError(f"cannot write backup to {dest}: {exc}") from exc

    dest.chmod(_SECRET_MODE)
    if dest.parent.is_dir() and dest.parent.name == "backups":
        dest.parent.chmod(_DIR_MODE)
    files = tuple(str(entry["name"]) for entry in manifest["files"])
    _log.info("wrote backup %s (%d files)", dest, len(files))
    return BackupResult(
        path=dest,
        bytes=dest.stat().st_size,
        files=files,
        schema_version=schema_version,
        include_secrets=include_secrets,
    )


# ── Inspection ─────────────────────────────────────────────────────


def _safe_member_name(name: str) -> bool:
    """Reject anything that could escape the extraction directory."""
    if not name or name in {".", ".."}:
        return False
    if "\\" in name or "/" in name:
        return False
    if PurePosixPath(name).is_absolute():
        return False
    return name in ALLOWED_MEMBERS or name == MANIFEST_NAME


def _read_manifest(archive: tarfile.TarFile) -> dict[str, Any]:
    try:
        member = archive.getmember(MANIFEST_NAME)
    except KeyError as exc:
        raise BackupError(f"bundle has no {MANIFEST_NAME}; it is not a Kater backup") from exc
    if not member.isfile():
        raise BackupError(f"{MANIFEST_NAME} is not a regular file")
    try:
        data = json.loads(_open_member(archive, member).read().decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BackupError(f"{MANIFEST_NAME} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise BackupError(f"{MANIFEST_NAME} must contain a JSON object")
    version = data.get("bundle_version")
    if not isinstance(version, int) or version > BUNDLE_VERSION:
        raise BackupError(
            f"unsupported bundle_version {version!r}; this Kater reads up to {BUNDLE_VERSION}"
        )
    entries = data.get("files")
    if not isinstance(entries, list):
        raise BackupError(f"{MANIFEST_NAME} is missing a files list")
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str):
            raise BackupError(f"{MANIFEST_NAME} has a malformed files entry: {entry!r}")
        if not _safe_member_name(entry["name"]) or entry["name"] == MANIFEST_NAME:
            raise BackupError(f"manifest declares an unsafe file name: {entry['name']!r}")
    return data


def _open_member(archive: tarfile.TarFile, member: tarfile.TarInfo) -> IO[bytes]:
    handle = archive.extractfile(member)
    if handle is None:
        raise BackupError(f"cannot read {member.name} from bundle")
    return handle


def inspect_backup(path: Path) -> dict[str, Any]:
    """Validate a bundle's manifest and per-member checksums without extracting."""
    path = Path(path)
    if not path.is_file():
        raise BackupError(f"backup not found: {path}")
    try:
        archive = tarfile.open(path, "r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise BackupError(f"cannot open backup {path}: {exc}") from exc
    with archive:
        manifest = _read_manifest(archive)
        declared = {str(entry["name"]): entry for entry in manifest["files"]}
        present: dict[str, tarfile.TarInfo] = {}
        unexpected: list[str] = []
        for member in archive.getmembers():
            if member.name == MANIFEST_NAME:
                continue
            if not member.isfile() or not _safe_member_name(member.name):
                unexpected.append(member.name)
                continue
            if member.name in present or member.name not in declared:
                unexpected.append(member.name)
                continue
            present[member.name] = member
        mismatches: list[str] = []
        total_bytes = 0
        for name, member in present.items():
            checksum, size = _digest_stream(
                _open_member(archive, member),
                max_member_bytes=MAX_MEMBER_BYTES,
                total_so_far=total_bytes,
                max_total_bytes=MAX_TOTAL_BYTES,
            )
            total_bytes += size
            entry = declared[name]
            if checksum != entry.get("sha256") or size != entry.get("bytes"):
                mismatches.append(name)
        missing = sorted(set(declared) - set(present))
    return {
        "path": str(path),
        "bundle_version": manifest["bundle_version"],
        "kater_version": manifest.get("kater_version", "unknown"),
        "created_at": manifest.get("created_at", ""),
        "schema_version": int(manifest.get("schema_version", 0) or 0),
        "include_secrets": bool(manifest.get("include_secrets", True)),
        "files": [dict(entry) for entry in manifest["files"]],
        "missing": missing,
        "unexpected": sorted(unexpected),
        "mismatches": sorted(mismatches),
        "ok": not (missing or unexpected or mismatches),
    }


# ── Restore ────────────────────────────────────────────────────────


def _extract_verified(
    archive: tarfile.TarFile,
    manifest: dict[str, Any],
    target: Path,
    *,
    max_member_bytes: int = MAX_MEMBER_BYTES,
    max_total_bytes: int = MAX_TOTAL_BYTES,
) -> list[str]:
    """Write every manifest member into ``target`` after re-checking its digest."""
    declared = {str(entry["name"]): entry for entry in manifest["files"]}
    seen: set[str] = set()
    total_bytes = 0
    for member in archive.getmembers():
        if member.name == MANIFEST_NAME:
            continue
        if not _safe_member_name(member.name):
            raise BackupError(f"refusing unsafe archive member: {member.name!r}")
        if member.issym() or member.islnk() or member.isdev() or member.isfifo():
            raise BackupError(f"refusing non-regular archive member: {member.name!r}")
        if not member.isfile():
            raise BackupError(f"refusing non-file archive member: {member.name!r}")
        if member.name not in declared:
            raise BackupError(f"archive member is not listed in the manifest: {member.name!r}")
        if member.name in seen:
            raise BackupError(f"archive contains duplicate member: {member.name!r}")
        seen.add(member.name)

        out = target / member.name
        with out.open("wb") as sink:
            checksum, size = _digest_stream(
                _open_member(archive, member),
                sink,
                max_member_bytes=max_member_bytes,
                total_so_far=total_bytes,
                max_total_bytes=max_total_bytes,
            )
        total_bytes += size
        entry = declared[member.name]
        if checksum != entry.get("sha256") or size != entry.get("bytes"):
            raise BackupError(f"checksum mismatch for {member.name!r}; bundle is corrupt")
        out.chmod(_SECRET_MODE)
    missing = sorted(set(declared) - seen)
    if missing:
        raise BackupError(f"bundle is missing files declared in its manifest: {missing}")
    return sorted(seen)


def _rollback_restore(kater_dir: Path, retired: Path) -> None:
    """Best-effort: put ``retired`` back as ``.kater`` after a failed mid-swap.

    Unlike the previous empty-dir-only path, this always clears a partial
    ``.kater`` (if present) and renames ``retired`` into place so a failure
    after the first ``os.replace`` does not leave the install half-restored.
    """
    if not retired.exists():
        return
    try:
        if kater_dir.exists():
            shutil.rmtree(kater_dir)
        os.replace(retired, kater_dir)
    except OSError as exc:
        _log.warning("restore rollback from retired failed: %s", exc)


def _has_state(kater_dir: Path) -> bool:
    return kater_dir.is_dir() and any(kater_dir.iterdir())


def restore_backup(
    path: Path,
    *,
    project_dir: Path | None = None,
    force: bool = False,
) -> RestoreResult:
    """Replace the local ``.kater/`` state with the contents of a bundle."""
    path = Path(path)
    kater_dir = state_dir(project_dir)
    if _has_state(kater_dir) and not force:
        raise BackupError(
            f"{kater_dir} already exists; pass force=True to replace it "
            "(a safety backup of the current state is taken first)"
        )

    try:
        archive = tarfile.open(path, "r:gz")
    except (tarfile.TarError, OSError) as exc:
        raise BackupError(f"cannot open backup {path}: {exc}") from exc

    kater_dir.parent.mkdir(parents=True, exist_ok=True)
    # Stage inside the project root so every move below is a same-filesystem
    # rename: a cross-device os.replace would fail halfway through the swap.
    workdir = Path(tempfile.mkdtemp(prefix=".kater-restore-", dir=kater_dir.parent))
    try:
        staging = workdir / "state"
        staging.mkdir(mode=_DIR_MODE)
        with archive:
            manifest = _read_manifest(archive)
            restored = _extract_verified(archive, manifest, staging)

        safety_source: Path | None = None
        if _has_state(kater_dir):
            safety_source = workdir / f"kater-safety-{_timestamp()}.tar.gz"
            try:
                create_backup(safety_source, project_dir=project_dir)
            except BackupError as exc:
                raise BackupError(
                    f"refusing to overwrite {kater_dir}: safety backup failed ({exc})"
                ) from exc

        retired = workdir / "retired"
        if kater_dir.exists():
            os.replace(kater_dir, retired)
        try:
            kater_dir.mkdir(parents=True, exist_ok=True)
            kater_dir.chmod(_DIR_MODE)
            for name in restored:
                os.replace(staging / name, kater_dir / name)
                if name in SECRET_MEMBERS:
                    (kater_dir / name).chmod(_SECRET_MODE)
        except OSError as exc:
            _rollback_restore(kater_dir, retired)
            raise BackupError(
                f"restore into {kater_dir} failed and was rolled back: {exc}"
            ) from exc

        safety_backup: Path | None = None
        if safety_source is not None:
            backups = default_backup_dir(project_dir)
            backups.mkdir(parents=True, exist_ok=True)
            backups.chmod(_DIR_MODE)
            safety_backup = backups / safety_source.name
            shutil.move(str(safety_source), str(safety_backup))
            safety_backup.chmod(_SECRET_MODE)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    # Drop caches pinned to the settings/database files we just replaced.
    invalidate_settings_cache()
    reset_db_cache()

    applied: tuple[int, ...] = ()
    if DB_NAME in restored:
        results = migrations.run_migrations(kater_dir / DB_NAME)
        applied = tuple(r.version for r in results if r.status == "applied")

    _log.info("restored %d files into %s", len(restored), kater_dir)
    return RestoreResult(
        restored_files=tuple(restored),
        schema_version=int(manifest.get("schema_version", 0) or 0),
        safety_backup=safety_backup,
        migrations_applied=applied,
    )
