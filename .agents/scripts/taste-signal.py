#!/usr/bin/env python3
"""Append an explicit signal to .agents/registry/signals.yaml.

Usage:
  uv run python .agents/scripts/taste-signal.py add --signal "..." [--plane agent-taste]
  uv run python .agents/scripts/taste-signal.py add --signal "..." --kind gate_fail --ref SHA
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _signals_lock import file_lock  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SIGNALS = ROOT / ".agents" / "registry" / "signals.yaml"

PLANES = ("agent-taste", "design-brain", "ui-taste")
KINDS = ("observation", "promotion_candidate", "gate_fail", "score_refresh")
SOURCES = ("human", "agent", "schedule")
STATUSES = ("open", "acked", "promoted", "dismissed")


def _need_yaml():
    try:
        import yaml  # type: ignore
        return yaml
    except ImportError:
        sys.exit(
            "PyYAML required: install it with `uv sync --dev` (or "
            "`pip install pyyaml`), then re-run "
            "`uv run python .agents/scripts/taste-signal.py`"
        )


def load() -> dict:
    yaml = _need_yaml()
    if not SIGNALS.exists():
        return {"version": 1, "entries": []}
    data = yaml.safe_load(SIGNALS.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        sys.exit(f"invalid signals.yaml: {SIGNALS}")
    data.setdefault("version", 1)
    data.setdefault("entries", [])
    if not isinstance(data["entries"], list):
        sys.exit("signals.yaml: entries must be a list")
    return data


def save(data: dict) -> None:
    yaml = _need_yaml()
    SIGNALS.parent.mkdir(parents=True, exist_ok=True)
    SIGNALS.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return (s[:40] or "signal")


def cmd_add(args: argparse.Namespace) -> int:
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    sid = now.strftime("%Y-%m-%dT%H-%M-%SZ") + "-" + slugify(args.signal)
    refs = list(args.ref or [])
    hint = args.score_hint
    if hint is not None and not (0.0 <= hint <= 1.0):
        sys.exit("--score-hint must be between 0 and 1")
    entry = {
        "id": sid,
        "ts": ts,
        "plane": args.plane,
        "kind": args.kind,
        "source": args.source,
        "signal": args.signal,
        "refs": refs,
        "score_hint": hint,
        "status": args.status,
    }
    # Lock the whole load-append-save cycle: eval-score.py --write-refresh-signal
    # and concurrent taste-signal runs write the same file.
    with file_lock(SIGNALS):
        data = load()
        data["entries"].append(entry)
        save(data)
    print(f"ok: appended {sid} → {SIGNALS.relative_to(ROOT)}")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="Explicit agent-taste / brain signals")
    sub = p.add_subparsers(dest="cmd", required=True)
    add = sub.add_parser("add", help="append one signal entry")
    add.add_argument("--signal", required=True)
    add.add_argument("--plane", choices=PLANES, default="agent-taste")
    add.add_argument("--kind", choices=KINDS, default="observation")
    add.add_argument("--source", choices=SOURCES, default="human")
    add.add_argument("--status", choices=STATUSES, default="open")
    add.add_argument("--ref", action="append", default=[])
    add.add_argument("--score-hint", type=float, default=None)
    args = p.parse_args()
    if args.cmd == "add":
        return cmd_add(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
