"""Execute the real workflow script with hermetic GitHub API mocks."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = ROOT / ".github/workflows/automerge.yml"


def _run_script(scenario: dict[str, object]) -> dict[str, object]:
    """Execute the workflow's auto-merge script against mocked GitHub APIs."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    step = next(
        step
        for step in workflow["jobs"]["automerge"]["steps"]
        if step["name"] == "Enable auto-merge for Dependabot"
    )
    node = shutil.which("node")
    assert node is not None, "Node.js is required to exercise the GitHub Actions script"
    harness = """
        import { readFileSync } from 'node:fs';
        const { script, scenario } = JSON.parse(readFileSync(0, 'utf8'));
        const calls = [];
        const notices = [];
        const infos = [];
        const context = {
            repo: { owner: 'test-owner', repo: 'test-repo' },
            payload: {
                pull_request: scenario.noPr ? undefined : { node_id: 'PR_node', number: 85 },
            },
        };
        const github = {
            rest: { repos: { get: async (params) => {
                calls.push({ kind: 'metadata', params });
                if (scenario.metadataError) throw new Error(scenario.metadataError);
                return { data: scenario.repository };
            } } },
            graphql: async (query, variables) => {
                calls.push({ kind: 'mutation', query, variables });
                if (scenario.mutationError) throw new Error(scenario.mutationError);
                return {};
            },
        };
        const core = {
            notice: (message) => notices.push(message), info: (message) => infos.push(message),
        };
        const AsyncFunction = Object.getPrototypeOf(async function () {}).constructor;
        let error = null;
        try {
            await new AsyncFunction('github', 'context', 'core', script)(github, context, core);
        } catch (caught) {
            error = caught.message;
        }
        console.log(JSON.stringify({ calls, notices, infos, error }));
    """
    completed = subprocess.run(
        [node, "--input-type=module", "-e", harness],
        input=json.dumps({"script": step["with"]["script"], "scenario": scenario}),
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )
    return json.loads(completed.stdout)


def test_disabled_policy_skips_without_a_mutation() -> None:
    """Skip the mutation when repository auto-merge is disabled."""
    result = _run_script({"repository": {"allow_auto_merge": False}})
    assert result["error"] is None
    assert result["calls"] == [
        {"kind": "metadata", "params": {"owner": "test-owner", "repo": "test-repo"}}
    ]
    assert result["notices"] == [
        "Auto-merge skipped: disabled by repository policy (allow_auto_merge=false)."
    ]
    assert result["infos"] == []


def test_enabled_policy_preserves_squash_automerge() -> None:
    """Keep squash auto-merge behavior when repository policy allows it."""
    result = _run_script({"repository": {"allow_auto_merge": True}})
    assert result["error"] is None
    assert [call["kind"] for call in result["calls"]] == ["metadata", "mutation"]
    mutation = result["calls"][1]
    assert "enablePullRequestAutoMerge" in mutation["query"]
    assert "mergeMethod: SQUASH" in mutation["query"]
    assert mutation["variables"] == {"id": "PR_node"}
    assert result["notices"] == []
    assert result["infos"] == ["auto-merge enabled for PR #85"]


@pytest.mark.parametrize("error", ["Forbidden", "Not Found", "API unavailable"])
def test_metadata_errors_propagate_without_a_mutation(error: str) -> None:
    """Propagate repository metadata errors without attempting a mutation."""
    result = _run_script({"metadataError": error})
    assert result["error"] == error
    assert [call["kind"] for call in result["calls"]] == ["metadata"]
    assert result["notices"] == []


def test_mutation_error_is_not_hidden_as_a_policy_skip() -> None:
    """Propagate mutation errors instead of reporting a policy skip."""
    result = _run_script(
        {"repository": {"allow_auto_merge": True}, "mutationError": "Other GraphQL failure"}
    )
    assert result["error"] == "Other GraphQL failure"
    assert [call["kind"] for call in result["calls"]] == ["metadata", "mutation"]
    assert result["notices"] == []
    assert result["infos"] == []


@pytest.mark.parametrize(
    "repository", [{}, {"allow_auto_merge": None}, {"allow_auto_merge": "false"}]
)
def test_missing_or_malformed_setting_fails_closed(repository: dict[str, object]) -> None:
    """Fail closed when the repository policy setting is absent or invalid."""
    result = _run_script({"repository": repository})
    assert result["error"] == (
        "Repository metadata did not provide a boolean allow_auto_merge setting."
    )
    assert [call["kind"] for call in result["calls"]] == ["metadata"]
    assert result["notices"] == []


def test_missing_pr_remains_a_noop() -> None:
    """Leave the workflow as a no-op when the event has no pull request."""
    result = _run_script({"noPr": True})
    assert result == {"calls": [], "notices": [], "infos": [], "error": None}


def test_existing_permissions_are_unchanged() -> None:
    """Preserve the workflow's existing permissions."""
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    assert workflow["permissions"] == {
        "contents": "write", "pull-requests": "write", "checks": "read"
    }
