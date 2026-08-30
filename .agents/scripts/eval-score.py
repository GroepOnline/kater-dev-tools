#!/usr/bin/env python3
"""Score agent-taste health; write eval/scorecard.json; optional --gate.

Usage:
  uv run python .agents/scripts/eval-score.py
  uv run python .agents/scripts/eval-score.py --gate
  uv run python .agents/scripts/eval-score.py --gate --enforce-freshness
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _signals_lock import file_lock  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
REG = ROOT / ".agents" / "registry"
EVAL = ROOT / ".agents" / "eval"
TASTE = REG / "taste.yaml"
TASTE_LOG = REG / "taste.log.yaml"
SIGNALS = REG / "signals.yaml"
THRESHOLDS = EVAL / "thresholds.yaml"
SCORECARD = EVAL / "scorecard.json"
GENERATE = ROOT / ".agents" / "scripts" / "generate-taste.py"

# Prefix of the freshness failure/warning messages built in evaluate().
FRESHNESS_PREFIX = "days_since_score_refresh"


def _need_yaml():
    try:
        import yaml  # type: ignore
        return yaml
    except ImportError:
        sys.exit(
            "PyYAML required: install it with `uv sync --dev` (or "
            "`pip install pyyaml`), then re-run "
            "`uv run python .agents/scripts/eval-score.py`"
        )


def load_yaml(path: Path, default=None):
    yaml = _need_yaml()
    if not path.exists():
        return default if default is not None else {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if data is not None else (default if default is not None else {})


def parse_ts(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def critical_signal(entry: dict) -> bool:
    if entry.get("status") != "open":
        return False
    if entry.get("kind") == "gate_fail":
        return True
    hint = entry.get("score_hint")
    if hint is not None:
        try:
            return float(hint) < 0.4
        except (TypeError, ValueError):
            return False
    return False


def taste_drift() -> tuple[int, str | None]:
    """Return (drift_count, detail). 0 means artefacts match generator."""
    if not GENERATE.exists():
        return 0, "generate-taste.py missing (skipped)"
    try:
        r = subprocess.run(
            [sys.executable, str(GENERATE), "--check"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return 1, "generate-taste.py --check timed out after 120s"
    if r.returncode == 0:
        return 0, None
    combined = "\n".join(part for part in (r.stderr, r.stdout) if part)
    detail = (combined or "drift").strip().splitlines()
    # Only DRIFT/MISSING lines are evidence; the tail may well be an "OK" line
    # for an artefact that happened to be checked last.
    offenders = [line for line in detail if line.startswith(("DRIFT", "MISSING"))]
    if offenders:
        return 1, "; ".join(line.strip() for line in offenders)
    for line in detail:
        stripped = line.strip()
        if stripped and not stripped.startswith("OK"):
            return 1, stripped
    return 1, "taste drift"


def days_since_refresh(entries: list) -> float | None:
    """Days since last score_refresh signal; None if never."""
    latest = None
    for e in entries:
        if e.get("kind") != "score_refresh":
            continue
        dt = parse_ts(str(e.get("ts") or ""))
        if dt and (latest is None or dt > latest):
            latest = dt
    if latest is None:
        # No scorecard-mtime fallback on purpose: scorecard.json is rewritten on
        # every run (and CI checkout resets mtimes), so it would report ~0 days
        # forever and silently disable the freshness gate.
        return None
    if latest.tzinfo is None:
        latest = latest.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (now - latest).total_seconds() / 86400.0


def evaluate(*, enforce_freshness: bool) -> dict:
    taste = load_yaml(TASTE, {})
    rules = taste.get("rules") or []
    tlog = load_yaml(TASTE_LOG, {})
    if isinstance(tlog, list):
        log_entries = tlog
    else:
        log_entries = tlog.get("entries") or tlog.get("observations") or []
    sig = load_yaml(SIGNALS, {"entries": []})
    entries = sig.get("entries") or []
    thr = load_yaml(THRESHOLDS, {})

    drift, drift_detail = taste_drift()
    open_crit = sum(1 for e in entries if isinstance(e, dict) and critical_signal(e))
    open_all = sum(1 for e in entries if isinstance(e, dict) and e.get("status") == "open")
    days = days_since_refresh(entries)
    rule_count = len(rules) if isinstance(rules, list) else 0

    failures: list[str] = []
    warnings: list[str] = []

    drift_max = int(thr.get("taste_drift_max", 0))
    if drift > drift_max:
        failures.append(f"taste_drift={drift} > max {drift_max}" + (f": {drift_detail}" if drift_detail else ""))

    crit_max = int(thr.get("open_critical_signals_max", 0))
    if open_crit > crit_max:
        failures.append(f"open_critical_signals={open_crit} > max {crit_max}")

    rule_min = int(thr.get("rule_count_min", 1))
    if rule_count < rule_min:
        failures.append(f"rule_count={rule_count} < min {rule_min}")

    warn_days = float(thr.get("days_since_score_refresh_warn", 2))
    fail_days = float(thr.get("days_since_score_refresh_fail", 7))
    do_fresh = enforce_freshness or bool(thr.get("enforce_score_freshness", False))
    if days is None:
        warnings.append("days_since_score_refresh: never refreshed")
        if do_fresh:
            failures.append("days_since_score_refresh: never refreshed (freshness enforced)")
    else:
        if days > warn_days:
            warnings.append(f"days_since_score_refresh={days:.1f} > warn {warn_days}")
        if do_fresh and days > fail_days:
            failures.append(f"days_since_score_refresh={days:.1f} > fail {fail_days}")

    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "ts": now,
        "pass": len(failures) == 0,
        "plane": "agent-taste",
        "metrics": {
            "taste_drift": drift,
            "rule_count": rule_count,
            "open_critical_signals": open_crit,
            "open_signals": open_all,
            "days_since_score_refresh": None if days is None else round(days, 2),
            "taste_log_entries": len(log_entries) if isinstance(log_entries, list) else 0,
        },
        "failures": failures,
        "warnings": warnings,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gate", action="store_true", help="exit 1 if scorecard fails")
    p.add_argument(
        "--enforce-freshness",
        action="store_true",
        help="fail when score refresh is stale (scheduled/full gate)",
    )
    p.add_argument(
        "--write-refresh-signal",
        action="store_true",
        help="append kind=score_refresh after a passing eval",
    )
    args = p.parse_args()

    card = evaluate(enforce_freshness=args.enforce_freshness)
    EVAL.mkdir(parents=True, exist_ok=True)
    SCORECARD.write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(card, indent=2))

    # Freshness failures must not block the refresh signal, otherwise a repo that
    # never recorded one can never record its first (deadlock under --enforce-freshness).
    blocking = [f for f in card["failures"] if not f.startswith(FRESHNESS_PREFIX)]
    if not blocking and args.write_refresh_signal:
        # append via taste-signal helper logic inline to avoid subprocess dependency cycle
        yaml = _need_yaml()
        # Lock the whole load-append-save cycle: taste-signal.py (and a second
        # eval-score run) write the same file and would clobber this entry.
        with file_lock(SIGNALS):
            data = load_yaml(SIGNALS, {"version": 1, "entries": []})
            data.setdefault("entries", [])
            now = datetime.now(timezone.utc)
            data["entries"].append(
                {
                    "id": now.strftime("%Y-%m-%dT%H-%M-%SZ") + "-score-refresh",
                    "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "plane": "agent-taste",
                    "kind": "score_refresh",
                    "source": "schedule",
                    "signal": "eval-score pass",
                    "refs": [],
                    "score_hint": 1.0,
                    "status": "acked",
                }
            )
            SIGNALS.write_text(
                yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
                encoding="utf-8",
            )

    if args.gate and not card["pass"]:
        for f in card["failures"]:
            print(f"FAIL: {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
