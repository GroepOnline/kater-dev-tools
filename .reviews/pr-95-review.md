# PR #95 review — Execution Foundation

Lens: `docs/architecture/runtime-kronkel.md` +
`docs/architecture/execution-foundation.md`.
Head at review time: `30564a5` (post CodeFactor split).

## Verdict

Foundation is aligned: Kater blijft execute-plane, GitHub is de eerste
toolkit, `kater_pr_*` zijn wrappers. Niet mergen als “volledig systeem” of
als startsein voor een Rust/Redis-daemon.

## Plane check

| Eis | Diff | Ok? |
| --- | --- | --- |
| Catalog `toolkit → integration → connection → action` | `PluginManifest`, `ConnectionView`, `IntegrationManifest`, `/api/connections`, `/api/actions` | ja |
| `execute(connection, action, input, identity, policy_context)` | `src/kater/executor.py`, REST, MCP, CLI | ja |
| GitHub gemigreerd | `github.pr.*` + wrappers in `registry.py` | ja |
| Secrets uit views | `ConnectionView` / OAuth-test zonder tokenwaarden | ja |
| Policy op dangerous writes | merge eist non-anonymous + `expected_head_sha`; `allow_dangerous` | ja |
| Docs lock split | `docs/architecture/execution-foundation.md` | ja |
| Geen Commander/Factory/OCX-creep | geen run-graph, geen deploy, geen model routing | ja |
| Geen Redis/Rust rewrite | niet in deze PR | ja |

## Findings (niet blokkerend voor foundation, wél reviewen)

1. **`allow_dangerous` default True.** Mutations zonder merge/delete-token
   blijven anonymous-ok (`linear.issues.create`). Alleen token-gevaarlijke
   acties eisen actor. Bewust; niet “alles is dangerous”.
2. **Idempotency replay checkt identity niet opnieuw.** Zelfde key +
   fingerprint geeft de cached envelope terug. Caller met andere
   `actor_id` kan een resultaat herhalen. Acceptabel voor v0 als keys
   caller-scoped blijven; later key = identity + fingerprint.
3. **GitHub `AuthBindingKind.NONE` op core.** Doctor blijft groen zonder
   PAT; WRITE blijft via aparte `env_ok`. Reviewers: dit is core-cloud
   hygiene, geen “GitHub zonder credentials in ops”.
4. **Timeouts via `ThreadPoolExecutor`.** Werkt; geen async cancel van de
   provider-call. Geen reden om Redis/Rust in te trekken.
5. **`list_connection_views` slikt store-fouten.** Nodig voor
   catalog-visibility tests die SQLite verbieden. Publieke catalog mag
   geen writer openen.
6. **CodeFactor Complex Method** op het oude `execute()` is gefixt door
   split (`_prepare`, `_run_attempts`, `_invoke`). Geen taalwissel.

## Out of scope (kronkel)

Rust+Zig daemon, Redis als MCP-bus, “één volledig systeem”. Dat is
afgewezen tot er gemeten fan-out/p99 is. Zie de kronkel-doc.

## Verify

```bash
uv run ruff check . && uv run mypy && uv run pytest --no-cov
```

Laatst lokaal: ruff/mypy groen; foundation + executor + API/CLI 129
passed; full suite was 1976 passed / 13 skipped op `5337df3`.
