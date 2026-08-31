from __future__ import annotations

from kater.api import ROUTER, Request


def _get(path: str):
    matched = ROUTER.match("GET", path)
    assert matched is not None, f"missing GET route: {path}"
    route, params = matched
    request = Request(
        method="GET",
        path=path,
        query={},
        headers={},
        raw_body=b"",
        client_ip="127.0.0.1",
        base_url="http://127.0.0.1:9091",
        params=params,
    )
    return route.handler(request)


def test_studio_shell_is_served_from_python_runtime() -> None:
    response = _get("/studio")
    assert response.status == 200
    assert response.content_type.startswith("text/html")
    body = response.encoded().decode("utf-8")
    assert '<div id="root"></div>' in body
    assert '/studio/assets/studio.js' in body
    assert '/studio/assets/studio.css' in body


def test_studio_assets_have_explicit_content_types() -> None:
    js = _get("/studio/assets/studio.js")
    css = _get("/studio/assets/studio.css")
    assert js.status == 200
    assert js.content_type.startswith("text/javascript")
    assert b"React" in js.encoded() or b"createElement" in js.encoded()
    assert css.status == 200
    assert css.content_type.startswith("text/css")
    assert b"--accent" in css.encoded()


def test_dashboard_remains_the_existing_fallback() -> None:
    response = _get("/dashboard")
    assert response.status == 200
    body = response.encoded().decode("utf-8")
    assert 'id="catalog-search"' in body
    assert '/studio/assets/studio.js' not in body


def test_unknown_studio_asset_has_no_route() -> None:
    assert ROUTER.match("GET", "/studio/assets/../../settings.json") is None
    assert ROUTER.match("GET", "/studio/assets/unknown.js") is None
