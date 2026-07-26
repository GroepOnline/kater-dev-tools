from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/ci.yml"
DEPENDABOT_SKIP = (
    "if: github.event_name == 'pull_request' && github.actor == 'dependabot[bot]'"
)
TRUSTED_ACTOR_GUARD = (
    "if: github.event_name != 'pull_request' || github.actor != 'dependabot[bot]'"
)


def _computer_acceptance_block() -> str:
    text = WORKFLOW.read_text(encoding="utf-8")
    return text.split("  computer-acceptance:\n", 1)[1].split(
        "\n  # ── e2e:", 1
    )[0]


def test_dependabot_gets_auditable_private_lane_skip() -> None:
    block = _computer_acceptance_block()
    assert DEPENDABOT_SKIP in block
    assert "Explain skipped private acceptance" in block
    assert "withholds repository secrets" in block


def test_private_lane_stays_strict_for_trusted_runs() -> None:
    block = _computer_acceptance_block()
    # Checkout Kater, checkout UDO, setup uv, sync, npm install, acceptance test,
    # and evidence upload must all remain behind the same trusted-actor guard.
    assert block.count(TRUSTED_ACTOR_GUARD) == 7
    assert "ssh-key: ${{ secrets.UDO_READ_DEPLOY_KEY }}" in block
    assert "tests/test_computer_acceptance_e2e.py" in block


def test_public_e2e_still_depends_on_acceptance_job_result() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    e2e_block = text.split("  e2e:\n", 1)[1].split("\n  # ── package:", 1)[0]
    assert "needs: [unit, integration, computer-acceptance]" in e2e_block
