from __future__ import annotations

import importlib.util
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "kater-with-chefvault.py"
UNIT = ROOT / "scripts" / "systemd" / "kater-system.service.example"


def _load_bootstrap():
    spec = importlib.util.spec_from_file_location("kater_with_chefvault", SCRIPT)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_run_checked_does_not_copy_child_output_into_error(monkeypatch) -> None:
    bootstrap = _load_bootstrap()
    completed = subprocess.CompletedProcess(
        args=["chefvault-profile"],
        returncode=17,
        stdout="provider-secret-from-stdout",
        stderr="provider-secret-from-stderr",
    )
    monkeypatch.setattr(bootstrap.subprocess, "run", lambda *args, **kwargs: completed)

    with pytest.raises(SystemExit) as error:
        bootstrap._run_checked(["chefvault-profile"], env={}, label="materialization")

    message = str(error.value)
    assert message == "materialization failed with exit code 17"
    assert "provider-secret" not in message


def test_materialized_profile_is_removed_before_return(tmp_path, monkeypatch) -> None:
    bootstrap = _load_bootstrap()
    runtime_dir = tmp_path / "runtime"
    captured: dict[str, Path] = {}

    def fake_run(command, *, env, label) -> None:
        output = Path(command[command.index("--output") + 1])
        captured["output"] = output
        captured["temp_dir"] = output.parent
        output.write_text('API_KEY="resolved-secret"\nOPTIONAL_KEY=null\n', encoding="utf-8")

    monkeypatch.setattr(bootstrap, "_run_checked", fake_run)

    result = bootstrap._materialize_secrets(
        env={},
        profile_command="chefvault-profile",
        runtime_dir=runtime_dir,
    )

    assert result == {"API_KEY": "resolved-secret"}
    assert stat.S_IMODE(runtime_dir.stat().st_mode) == 0o700
    assert not captured["output"].exists()
    assert not captured["temp_dir"].exists()
    assert list(runtime_dir.iterdir()) == []


def test_materialized_profile_is_removed_when_validation_fails(tmp_path, monkeypatch) -> None:
    bootstrap = _load_bootstrap()
    runtime_dir = tmp_path / "runtime"

    def fake_run(command, *, env, label) -> None:
        output = Path(command[command.index("--output") + 1])
        output.write_text('PATH="/tmp/untrusted"\n', encoding="utf-8")

    monkeypatch.setattr(bootstrap, "_run_checked", fake_run)

    with pytest.raises(SystemExit, match="process-control variable"):
        bootstrap._materialize_secrets(
            env={},
            profile_command="chefvault-profile",
            runtime_dir=runtime_dir,
        )

    assert list(runtime_dir.iterdir()) == []


def test_kater_executable_is_resolved_beside_python(tmp_path, monkeypatch) -> None:
    bootstrap = _load_bootstrap()
    bin_dir = tmp_path / ".venv" / "bin"
    bin_dir.mkdir(parents=True)
    python = bin_dir / "python"
    kater = bin_dir / "kater"
    python.touch()
    kater.touch()
    monkeypatch.setattr(sys, "executable", str(python))

    assert bootstrap._kater_executable() == str(kater)


def test_system_unit_keeps_state_outside_immutable_release() -> None:
    text = UNIT.read_text(encoding="utf-8")

    assert "WorkingDirectory=/var/lib/kater" in text
    assert "ReadWritePaths=/var/lib/kater /var/cache/kater /run/kater" in text
    assert "ReadWritePaths=" in text
    assert "/opt/kater/current/.kater" not in text
    assert "CHEF_VAULT_RUNTIME_DIR=/run/kater/chefvault" in text
