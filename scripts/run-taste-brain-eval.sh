#!/usr/bin/env bash
# Shared runner for agent-taste + design-system brain eval (fleet / Kater host).
# Default: report only. Pass --commit to push scorecards on chore/eval-scorecards.
# Never install as a laptop daemon (zero-local). See infra/README-taste-brain-eval.md
set -euo pipefail

COMMIT=0
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

echo "== kater agent-taste eval =="
cd "$KATER_DIR"
git pull --rebase --autostash 2>/dev/null || git pull --rebase || true
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
  git pull --rebase --autostash 2>/dev/null || git pull --rebase || true
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

if [[ "$COMMIT" == "1" ]]; then
  echo "== commit scorecards on $BRANCH =="
  for repo in "$KATER_DIR" ${DESIGN_SYSTEM_DIR:+"$DESIGN_SYSTEM_DIR"}; do
    (
      cd "$repo"
      git fetch origin 2>/dev/null || true
      git checkout -B "$BRANCH"
      git add -A -- \
        .agents/eval/scorecard.json .agents/registry/signals.yaml \
        brain/eval/scorecard.json brain/signals/signals.yaml 2>/dev/null || true
      if git diff --cached --quiet; then
        echo "no scorecard changes in $repo"
      else
        git commit -m "chore: refresh taste/brain eval scorecards"
        git push -u origin "$BRANCH"
      fi
    )
  done
fi

echo "ok: taste + brain eval passed"
