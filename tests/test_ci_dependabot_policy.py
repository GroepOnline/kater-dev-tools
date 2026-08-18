from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/ci.yml"
DEPENDABOT_SKIP = "if: github.event_name == 'pull_request' && github.actor == 'dependabot[bot]'"
TRUSTED_RUN_GUARD = (
    "if: github.event.repository.fork != true && "
    "(github.event_name != 'pull_request' || github.actor != 'dependabot[bot]')"
)


def _job_block(job: str, next_job: str) -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    return text.split(f"  {job}:\n", 1)[1].split(f"\n  {next_job}:\n", 1)[0]


def test_dependabot_gets_auditable_private_lane_skip() -> None:
    block = _job_block("computer-acceptance", "e2e")
    assert DEPENDABOT_SKIP in block
    assert "Explain skipped private acceptance" in block
    assert "withholds repository secrets" in block


def _named_step(job_block: str, step_name: str) -> str:
    needle = f"      - name: {step_name}\n"
    if needle not in job_block:
        raise AssertionError(f"missing step {step_name!r}")
    rest = job_block.split(needle, 1)[1]
    nxt = rest.find("\n      - name: ")
    return rest if nxt < 0 else rest[:nxt]


def test_private_lane_stays_strict_for_trusted_runs() -> None:
    block = _job_block("computer-acceptance", "e2e")
    # Probe runs behind the trusted-actor guard; private steps require its output.
    assert block.count(TRUSTED_RUN_GUARD) == 1
    probe = _named_step(block, "Probe UDO deploy key")
    assert TRUSTED_RUN_GUARD in probe
    assert block.count("if: steps.udo.outputs.available == 'true'") == 7
    assert "ssh-key: ${{ secrets.UDO_READ_DEPLOY_KEY }}" in block
    assert "tests/test_computer_acceptance_e2e.py" in block


def test_public_e2e_still_depends_on_acceptance_job_result() -> None:
    e2e_block = _job_block("e2e", "package")
    assert "needs: [unit, integration, computer-acceptance]" in e2e_block
