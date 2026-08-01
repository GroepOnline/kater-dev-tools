#!/usr/bin/env python3
"""Materialize the Kater secret profile and start the gateway.

Only the per-consumer broker token is bootstrapped locally. All provider keys are
resolved from Vaultwarden through ChefVault and passed to the child process without
shell evaluation.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path

_ENV_LINE = re.compile(r"^([A-Z_][A-Z0-9_]*)=(.*)$")

# Materialized ChefVault values are credential data, never process controls. Any
# key the child's shell/loader/interpreter would act on (PATH lookup, dynamic
# linker, Python import path, shell startup hooks) must never be sourced from the
# broker: injecting them would let a compromised or misconfigured profile
# redirect execution instead of only supplying secrets.
_DENIED_ENV_NAMES = frozenset(
    {
        "PATH",
        "PYTHONPATH",
        "PYTHONHOME",
        "PYTHONSTARTUP",
        "IFS",
        "ENV",
        "BASH_ENV",
        "SHELLOPTS",
        "GLOBIGNORE",
    }
)
_DENIED_ENV_PREFIXES = ("LD_", "DYLD_")


def _is_denied_env_name(name: str) -> bool:
    return name in _DENIED_ENV_NAMES or name.startswith(_DENIED_ENV_PREFIXES)


def _broker_token() -> str:
    direct = os.environ.get("CHEF_VAULT_BROKER_TOKEN", "").strip()
    if direct:
        return direct
    path = Path(
        os.environ.get(
            "CHEF_VAULT_BROKER_TOKEN_FILE",
            "~/.config/chefgroep/kater-broker-token",
        )
    ).expanduser()
    if not path.is_file():
        raise SystemExit(
            "ChefVault broker token missing: set CHEF_VAULT_BROKER_TOKEN or create "
            f"{path} with mode 0600"
        )
    if stat.S_IMODE(path.lstat().st_mode) & 0o077:
        raise SystemExit(
            f"ChefVault broker token file {path} is group/other-accessible; "
            "restrict it to mode 0600"
        )
    token = path.read_text(encoding="utf-8").strip()
    if not token:
        raise SystemExit(f"ChefVault broker token file is empty: {path}")
    return token


def _read_materialized(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        match = _ENV_LINE.match(line)
        if not match:
            continue
        key, raw = match.groups()
        if _is_denied_env_name(key):
            # Broker profiles carry credentials only. A runtime/execution-control
            # variable here is either a misconfiguration or an attempt to steer
            # the child process, so fail closed rather than inject it.
            raise SystemExit(
                f"ChefVault returned process-control variable {key!r}; refusing to "
                "inject it into the Kater environment"
            )
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise SystemExit(f"invalid ChefVault env value for {key}: {error}") from error
        if not isinstance(value, str):
            # Optional provider keys that ChefVault could not resolve are
            # reported as non-string values (e.g. JSON null). Per the runbook
            # these must not block startup, so skip them instead of failing.
            continue
        result[key] = value
    return result


def _secure_materialized_file(output: Path) -> None:
    """Verify the credential file is a private, regular file before reading it.

    Rejects symlinks and non-regular files (symlink/hardlink swap attacks) and
    enforces the documented mode 0600 regardless of the materializer's umask.
    """
    info = output.lstat()
    if stat.S_ISLNK(info.st_mode):
        raise SystemExit(f"refusing to read symlinked ChefVault env file: {output}")
    if not stat.S_ISREG(info.st_mode):
        raise SystemExit(f"ChefVault env file is not a regular file: {output}")
    output.chmod(0o600)


def _run_checked(command: list[str], *, env: dict[str, str], label: str) -> None:
    completed = subprocess.run(
        command,
        env=env,
        check=False,
        text=True,
        capture_output=True,
    )
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "unknown error"
        raise SystemExit(f"{label} failed: {detail}")


def main() -> None:
    # Resolve uv against the trusted process PATH now, before any broker-supplied
    # values are in play, so the child cannot redirect which uv binary runs.
    uv_bin = shutil.which("uv")
    if uv_bin is None:
        raise SystemExit("uv executable not found on PATH")

    root = Path.cwd()
    output = root / ".kater" / ".env.chefvault"
    output.parent.mkdir(parents=True, exist_ok=True)
    # The state dir holds materialized credentials; keep it owner-only.
    output.parent.chmod(0o700)

    env = os.environ.copy()
    env["CHEF_VAULT_BROKER_TOKEN"] = _broker_token()
    env.setdefault("CHEF_VAULT_BROKER_URL", "http://127.0.0.1:8322")
    env.setdefault("CHEF_VAULT_RUNTIME_DIR", str(root / ".kater" / "runtime" / "chefvault"))

    profile_command = env.get("CHEF_VAULT_PROFILE_COMMAND", "chefvault-profile")
    # Materialize under a restrictive umask so the file is created private even
    # before the explicit chmod below closes any residual window.
    previous_umask = os.umask(0o077)
    try:
        _run_checked(
            [
                profile_command,
                "--json",
                "materialize",
                "kater-dev-tools/ops",
                "--output",
                str(output),
            ],
            env=env,
            label="ChefVault profile materialization",
        )
    finally:
        os.umask(previous_umask)
    # Verify and lock down the credential file before it is read or handed off.
    _secure_materialized_file(output)

    env.update(_read_materialized(output))
    env["KATER_EXTENSIONS_MODULE"] = "kater.chefvault_extension"
    profiles = {
        part.strip()
        for part in env.get("KATER_PROFILE", "ops").split(",")
        if part.strip()
    }
    profiles.add("chef-vault")
    env["KATER_PROFILE"] = ",".join(sorted(profiles))

    # High-risk backends are disabled by default. Persist an explicit enable for
    # this private source so the wrapper is a complete bootstrap, not a partial hint.
    _run_checked(
        [uv_bin, "run", "kater", "enable", "chefvault"],
        env=env,
        label="Kater ChefVault backend enable",
    )

    args = sys.argv[1:] or ["up"]
    os.execve(uv_bin, [uv_bin, "run", "kater", *args], env)


if __name__ == "__main__":
    main()
