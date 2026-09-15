"""Strict runtime identity: malformed or missing fields are null, never guessed."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from kater.build_identity import (
    IDENTITY_FIELDS,
    cli_version_payload,
    format_identity_log,
    load_build_identity,
    validate_identity_field,
    write_stamp,
)

ROOT = Path(__file__).resolve().parent.parent
STAMP_SCRIPT = ROOT / "scripts" / "stamp-build-identity.py"
NULL_IDENTITY = {field: None for field in IDENTITY_FIELDS}
VALID_SHA = "0123456789abcdef0123456789abcdef01234567"
VALID_DIGEST = "a" * 64


def _clear_env(monkeypatch) -> None:
    for name in (
        "KATER_BUILD_VERSION",
        "KATER_BUILD_SHA",
        "KATER_BUILD_RELEASE",
        "KATER_BUILD_ARTIFACT_DIGEST",
    ):
        monkeypatch.delenv(name, raising=False)


def test_missing_sources_are_null(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    assert load_build_identity(stamp=tmp_path / "missing.json") == NULL_IDENTITY


def test_malformed_sha_and_version_are_null(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    stamp = tmp_path / "_build_identity.json"
    stamp.write_text(
        json.dumps(
            {
                "version": "not-a-version",
                "source_sha": "DEADBEEF",
                "release": "1.1.1",
                "artifact_digest": "nope",
            }
        ),
        encoding="utf-8",
    )
    assert load_build_identity(stamp=stamp) == NULL_IDENTITY


def test_unknown_tokens_are_null() -> None:
    assert validate_identity_field("version", "unknown") is None
    assert validate_identity_field("source_sha", "NONE") is None
    assert validate_identity_field("release", "null") is None


def test_valid_stamp_is_accepted(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    stamp = tmp_path / "_build_identity.json"
    written = write_stamp(
        stamp,
        version="1.1.1",
        source_sha=VALID_SHA,
        release="v1.1.1",
        artifact_digest=VALID_DIGEST,
    )
    assert written == {
        "version": "1.1.1",
        "source_sha": VALID_SHA,
        "release": "v1.1.1",
        "artifact_digest": f"sha256:{VALID_DIGEST}",
    }
    assert load_build_identity(stamp=stamp) == written


def test_env_overrides_file_and_malformed_env_does_not_fall_back(
    monkeypatch, tmp_path: Path
) -> None:
    stamp = tmp_path / "_build_identity.json"
    write_stamp(
        stamp,
        version="1.1.1",
        source_sha=VALID_SHA,
        release="v1.1.1",
        artifact_digest=VALID_DIGEST,
    )
    monkeypatch.setenv("KATER_BUILD_VERSION", "2.0.0")
    monkeypatch.setenv("KATER_BUILD_SHA", "not-a-sha")
    monkeypatch.delenv("KATER_BUILD_RELEASE", raising=False)
    monkeypatch.delenv("KATER_BUILD_ARTIFACT_DIGEST", raising=False)
    identity = load_build_identity(stamp=stamp)
    assert identity["version"] == "2.0.0"
    assert identity["source_sha"] is None
    assert identity["release"] == "v1.1.1"
    assert identity["artifact_digest"] == f"sha256:{VALID_DIGEST}"


def test_malformed_json_is_null(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    stamp = tmp_path / "_build_identity.json"
    stamp.write_text("{not-json", encoding="utf-8")
    assert load_build_identity(stamp=stamp) == NULL_IDENTITY


def test_cli_payload_includes_package_version(monkeypatch, tmp_path: Path) -> None:
    _clear_env(monkeypatch)
    monkeypatch.setattr("kater.build_identity.stamp_path", lambda: tmp_path / "missing.json")
    payload = cli_version_payload()
    assert payload["package_version"]
    assert set(payload) == {"package_version", *IDENTITY_FIELDS}
    for field in IDENTITY_FIELDS:
        assert payload[field] is None


def test_identity_log_uses_null_token() -> None:
    line = format_identity_log(NULL_IDENTITY)
    assert line == (
        "version=null source_sha=null release=null artifact_digest=null"
    )


def test_stamp_script_writes_validated_file(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "kater"\nversion = "1.1.1"\n',
        encoding="utf-8",
    )
    (tmp_path / "src" / "kater").mkdir(parents=True)
    result = subprocess.run(
        [
            sys.executable,
            str(STAMP_SCRIPT),
            "--root",
            str(tmp_path),
            "--no-git",
            "--version",
            "1.1.1",
            "--sha",
            VALID_SHA,
            "--release",
            "v1.1.1",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    stamped = json.loads((tmp_path / "src" / "kater" / "_build_identity.json").read_text())
    assert stamped["version"] == "1.1.1"
    assert stamped["source_sha"] == VALID_SHA
    assert stamped["release"] == "v1.1.1"
    assert stamped["artifact_digest"] is None
