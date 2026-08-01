# Agent taste (canonieke bron)

Dit is de gedeelde agent-gedrag-taste-plane voor ChefGroep coding agents.
Niet te verwarren met UI-taste in `design-system/taste/`.

| Plane | Waar | Wat |
|---|---|---|
| UI-taste | `design-system/taste/` | hoe product-UI eruitziet |
| Agent-taste (deze map) | `kater-dev-tools/.agents/registry/` | hoe agents zich gedragen |
| Per-tool overlay | `taste.overlay.<tool>.yaml` | alleen syntax/locatie, geen inhoud-override |

## Bestanden

| Pad | Rol |
|---|---|
| `registry/taste.yaml` | canonieke regels |
| `registry/taste.log.yaml` | ruwe observaties (nog niet gepromoveerd) |
| `registry/taste.overlay.*.yaml` | dunne tool-wrappers |
| `registry/signals.yaml` | expliciete signal-log (append-only) |
| `eval/thresholds.yaml` | harde drempels voor `--gate` |
| `eval/scorecard.json` | gegenereerde scorecard |
| `scripts/generate-taste.py` | schrijft per-tool artefacts |
| `scripts/taste-signal.py` | append signal |
| `scripts/eval-score.py` | scorecard + optional `--gate` |

## Precedence

1. `taste.yaml` is single source of truth voor inhoud.
2. Overlays mogen alleen toevoegen (pad, markers, syntax), nooit `text:` overschrijven.
3. Gegenereerde bestanden krijgen header `GENERATED from .agents/registry/taste.yaml`.
4. Globaal `~/.commandcode` mag later project-artefacts aanvullen; het mag canonieke regels niet stil vervangen.

## Genereren

```bash
python3 .agents/scripts/generate-taste.py
python3 .agents/scripts/generate-taste.py --check   # drift: exit 1 als artefacts stale
python3 .agents/scripts/generate-taste.py --target /pad/naar/consumer-repo
python3 .agents/scripts/generate-taste.py --target /pad/naar/consumer-repo --check
```

Targets (v1):

- `.commandcode/taste/taste.md` (Command Code)
- `.cursor/rules/taste.mdc` (Cursor)
- `CLAUDE.md` sectie tussen `<!-- TASTE:START -->` … `<!-- TASTE:END -->`

Pi en Agy: targets nog niet aangesloten tot hun configformaat is geverifieerd.

## Loop

```text
observatie → taste.log.yaml → review → promote naar taste.yaml → generate-taste.py → commit artefacts
```

## Signals + eval

Capture is **expliciet alleen** (geen auto-write op elke edit):

```bash
uv run python .agents/scripts/taste-signal.py add --signal "…" --plane agent-taste
uv run python .agents/scripts/eval-score.py
uv run python .agents/scripts/eval-score.py --gate
```

Thresholds: `taste_drift=0`, `open_critical_signals=0`, `rule_count_min>=1`,
score-freshness warn/fail alleen met `--enforce-freshness` of scheduled gate.

Dual scheduler: GHA `agent-taste-eval.yml` + fleet
`scripts/run-taste-brain-eval.sh` / `infra/taste-brain-eval.timer`
(zie `infra/README-taste-brain-eval.md`). Scorecards in CI = artefact, geen
auto-commit naar main.

## Relatie met design-system

`design-system` besloot 2026-07-30 dat de canonieke agent-taste hier hoort.
Het repo consumeert gegenereerde Command Code, Cursor en Claude Code
artefacts via `--target`; het bevat geen tweede `taste.yaml`.
Zie daar: `brain/Decisions/2026-07-30 Agent-taste buiten dit repo.md`.
