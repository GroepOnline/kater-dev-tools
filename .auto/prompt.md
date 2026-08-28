# Autoresearch: Kater Dev MCP — 85% effectiever / kwalitatiever

## Objective
Maak de Kater Dev MCP-tool-surface significant effectiever: **sneller** (boot + registry-walk,
minder overhead per tool-call), **kwalitatiever** (complete, eenduidige tool-definities met
bruikbare beschrijvingen en correcte JSON-schema's), en **beter routable** (tool-keuze voor
agents). Streefdoel: meetbare ~85% verbetering op de primaire metric t.o.v. baseline.

## Metrics
- **Primary**: `tool_count` × `described_tools`-ratio = `described_tools / tool_count` — de
  aandeel van tools met een inhoudelijke beschrijving (hoger is beter). Kwaliteitsproxy die geen
  live gateway nodig heeft.
- **Secondary**: `boot_ms`, `registry_walk_ms` (lager beter — snelheid), `avg_description_chars`
  (richtwaarde 60–200, beschrijving is de tool-call-kwaliteit), `app_tools_listed`.

## How to Run
`./.auto/measure.sh` — output `METRIC name=value` regels. Determinisch, offline, geen Kater-aanroepen.

## Files in Scope
- `src/kater/mcp_server.py` — FastMCP app, tool-registratie, boot-path
- `src/kater/registry.py` — tools_for_profile, per-profile tool-sets
- `src/kater/profiles.py` — all_tool_sources, profiel-definities (TOOL-beschrijvingen)
- `src/kater/cli.py` — serve/commands (als tool-remapping daar zit)
- `.auto/measure.sh`, `.auto/log.jsonl` — meet- en log-artefacten

## Off Limits
- Geen live `kater` gateway/SSH/cloud-aanroepen vanuit de batterij
- Geen nieuwe zware dependencies (alleen stdlib/bestaande deps)
- Geen wijzigingen aan `SECURITY.md`-gedrag: authgate/oauth/tunnel-blokkades blijven
- Geen remote worktrees/java/go; dit is Python (`uv run`)

## Constraints
- `uv run pytest` moet groen (tests/ bestaan; bij schemawijzigingen testen meeliften)
- `uv run ruff check` clean
- Batches blijven <10s in de batterij (snel herhalen)

## What's Been Tried
- (baseline vóór eerste experiment — nog niets)