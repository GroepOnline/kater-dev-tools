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
import stat
import subprocess
import sys
import tempfile
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
        # The child may include broker responses or provider values in its output.
        # Keep startup diagnostics useful without copying credential data to journald.
        raise SystemExit(f"{label} failed with exit code {completed.returncode}")


def _prepare_runtime_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
        raise SystemExit(f"ChefVault runtime path is not a private directory: {path}")
    path.chmod(0o700)


def _materialize_secrets(
    *, env: dict[str, str], profile_command: str, runtime_dir: Path
) -> dict[str, str]:
    """Resolve credentials through a short-lived file under the runtime directory."""
    _prepare_runtime_dir(runtime_dir)
    previous_umask = os.umask(0o077)
    try:
        with tempfile.TemporaryDirectory(prefix=".bootstrap-", dir=runtime_dir) as temp_dir:
            output = Path(temp_dir) / "profile.env"
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
            _secure_materialized_file(output)
            return _read_materialized(output)
    finally:
        os.umask(previous_umask)


def _kater_executable() -> str:
    """Resolve Kater beside the trusted Python interpreter running this wrapper."""
    executable = Path(sys.executable).with_name("kater")
    if not executable.is_file():
        raise SystemExit(f"kater executable not found beside Python: {executable}")
    return str(executable)


def main() -> None:
    # Resolve the executable before broker-supplied values enter the environment.
    # This also lets systemd use /var/lib/kater as cwd while code stays in /opt.
    kater_bin = _kater_executable()
    root = Path.cwd()

    env = os.environ.copy()
    env["CHEF_VAULT_BROKER_TOKEN"] = _broker_token()
    env.setdefault("CHEF_VAULT_BROKER_URL", "http://127.0.0.1:8322")
    env.setdefault("CHEF_VAULT_RUNTIME_DIR", str(root / ".kater" / "runtime" / "chefvault"))

    runtime_dir = Path(env["CHEF_VAULT_RUNTIME_DIR"]).expanduser()
    profile_command = env.get("CHEF_VAULT_PROFILE_COMMAND", "chefvault-profile")
    env.update(
        _materialize_secrets(
            env=env,
            profile_command=profile_command,
            runtime_dir=runtime_dir,
        )
    )
    env["KATER_EXTENSIONS_MODULE"] = "kater.chefvault_extension"
    profiles = {part.strip() for part in env.get("KATER_PROFILE", "ops").split(",") if part.strip()}
    profiles.add("chef-vault")
    env["KATER_PROFILE"] = ",".join(sorted(profiles))

    # High-risk backends are disabled by default. Persist an explicit enable for
    # this private source so the wrapper is a complete bootstrap, not a partial hint.
    _run_checked(
        [kater_bin, "enable", "chefvault"],
        env=env,
        label="Kater ChefVault backend enable",
    )

    args = sys.argv[1:] or ["up"]
    os.execve(kater_bin, [kater_bin, *args], env)


if __name__ == "__main__":
    main()
