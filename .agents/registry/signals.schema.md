# Signal entry contract

Append-only. One file: `signals.yaml` with `version` + `entries` list.

## Fields

| Field | Required | Values |
|---|---|---|
| `id` | yes | stable slug, e.g. `2026-07-30T12-00-00Z-dutch` |
| `ts` | yes | ISO-8601 UTC |
| `plane` | yes | `agent-taste` \| `design-brain` \| `ui-taste` |
| `kind` | yes | `observation` \| `promotion_candidate` \| `gate_fail` \| `score_refresh` |
| `source` | yes | `human` \| `agent` \| `schedule` |
| `signal` | yes | short free text |
| `refs` | yes | list of rule ids, note paths, or commit SHAs (may be empty) |
| `score_hint` | no | `null` or float 0..1 |
| `status` | yes | `open` \| `acked` \| `promoted` \| `dismissed` |

## Rules

- Capture is **explicit only** (CLI / human). No auto-write on every edit.
- `kind=gate_fail` with `status=open` fails the eval gate.
- `status=open` and `score_hint < 0.4` counts as critical.
- Promote observations into `taste.yaml` / taste-rules via review, not via the gate.
