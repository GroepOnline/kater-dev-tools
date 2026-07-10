from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any


def _replace_once(value: str, old: str, new: str, *, label: str) -> str:
    count = value.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one occurrence, found {count}")
    return value.replace(old, new, 1)


def _replace_all(value: str, replacements: dict[str, str]) -> str:
    for old, new in replacements.items():
        if old not in value:
            raise RuntimeError(f"dashboard review fix target missing: {old!r}")
        value = value.replace(old, new)
    return value


def _patch_dashboard(dashboard: Any) -> None:
    dashboard._JS = _replace_once(
        dashboard._JS,
        """function trackedRAF(fn) {
  if (typeof requestAnimationFrame !== 'function') return 0;
  const id = requestAnimationFrame((ts) => { rafFrames.delete(id); fn(ts); });
  rafFrames.add(id);
  return id;
}
  const id = setTimeout(() => { timers.delete(id); fn(); }, ms);
  timers.add(id);
  return id;
}
""",
        """function trackedRAF(fn) {
  if (typeof requestAnimationFrame !== 'function') return 0;
  const id = requestAnimationFrame((ts) => { rafFrames.delete(id); fn(ts); });
  rafFrames.add(id);
  return id;
}
function trackedTimeout(fn, ms) {
  const id = setTimeout(() => { timers.delete(id); fn(); }, ms);
  timers.add(id);
  return id;
}
""",
        label="trackedTimeout helper",
    )
    dashboard._JS = _replace_once(
        dashboard._JS,
        "  const url = '/oauth/authorize'",
        "  const url = '/authorize'",
        label="OAuth authorization route",
    )
    dashboard._JS = _replace_once(
        dashboard._JS,
        "  const list = Array.isArray(data) ? data : (data.backends || []);",
        "  const list = Array.isArray(data) ? data : (data.backends || data.servers || []);",
        label="backend response compatibility",
    )
    dashboard._JS = _replace_once(
        dashboard._JS,
        "  $('detail-name').textContent = server.name;",
        """  $('detail-name').textContent = server.name;
  ['confirm-server-enable', 'confirm-server-disable'].forEach((id) => {
    const button = $(id);
    if (button) button.dataset.name = server.name;
  });""",
        label="detail confirm target",
    )
    dashboard._JS = _replace_once(
        dashboard._JS,
        """  const titles = {
    enable: 'ENABLE SERVER', disable: 'DISABLE SERVER',
    'save-credentials': 'SAVE CREDENTIALS',
  };
  const bodies = {
    enable: 'Enabling "' + (name || '') + '" opens a live tool connection. Confirm?',
    disable: 'Disabling "' + (name || '') + '" cuts an active tool connection. Confirm?',
    'save-credentials': 'Saving credentials writes secrets to storage. Confirm?',
  };
  const t = $('confirm-title'), b = $('confirm-body');
  if (t) t.textContent = titles[action] || 'CONFIRM';
  if (b) b.textContent = bodies[action] || '';
""",
        """  const titles = {
    enable: 'Enable server', disable: 'Disable server',
    'save-credentials': 'Save credentials',
  };
  const labels = {
    enable: 'Enable server', disable: 'Disable server',
    'save-credentials': 'Save credentials',
  };
  const bodies = {
    enable: 'Enabling "' + (name || '') + '" opens a live tool connection.',
    disable: 'Disabling "' + (name || '') + '" cuts an active tool connection.',
    'save-credentials': 'Saving credentials writes secrets to storage.',
  };
  const t = $('confirm-title'), b = $('confirm-body');
  if (t) t.textContent = titles[action] || 'Confirm action';
  if (b) b.textContent = bodies[action] || '';
  if (confirmCtx.ok) confirmCtx.ok.textContent = labels[action] || 'Continue';
""",
        label="specific confirm labels",
    )
    dashboard._JS = _replace_once(
        dashboard._JS,
        """  const dlg = $('confirm');
  if (!dlg) return;
  const titles = {""",
        """  const dlg = $('confirm');
  if (!dlg) return;
  dlg.hidden = false;
  const titles = {""",
        label="confirm dialog open state",
    )
    dashboard._JS = _replace_once(
        dashboard._JS,
        """  dlg.classList.add('hidden');
  dlg.setAttribute('aria-hidden', 'true');
  confirmCtx = null;""",
        """  dlg.classList.add('hidden');
  dlg.setAttribute('aria-hidden', 'true');
  dlg.hidden = true;
  confirmCtx = null;""",
        label="confirm dialog close state",
    )
    dashboard._JS = _replace_all(
        dashboard._JS,
        {
            "server.enabled ? 'ENABLED' : 'DISABLED'": "server.enabled ? 'Enabled' : 'Disabled'",
            "telegraph('tunnel toggle failed: ' + e.message, 'err')": (
                "telegraph('Tunnel toggle failed: ' + e.message + "
                "'. Retry; if it fails again, check the gateway logs.', 'err')"
            ),
            "'server ' + (enabled ? 'enable' : 'disable') + ' failed: ' + e.message,": (
                "'Server ' + (enabled ? 'enable' : 'disable') + ' failed: ' + e.message + "
                "'. Retry; if it fails again, check authentication and gateway logs.',"
            ),
            "telegraph('save failed: ' + e.message, 'err')": (
                "telegraph('Credential save failed: ' + e.message + "
                "'. Verify the token and storage permissions, then retry.', 'err')"
            ),
            "telegraph('deploy config failed: ' + e.message, 'err')": (
                "telegraph('Deploy configuration failed: ' + e.message + "
                "'. Reload the dashboard; if it persists, check /api/deploy/config.', 'err')"
            ),
            "telegraph('clipboard blocked by browser', 'err')": (
                "telegraph('Clipboard access was blocked. Allow "
                "clipboard access or copy the code manually.', 'err')"
            ),
            "telegraph('clipboard unavailable', 'err')": (
                "telegraph('Clipboard API is unavailable. Select "
                "the code and copy it manually.', 'err')"
            ),
            "telegraph('settings load failed: ' + e.message, 'err')": (
                "telegraph('Settings load failed: ' + e.message + "
                "'. Reload the page and verify /api/settings is reachable.', 'err')"
            ),
            "telegraph('settings save failed: ' + e.message, 'err')": (
                "telegraph('Settings save failed: ' + e.message + "
                "'. Check authentication and field values, then retry.', 'err')"
            ),
            "telegraph('err: ' + e.message, 'err')": (
                "telegraph('Command failed: ' + e.message + "
                "'. Check the command syntax and gateway logs, then retry.', 'err')"
            ),
        },
    )

    dashboard._VIEW_DASHBOARD = _replace_all(
        dashboard._VIEW_DASHBOARD,
        {
            ">CONTROL PLANE<": ">Control plane<",
            ">KEY METRICS<": ">Key metrics<",
            ">TUNNELS<": ">Tunnels<",
            ">START</button>": ">Start</button>",
            ">TOPOLOGY<": ">Topology<",
            ">LIVE TELEMETRY<": ">Live telemetry<",
            ">STREAM<": ">Stream<",
            ">BACKEND HEALTH<": ">Backend health<",
            ">RECENT CALLS<": ">Recent calls<",
        },
    )
    dashboard._VIEW_CATALOG = _replace_all(
        dashboard._VIEW_CATALOG,
        {
            ">SERVER CATALOG<": ">Server catalog<",
            ">REGISTRY<": ">Registry<",
        },
    )
    dashboard._VIEW_EVALS = _replace_all(
        dashboard._VIEW_EVALS,
        {
            ">TOOL PERFORMANCE<": ">Tool performance<",
            ">EVALUATION INDEX<": ">Evaluation index<",
            ">Avg Latency<": ">Avg latency<",
        },
    )
    dashboard._VIEW_DEPLOY = _replace_all(
        dashboard._VIEW_DEPLOY,
        {
            ">DEPLOYMENT CONFIGS<": ">Deployment configs<",
            ">DEPLOY MANIFEST<": ">Deploy manifest<",
        },
    )
    dashboard._VIEW_SETTINGS = _replace_all(
        dashboard._VIEW_SETTINGS,
        {
            ">SETTINGS<": ">Settings<",
            ">GATEWAY CONFIG<": ">Gateway config<",
            ">Auth Mode</label>": ">Auth mode</label>",
            ">Default Profile</label>": ">Default profile</label>",
            ">CORS Origins</label>": ">CORS origins</label>",
            ">Rate Limit / min</label>": ">Rate limit / min</label>",
            ">Storage Backend</label>": ">Storage backend</label>",
            ">Save Settings</button>": ">Save settings</button>",
        },
    )
    dashboard._HTML_SHELL_BOTTOM = _replace_all(
        dashboard._HTML_SHELL_BOTTOM,
        {
            ">Transport / Risk<": ">Transport / risk<",
            ">Launch Command<": ">Launch command<",
            'data-confirm-title="Enable Server"': 'data-confirm-title="Enable server"',
            'data-confirm-title="Disable Server"': 'data-confirm-title="Disable server"',
            'data-confirm-title="Save Credentials"': 'data-confirm-title="Save credentials"',
            'onclick="detailToggle(true)"': '',
            'onclick="detailToggle(false)"': '',
            '>Confirm</span>': '>Confirm action</span>',
            (
                'onclick="runConfirmed()">Confirm</button>'
            ): 'onclick="runConfirmed()">Continue</button>',
        },
    )
    dashboard._HTML = (
        dashboard._HTML_SHELL_TOP
        + dashboard._VIEW_DASHBOARD
        + dashboard._VIEW_CATALOG
        + dashboard._VIEW_EVALS
        + dashboard._VIEW_DEPLOY
        + dashboard._VIEW_SETTINGS
        + dashboard._HTML_SHELL_BOTTOM
    )


def _patch_api() -> None:
    import kater.api as api
    import kater.api.routes as api_routes
    import kater.api.server as api_server
    import kater.proxy as proxy_mod
    import kater.settings as settings_mod
    import kater.storage as storage
    import kater.telemetry as telemetry

    def events(req: Any) -> Any:
        try:
            limit = api_routes._parse_limit(req)
            since = api_routes._parse_since(req)
        except ValueError as exc:
            return api.Response.json(400, {"error": str(exc)})
        name = req.query1("name")
        success_raw = req.query1("success")
        rows = storage.query_events(limit=0, name=name or None, since=since)
        if success_raw is not None:
            wanted = success_raw.lower() == "true"
            rows = [row for row in rows if bool(row.get("success")) is wanted]
        rows = list(reversed(rows[-limit:]))
        result = []
        for index, row in enumerate(rows):
            result.append(
                {
                    "id": row.get("id", index + 1),
                    "type": row.get("type"),
                    "name": row.get("name"),
                    "timestamp": row.get("timestamp"),
                    "duration_ms": int(row.get("duration_ms") or 0),
                    "success": bool(row.get("success")),
                    "profile": row.get("profile"),
                    "metadata": row.get("metadata") or {},
                }
            )
        return api.Response.json(200, {"total": len(result), "events": result})

    def backends(
        _: Any,
        proxy_factory: Callable[[], Any] | None = None,
    ) -> Any:
        overview = telemetry.status_overview().get("servers", {})
        totals = {
            "enabled": overview.get("enabled", 0),
            "disabled": overview.get("disabled", 0),
            "configured": overview.get("configured", 0),
            "missing_env": overview.get("missing_env", 0),
        }
        settings = settings_mod.load_settings()
        per_server: dict[str, dict[str, bool]] = {}
        import kater.profiles as profiles

        for source in profiles.all_tool_sources():
            if source.transport == "native":
                continue
            env_present = all(os.environ.get(variable) for variable in source.env)
            per_server[source.name] = {
                "enabled": settings.is_server_enabled(source.name, default=True),
                "configured": bool(env_present),
                "missing_env": not env_present,
            }
        provider = proxy_factory or proxy_mod.get_proxy
        try:
            statuses = provider().statuses()
        except Exception as exc:
            api_server._log.exception("failed to collect backend statuses")
            return api.Response.json(
                503,
                {
                    "error": "backend_status_unavailable",
                    "message": "Backend status collection failed; check gateway logs and retry.",
                    "detail": str(exc),
                    "backends": [],
                    "servers": [],
                    "totals": totals,
                },
            )
        result = []
        for status in statuses:
            item = status.to_dict()
            extra = per_server.get(item["name"], {})
            item["enabled"] = extra.get("enabled")
            item["configured"] = extra.get("configured")
            item["missing_env"] = extra.get("missing_env")
            result.append(item)
        return api.Response.json(
            200,
            {"backends": result, "servers": result, "totals": totals},
        )

    def replace_route(method: str, pattern: str, handler: Callable[[Any], Any]) -> None:
        for index, route in enumerate(api.ROUTER._routes):
            if route.method == method and route.pattern == pattern:
                api.ROUTER._routes[index] = api.Route(
                    method=route.method,
                    pattern=route.pattern,
                    handler=handler,
                    public=route.public,
                    rate_limit=route.rate_limit,
                )
                return
        raise RuntimeError(f"route not found: {method} {pattern}")

    setattr(api, "_events", events)  # noqa: B010
    setattr(api, "_backends", backends)  # noqa: B010
    replace_route("GET", "/api/events", events)
    replace_route("GET", "/api/backends", backends)


def apply_review_fixes(dashboard: Any) -> None:
    if getattr(dashboard, "_PR81_REVIEW_FIXES_APPLIED", False):
        return
    _patch_dashboard(dashboard)
    _patch_api()
    dashboard._PR81_REVIEW_FIXES_APPLIED = True
