# Browser lane providers

Kater’s browser lane is not a single browser. Pick a backend with
`KATER_BROWSER_PROVIDER`. Extra setup lives in `.env.example`.

## local (default)

Playwright Chromium runs in-process. Install with
`pip/uv install kater[browser]` and `playwright install chromium`.
Good for laptop demos and CI without an external browser service.

## cdp

Attach to an existing Chrome DevTools Protocol endpoint. Point
`KATER_BROWSER_CDP_URL` at Browserless, `chrome --remote-debugging-port=9222`,
or any CDP websocket/HTTP discovery URL. Kater does not launch Chrome; it
connects to whatever is already listening.

## steel / remote

Drive [Steel Browser OSS](https://github.com/steel-dev/steel-browser) over
REST plus CDP. Set `KATER_BROWSER_PROVIDER` to `steel` or `remote`, and set
`KATER_BROWSER_STEEL_URL` (and `KATER_BROWSER_STEEL_KEY` when the Steel API
requires auth). Kater creates a Steel session, uses the returned CDP URL, then
releases the session on close.

## Policy knobs

Domain allow/deny lists, private-network access, session caps, and
`evaluate` gating are shared across providers. See the browser section of
`.env.example`.
