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
import subprocess
import sys
from pathlib import Path

_ENV_LINE = re.compile(r"^([A-Z_][A-Z0-9_]*)=(.*)$")


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
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as error:
            raise SystemExit(f"invalid ChefVault env value for {key}: {error}") from error
        if not isinstance(value, str):
            raise SystemExit(f"invalid ChefVault env value for {key}")
        result[key] = value
    return result


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
    root = Path.cwd()
    output = root / ".kater" / ".env.chefvault"
    output.parent.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["CHEF_VAULT_BROKER_TOKEN"] = _broker_token()
    env.setdefault("CHEF_VAULT_BROKER_URL", "http://127.0.0.1:8322")
    env.setdefault("CHEF_VAULT_RUNTIME_DIR", str(root / ".kater" / "runtime" / "chefvault"))

    profile_command = env.get("CHEF_VAULT_PROFILE_COMMAND", "chefvault-profile")
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
        ["uv", "run", "kater", "enable", "chefvault"],
        env=env,
        label="Kater ChefVault backend enable",
    )

    args = sys.argv[1:] or ["up"]
    os.execvpe("uv", ["uv", "run", "kater", *args], env)


if __name__ == "__main__":
    main()
