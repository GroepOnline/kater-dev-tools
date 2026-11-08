# Runtime kronkel — Python blijft, geen Redis-MCP-systeem

Brain dump (2026-09-12). Geen RFC, geen go-besluit. Wel de review-lens
voor PRs op Kater: wat Kater is, wat het niet wordt, en wanneer een
systems-daemon wél ter sprake mag komen.

Canoniek contract blijft
[`execution-foundation.md`](execution-foundation.md).

## Kronkel

Eén Rust+Zig daemon die alle connections doorstuurt via Redis, “gecombineerd
met MCP”, als volledig systeem.

Het nuttige deel: een langlevende connection fabric (warme sessies,
multiplex, backpressure). Dat lijkt op wat `src/kater/connectors/dispatch.py`
nu al in het klein doet — stateless per call, optioneel een pooled
stdio-backend met TTL.

De rest is plane-vervaging.

## Wat Kater is

Kater is ChefGroep's execution/integration-gateway:

```text
toolkit → integration → connection → action
kater.execute(connection, action, input, identity, policy_context)
```

Job: catalog, credentials op connections, schema, policy, retries,
idempotency, audit. Geen inference (OCX), geen runs/workflows (Commander),
geen fleet-deploy (Factory).

MCP is een interface die Kater aanroept. MCP is niet de architectuur.

Python (3.11–3.14, `uv`, één proces, drie listeners) blijft de runtime
tot er gemeten pijn is: p99 op `execute`, connection-fan-out, of een
hosted multi-node execute-plane. CodeFactor-complexiteit op `execute()`
is te veel verantwoordelijkheid in één functie, geen taalvonnis.

Vendor-werk is al polyglot: stdio-backends via Node/`npx`, Studio is
React/Vite → statische assets, GitHub-native acties wrappen Python + `gh`.

## Wat de kronkel fout tekent

**Redis is de verkeerde bus.** MCP is JSON-RPC over stdio/SSE/HTTP
(initialize, sessie, schemas). Redis is queue/cache. Elke call via Redis
is serialiseren + protocol opnieuw openen + timeouts/idempotency opnieuw +
secrets in de broker. Eén machine, één proces: in-process pool wint.
Redis pas als er meerdere workers/nodes zijn.

**MCP-als-systeem.** Skills en Commander praten *tegen* Kater. Als MCP de
ruggengraat wordt, wordt Kater weer een tool-host.

**“Volledig systeem”.** Eén daemon voor connections + MCP + Redis-routing
+ alles is Commander + halve Factory + service mesh. Credentials blijven
op Kater-connections. Taken bij Commander. Deploy bij Factory.

**Rust én Zig in één daemon.** Twee toolchains zonder split. Als er ooit
een execute-worker komt: Rust, niet beide. Zig is alloc/FFI, niet deze
catalog/policy-loop.

## Wat later mag (niet nu)

Optionele Rust execute-worker *naast* Python-Kater, niet in plaats van:

- Python houdt catalog, CLI, doctor, policy-definities, MCP/REST-surface
- Worker houdt warme provider-connections en doet timeout/retry
- Contract blijft `connection + action + input + identity`
- Redis alleen als multi-worker queue, niet als pad van elke tool-call

Trigger: gemeten load, niet een herschrijf-drang. Eerst foundation
productiseren (GitHub-toolkit hard, daarna Linear → …).

## PR-review lens

Gebruik dit bij elke Kater-PR. Fail de review als een diff de kronkel
implementeert zonder de trigger hierboven.

1. **Plane.** Credentials/connections/execute/policy/audit = Kater.
   Runs/workflows = Commander. Deploy/config/fleet = Factory.
   Modelkeys/routes = OCX. MCP/plugins/skills = interface.
2. **Contract.** Nieuwe acties gaan via `execute(connection, action, input,
   identity, policy_context)`. Speciale `kater_pr_*` (en later andere
   shortcuts) zijn wrappers, geen tweede pad.
3. **Secrets.** Catalog, `ConnectionView`, REST en MCP echoën geen
   tokenwaarden. Hoogstens secret *names*.
4. **Dangerous writes.** Merge/delete/admin/drop via policy (actor,
   `allow_dangerous`, exact-head waar van toepassing). Niet “Kater is een
   PR-merger”.
5. **Geen bus in het execute-pad.** Geen Redis/NATS/queue tussen caller en
   provider tenzij de PR multi-node fan-out bewijst.
6. **Geen taalwissel.** Geen Rust/Zig/TS rewrite van de gateway in deze
   repo zonder gemeten p99/fan-out-bewijs.
7. **Geen tweede Commander.** Geen run-graph, agent-orchestratie of
   workflow-engine in Kater.
8. **MCP blijft transport.** Nieuwe native tools zijn dunne surfaces op
   `execute` / catalog, geen parallelle architectuur.

Review-notities horen in `.reviews/pr-<n>-review.md` (zie
`.reviews/README.md`). Open-PR volgorde:
[`../merge-train-20260912.md`](../merge-train-20260912.md).
