"""Deployed runtime identity. Missing or malformed fields are null, never guessed.

Values come from a build/deploy stamp (``_build_identity.json`` next to this
package) or from ``KATER_BUILD_*`` environment variables. This module never
reads ``git`` — a checkout SHA is not the deployed identity.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

ENV_VERSION = "KATER_BUILD_VERSION"
ENV_SHA = "KATER_BUILD_SHA"
ENV_RELEASE = "KATER_BUILD_RELEASE"
ENV_DIGEST = "KATER_BUILD_ARTIFACT_DIGEST"

STAMP_NAME = "_build_identity.json"
IDENTITY_FIELDS = ("version", "source_sha", "release", "artifact_digest")

_VERSION_RE = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:\.dev[0-9]+)?$")
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_RELEASE_RE = re.compile(
    r"^v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:\.dev[0-9]+)?$"
)
_DIGEST_RE = re.compile(r"^(?:sha256:)?[0-9a-f]{64}$")
_REJECT_TOKENS = frozenset({"", "unknown", "none", "null"})

_ENV_FOR_FIELD = {
    "version": ENV_VERSION,
    "source_sha": ENV_SHA,
    "release": ENV_RELEASE,
    "artifact_digest": ENV_DIGEST,
}


def stamp_path() -> Path:
    return Path(__file__).resolve().parent / STAMP_NAME


def empty_identity() -> dict[str, str | None]:
    return {field: None for field in IDENTITY_FIELDS}


def validate_identity_field(name: str, raw: object) -> str | None:
    """Return a strict value or null. Never substitutes a default."""
    if raw is None or not isinstance(raw, str):
        return None
    value = raw.strip()
    if value.lower() in _REJECT_TOKENS:
        return None
    if name == "version":
        return value if _VERSION_RE.fullmatch(value) else None
    if name == "source_sha":
        return value if _SHA_RE.fullmatch(value) else None
    if name == "release":
        return value if _RELEASE_RE.fullmatch(value) else None
    if name == "artifact_digest":
        if not _DIGEST_RE.fullmatch(value):
            return None
        return value if value.startswith("sha256:") else f"sha256:{value}"
    return None


def _read_stamp_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def load_build_identity(*, stamp: Path | None = None) -> dict[str, str | None]:
    file_data = _read_stamp_file(stamp if stamp is not None else stamp_path())
    identity = empty_identity()
    for field, env_name in _ENV_FOR_FIELD.items():
        if env_name in os.environ and os.environ[env_name].strip() != "":
            identity[field] = validate_identity_field(field, os.environ[env_name])
        else:
            identity[field] = validate_identity_field(field, file_data.get(field))
    return identity


def write_stamp(
    path: Path,
    *,
    version: object = None,
    source_sha: object = None,
    release: object = None,
    artifact_digest: object = None,
) -> dict[str, str | None]:
    identity = {
        "version": validate_identity_field("version", version),
        "source_sha": validate_identity_field("source_sha", source_sha),
        "release": validate_identity_field("release", release),
        "artifact_digest": validate_identity_field("artifact_digest", artifact_digest),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(identity, indent=2) + "\n", encoding="utf-8")
    return identity


def format_identity_log(identity: dict[str, str | None] | None = None) -> str:
    payload = identity if identity is not None else load_build_identity()
    return " ".join(
        f"{field}={payload[field] if payload[field] is not None else 'null'}"
        for field in IDENTITY_FIELDS
    )


def cli_version_payload() -> dict[str, str | None]:
    from kater import __version__

    payload = load_build_identity()
    return {"package_version": __version__, **payload}
