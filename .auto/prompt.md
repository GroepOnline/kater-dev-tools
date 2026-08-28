# Autoresearch: Kater Dev MCP — 85% effectiever / kwalitatiever

## Objective
Maak de Kater Dev MCP-tool-surface significant effectiever: **sneller** (boot + registry-walk,
minder overhead per tool-call), **kwalitatiever** (complete, eenduidige tool-definities met
bruikbare beschrijvingen en correcte JSON-schema's), en **beter routable** (tool-keuze voor
agents). Streefdoel: meetbare ~85% verbetering op de primaire metric t.o.v. baseline.

## Metrics
- **Primary**: `cold_ms` (lager is beter) — time-to-tool-list in een fris proces: de tijd die een
  MCP-client wacht voordat de tool-surface beschikbaar is. Dat is de "sneller"-helft van het doel
  (85% sneller = base ~500ms → <75ms).
- **Secondary**: `registry_walk_ms` (lager beter), `boot_ms` (lager beter),
  `description_ratio` (alle 17 tools beschreven — al 1.0, houden), `avg_description_chars`
  (richtwaarde 60–200; agenten kiezen tools op beschrijving → tool-call-kwaliteit),
  `app_tools_listed` (⩾0 = server bootbaar).

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
- **Baseline (2026-08-28)**: cold_ms ≈ 500–900ms; het zware gewicht zit in de cold-importketen
  (kater + fastmcp/pydantic + mcp_server top-level imports), niet in build_native_tools (~0ms wam).
  Kans: hete imports (fastmcp, proxy, browser, pr_control) lazy maken achter getters → cold-start
  kan naar de 100ms-klasse. Description-ratio zit al op 1.0 (niets te winnen op aanwezigheid;
  wel op rijkdom van beschrijvingen).