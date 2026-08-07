# web/ — single-file dashboard

## OVERVIEW
`render_dashboard(ws_port)` returns one HTML string: inline `_CSS` (L3–1010) + `_HTML` (L1012) + `_JS` (L1023–2439, vanilla SPA: constellation canvas, Ctrl+K command bar, WS client). Only Python fn is render_dashboard (L2442).

## WHERE TO LOOK
| Task | Location |
|------|----------|
| Change CSS | _CSS constant |
| Change markup | _HTML constant |
| Change JS/app logic | _JS constant |
| Change ws_port sync | render_dashboard injection |

## CONVENTIONS
- Served only by `GET /` and `/dashboard` in api/routes.py (sole caller).
- `window.KATER_CONFIG={wsPort}` injected at bottom so client matches runtime WS bind.
- Semantic `.btn-action.danger` — never decorative.

## ANTI-PATTERNS
- Don't add a build step / separate frontend repo — this is intentionally inline.
- Don't realign positions against the 600x400 fallback (known limitation, ~L1330).
