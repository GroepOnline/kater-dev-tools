from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated

import typer

from kater.control_plane.models import AccountState, ProviderAccount, QuotaWindow, RoutingRequest
from kater.control_plane.routing import QuotaAwareRouter
from kater.control_plane.store import (
    list_route_candidates,
    query_routing_decisions,
    remove_route_candidate,
    upsert_route_candidate,
)

app = typer.Typer(
    help="Manage persistent logical capability routes and account fallback pools."
)


def _print(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _parse_quota(spec: str) -> QuotaWindow:
    parts = spec.split(":", 3)
    if len(parts) < 2:
        raise typer.BadParameter("quota must be NAME:LIMIT[:USED[:RESET_ISO]]")
    try:
        limit = int(parts[1])
        used = int(parts[2]) if len(parts) >= 3 and parts[2] else 0
        resets_at = (
            datetime.fromisoformat(parts[3].replace("Z", "+00:00"))
            if len(parts) == 4
            else None
        )
    except ValueError as exc:
        raise typer.BadParameter(f"invalid quota {spec!r}: {exc}") from exc
    return QuotaWindow(name=parts[0], limit=limit, used=used, resets_at=resets_at)


def _binding_payload(capability: str, account: ProviderAccount) -> dict[str, object]:
    return {
        "capability": capability,
        "account_id": account.account_id,
        "provider": account.provider,
        "backend": account.backend,
        "tool_name": account.tool_name,
        "scopes": sorted(account.scopes),
        "priority": account.priority,
        "max_concurrent": account.max_concurrent,
        "cost_per_million_units": account.cost_per_million_units,
        "latency_ms": account.latency_ms,
        "state": account.state.value,
        "cooldown_until": account.cooldown_until,
        "quota_windows": [
            {
                "name": window.name,
                "limit": window.limit,
                "used": window.used,
                "resets_at": window.resets_at,
            }
            for window in account.quota_windows
        ],
    }


@app.command("add")
def add_route(
    capability: str,
    account_id: Annotated[str, typer.Option("--account")],
    provider: Annotated[str, typer.Option("--provider")],
    backend: Annotated[str, typer.Option("--backend")],
    tool_name: Annotated[str, typer.Option("--tool")],
    scopes: Annotated[str, typer.Option("--scopes")] = "",
    priority: Annotated[int, typer.Option("--priority")] = 100,
    max_concurrent: Annotated[int, typer.Option("--max-concurrent")] = 1,
    cost: Annotated[float, typer.Option("--cost-per-million")] = 0.0,
    latency_ms: Annotated[float, typer.Option("--latency-ms")] = 0.0,
    state: Annotated[AccountState, typer.Option("--state")] = AccountState.ACTIVE,
    quota: Annotated[list[str] | None, typer.Option("--quota")] = None,
) -> None:
    """Add or replace one account candidate for a logical capability alias."""
    account = ProviderAccount(
        account_id=account_id,
        provider=provider,
        backend=backend,
        tool_name=tool_name,
        scopes=frozenset(item.strip() for item in scopes.split(",") if item.strip()),
        priority=priority,
        max_concurrent=max_concurrent,
        cost_per_million_units=cost,
        latency_ms=latency_ms,
        state=state,
        quota_windows=tuple(_parse_quota(item) for item in (quota or [])),
    )
    upsert_route_candidate(capability, account)
    _print({"saved": True, **_binding_payload(capability, account)})


@app.command("list")
def list_routes(
    capability: Annotated[str | None, typer.Option("--capability")] = None,
) -> None:
    """List persistent route candidates; secret material is never stored or shown."""
    bindings = list_route_candidates(capability)
    _print(
        {
            "total": len(bindings),
            "routes": [
                _binding_payload(item.capability, item.account) for item in bindings
            ],
        }
    )


@app.command("remove")
def remove_route(capability: str, account_id: str) -> None:
    """Remove one account candidate from a capability pool."""
    removed = remove_route_candidate(capability, account_id)
    _print({"removed": removed, "capability": capability, "account_id": account_id})
    if not removed:
        raise typer.Exit(code=1)


@app.command("dry-run")
def dry_run(
    capability: str,
    context_id: Annotated[str, typer.Option("--context")] = "cli",
    scopes: Annotated[str, typer.Option("--scopes")] = "",
    estimated_units: Annotated[int, typer.Option("--estimated-units")] = 1,
) -> None:
    """Rank a route pool without invoking a backend or consuming quota."""
    bindings = list_route_candidates(capability)
    request = RoutingRequest(
        capability=capability,
        context_id=context_id,
        required_scopes=frozenset(
            item.strip() for item in scopes.split(",") if item.strip()
        ),
        estimated_units=estimated_units,
    )
    decisions = QuotaAwareRouter().rank([item.account for item in bindings], request)
    _print(
        {
            "request": {
                "capability": capability,
                "context_id": context_id,
                "required_scopes": sorted(request.required_scopes),
                "estimated_units": estimated_units,
            },
            "ranked": [
                {
                    "account_id": item.account_id,
                    "provider": item.provider,
                    "backend": item.backend,
                    "tool_name": item.tool_name,
                    "score": item.score,
                    "reasons": item.reasons,
                }
                for item in decisions
            ],
        }
    )


@app.command("decisions")
def decisions(
    capability: Annotated[str | None, typer.Option("--capability")] = None,
    context_id: Annotated[str | None, typer.Option("--context")] = None,
    limit: Annotated[int, typer.Option("--limit")] = 50,
) -> None:
    """Inspect the durable routing decision ledger."""
    rows = query_routing_decisions(
        capability=capability,
        context_id=context_id,
        limit=limit,
    )
    _print({"total": len(rows), "decisions": rows})


if __name__ == "__main__":
    app()