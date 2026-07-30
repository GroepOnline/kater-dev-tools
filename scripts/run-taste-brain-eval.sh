#!/usr/bin/env bash
# Shared runner for agent-taste + design-system brain eval (fleet / Kater host).
# Default: report only. Pass --commit to push scorecards on chore/eval-scorecards.
# Never install as a laptop daemon (zero-local). See infra/README-taste-brain-eval.md
set -euo pipefail

# COMMIT=1 in the environment (systemd drop-in) is equivalent to --commit.
COMMIT="${COMMIT:-0}"
ENFORCE_FRESHNESS=1
DESIGN_SYSTEM_DIR="${DESIGN_SYSTEM_DIR:-}"
KATER_DIR="${KATER_DIR:-}"
BRANCH="${EVAL_SCORECARD_BRANCH:-chore/eval-scorecards}"

usage() {
  cat <<'EOF'
Usage: run-taste-brain-eval.sh [--commit] [--no-enforce-freshness]

Env:
  KATER_DIR            path to kater-dev-tools checkout (default: script repo root)
  DESIGN_SYSTEM_DIR    path to design-system checkout (required for ds gate)
  EVAL_SCORECARD_BRANCH  branch for --commit (default: chore/eval-scorecards)
  COMMIT=1             same as --commit
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --commit) COMMIT=1; shift ;;
    --no-enforce-freshness) ENFORCE_FRESHNESS=0; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KATER_DIR="${KATER_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"

fail_signal() {
  local msg="$1"
  local plane="${2:-agent-taste}"
  if [[ -x "$(command -v uv)" ]] && [[ -f "$KATER_DIR/.agents/scripts/taste-signal.py" ]]; then
    (cd "$KATER_DIR" && uv run python .agents/scripts/taste-signal.py add \
      --signal "$msg" --kind gate_fail --source schedule --plane "$plane" --score-hint 0.0) || true
  fi
  if [[ -n "$DESIGN_SYSTEM_DIR" ]] && [[ -f "$DESIGN_SYSTEM_DIR/ds" ]]; then
    (cd "$DESIGN_SYSTEM_DIR" && python3 ds brain signal "$msg" --kind gate_fail --source schedule --plane design-brain --score-hint 0.0) || true
  fi
}

# Evaluating a stale or conflicted checkout would publish a fresh scorecard and
# score_refresh signal for code we never actually saw, so a failed sync is fatal.
sync_repo() {
  local repo="$1"
  local plane="${2:-agent-taste}"
  if ! git pull --rebase --autostash; then
    fail_signal "git pull --rebase failed in $repo (stale or conflicted checkout)" "$plane"
    exit 1
  fi
}

echo "== kater agent-taste eval =="
cd "$KATER_DIR"
sync_repo "$KATER_DIR" agent-taste
uv sync --frozen --dev
GATE_ARGS=(--gate)
[[ "$ENFORCE_FRESHNESS" == "1" ]] && GATE_ARGS+=(--enforce-freshness)
if ! uv run python .agents/scripts/generate-taste.py --check; then
  fail_signal "generate-taste --check drift" agent-taste
  exit 1
fi
if ! uv run python .agents/scripts/eval-score.py "${GATE_ARGS[@]}" --write-refresh-signal; then
  fail_signal "eval-score gate failed" agent-taste
  exit 1
fi

if [[ -z "$DESIGN_SYSTEM_DIR" ]]; then
  echo "DESIGN_SYSTEM_DIR unset — skipping design-system brain gate"
else
  echo "== design-system brain eval =="
  cd "$DESIGN_SYSTEM_DIR"
  sync_repo "$DESIGN_SYSTEM_DIR" design-brain
  DS_ARGS=()
  [[ "$ENFORCE_FRESHNESS" == "1" ]] && DS_ARGS+=(--enforce-freshness)
  if ! python3 ds brain eval "${DS_ARGS[@]}" --write-refresh-signal; then
    fail_signal "ds brain eval failed" design-brain
    exit 1
  fi
  if ! python3 ds brain gate "${DS_ARGS[@]}"; then
    fail_signal "ds brain gate failed" design-brain
    exit 1
  fi
fi

# Each repo keeps its scorecards in its own layout, so pathspecs are passed per
# repo instead of unioned (git add fails on a pathspec that matches nothing).
commit_scorecards() {
  local repo="$1"
  shift
  (
    cd "$repo"
    git fetch origin
    # Base the branch on the freshly fetched remote tip when it exists, so
    # earlier scorecard commits survive and the push stays fast-forward.
    if git rev-parse --verify --quiet "refs/remotes/origin/$BRANCH" >/dev/null; then
      git checkout -B "$BRANCH" "origin/$BRANCH"
    else
      git checkout -B "$BRANCH"
    fi
    local -a paths=()
    local p
    for p in "$@"; do
      if [[ -e "$p" ]]; then
        paths+=("$p")
      fi
    done
    if [[ ${#paths[@]} -eq 0 ]]; then
      echo "no scorecard files in $repo"
      return 0
    fi
    git add -A -- "${paths[@]}"
    if git diff --cached --quiet; then
      echo "no scorecard changes in $repo"
    else
      git commit -m "chore: refresh taste/brain eval scorecards"
      git push -u origin "$BRANCH"
    fi
  )
}

if [[ "$COMMIT" == "1" ]]; then
  echo "== commit scorecards on $BRANCH =="
  commit_scorecards "$KATER_DIR" \
    .agents/eval/scorecard.json .agents/registry/signals.yaml
  if [[ -n "$DESIGN_SYSTEM_DIR" ]]; then
    commit_scorecards "$DESIGN_SYSTEM_DIR" \
      brain/eval/scorecard.json brain/signals/signals.yaml
  fi
fi

echo "ok: taste + brain eval passed"
