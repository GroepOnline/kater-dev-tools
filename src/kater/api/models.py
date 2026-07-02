"""Request/Response dataclasses and route table — the data seam between
the stdlib HTTP server and application logic.

Every other api sub-module imports from here; this module has **no**
kater-internal imports so it can never create a circular dependency.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote_plus

# ── Request / Response ─────────────────────────────────────────────


@dataclass
class Request:
    method: str
    path: str
    query: dict[str, list[str]]
    headers: dict[str, str]
    raw_body: bytes
    client_ip: str
    base_url: str
    params: dict[str, str] = field(default_factory=dict)

    def query1(self, key: str, default: str | None = None) -> str | None:
        return self.query.get(key, [default])[0]

    def header(self, name: str) -> str | None:
        return self.headers.get(name.lower())

    @property
    def json(self) -> dict[str, Any]:
        if not self.raw_body:
            return {}
        try:
            return json.loads(self.raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            raise ValueError("Invalid JSON in request body") from None

    @property
    def form(self) -> dict[str, str]:
        out: dict[str, str] = {}
        try:
            body_str = self.raw_body.decode("utf-8")
        except UnicodeDecodeError:
            raise ValueError("Request body is not valid UTF-8") from None
        for pair in body_str.split("&"):
            if "=" in pair:
                k, v = pair.split("=", 1)
                # unquote_plus converts '+' to space, which unquote does not —
                # a verifier/code containing '+' would otherwise be misparsed.
                out[unquote_plus(k)] = unquote_plus(v)
        return out

    @property
    def json_or_form(self) -> dict[str, Any]:
        ctype = self.header("content-type") or ""
        return self.json if ctype.startswith("application/json") else self.form


@dataclass
class Response:
    status: int = 200
    payload: dict[str, Any] | None = None
    body: bytes | None = None
    content_type: str = "application/json; charset=utf-8"
    headers: dict[str, str] = field(default_factory=dict)

    @classmethod
    def json(cls, status: int, payload: dict[str, Any]) -> Response:
        return cls(status=status, payload=payload)

    @classmethod
    def html(cls, status: int, markup: str) -> Response:
        return cls(
            status=status,
            body=markup.encode("utf-8"),
            content_type="text/html; charset=utf-8",
        )

    @classmethod
    def redirect(cls, location: str) -> Response:
        return cls(status=302, body=b"", content_type="text/plain", headers={"Location": location})

    def encoded(self) -> bytes:
        if self.body is not None:
            return self.body
        return json.dumps(self.payload, ensure_ascii=False, indent=2).encode("utf-8")


# ── Route table ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Route:
    method: str
    pattern: str
    handler: Callable[[Request], Response]
    public: bool = False
    rate_limit: bool = True


def _segments(path: str) -> list[str]:
    stripped = path.strip("/")
    return stripped.split("/") if stripped else []


class RouteTable:
    def __init__(self) -> None:
        self._routes: list[Route] = []

    def add(self, route: Route) -> None:
        self._routes.append(route)

    def match(self, method: str, path: str) -> tuple[Route, dict[str, str]] | None:
        target = _segments(path)
        exact: tuple[Route, dict[str, str]] | None = None
        # Among parameterized matches, prefer the most specific one: the route
        # with the fewest param segments wins, so a literal like
        # /servers/{name}/credentials beats the generic /servers/{name}/{action}.
        best_param: tuple[Route, dict[str, str]] | None = None
        best_param_count: int | None = None
        for route in self._routes:
            if route.method != method:
                continue
            pat = _segments(route.pattern)
            if len(pat) != len(target):
                continue
            captured: dict[str, str] = {}
            ok = True
            param_count = 0
            for p, t in zip(pat, target, strict=True):
                if p.startswith("{") and p.endswith("}"):
                    captured[p[1:-1]] = t
                    param_count += 1
                elif p != t:
                    ok = False
                    break
            if not ok:
                continue
            if param_count == 0:
                exact = (route, captured)
            elif best_param_count is None or param_count < best_param_count:
                best_param = (route, captured)
                best_param_count = param_count
        return exact or best_param


ROUTER = RouteTable()


def route(method: str, pattern: str, *, public: bool = False) -> Callable[..., Any]:
    def decorator(func: Callable[[Request], Response]) -> Callable[[Request], Response]:
        ROUTER.add(Route(method, pattern, func, public=public))
        return func

    return decorator
