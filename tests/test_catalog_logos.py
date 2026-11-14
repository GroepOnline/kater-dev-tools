from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import generate_catalog_logos as gcl  # noqa: E402

INITIALS_PATTERN = re.compile(r"<text[^>]*>(?P<text>[^<]+)</text>", re.DOTALL)


def _run_main(out_dir: Path) -> int:
    return gcl.main(["--out", str(out_dir)])


def test_logos_generated(tmp_path: Path) -> None:
    out = tmp_path / "logos"
    rc = _run_main(out)
    assert rc == 0
    svgs = sorted(out.glob("*.svg"))
    assert len(svgs) >= 28, f"expected >=28 SVG files, got {len(svgs)}"
    for svg in svgs:
        head = svg.read_text(encoding="utf-8")[:64].lstrip()
        assert head.startswith("<svg") or head.startswith("<?xml"), (
            f"{svg.name} did not start with svg/xml declaration: {head!r}"
        )


def test_logos_deterministic(tmp_path: Path) -> None:
    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    assert _run_main(out_a) == 0
    assert _run_main(out_b) == 0
    files_a = sorted(out_a.glob("*.svg"))
    files_b = sorted(out_b.glob("*.svg"))
    assert [p.name for p in files_a] == [p.name for p in files_b]
    for a, b in zip(files_a, files_b, strict=True):
        assert a.read_bytes() == b.read_bytes(), f"non-deterministic: {a.name}"


def test_logos_have_gradient(tmp_path: Path) -> None:
    out = tmp_path / "logos"
    assert _run_main(out) == 0
    sample = out / "github.svg"
    assert sample.exists()
    import xml.etree.ElementTree as ET

    # Files are produced by our own deterministic SVG generator, not untrusted input.
    tree = ET.parse(sample)  # noqa: S314
    root = tree.getroot()
    assert root.tag.endswith("svg"), f"root tag was {root.tag!r}"
    assert root.get("viewBox") == "0 0 64 64"
    ns = {"svg": gcl.SVG_NS}
    grads = root.findall("svg:defs/svg:linearGradient", ns)
    assert grads, "no linearGradient element found"
    stops = grads[0].findall("svg:stop", ns)
    assert len(stops) >= 2
    colors = [s.get("stop-color") for s in stops]
    assert all(colors)


def test_logos_match_category(tmp_path: Path) -> None:
    out = tmp_path / "logos"
    assert _run_main(out) == 0
    figma_svg = (out / "figma.svg").read_text(encoding="utf-8")
    github_svg = (out / "github.svg").read_text(encoding="utf-8")
    prod = gcl.CATEGORY_GRADIENTS[gcl.Category.PRODUCTIVITY]
    dev = gcl.CATEGORY_GRADIENTS[gcl.Category.DEV]
    assert any(c.lower() in figma_svg.lower() for c in prod), (
        f"figma.svg missing productivity gradient stops {prod}: {figma_svg!r}"
    )
    assert any(c.lower() in github_svg.lower() for c in dev), (
        f"github.svg missing dev gradient stops {dev}: {github_svg!r}"
    )


def test_initials_handles_compound_names() -> None:
    assert gcl.initials("github") == "G"
    assert gcl.initials("brave-search") == "BS"
    assert gcl.initials("sequential-thinking") == "ST"
    assert gcl.initials("notion") == "N"
    assert gcl.initials("a-b-c-d") == "AB"
    assert gcl.initials("") == "?"


def test_logo_url_serves_end_to_end() -> None:
    from kater.authgate import _is_public_path
    from kater.profiles import visible_tool_sources

    served = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "kater"
        / "web"
        / "studio_dist"
        / "assets"
        / "logos"
    )
    src = next(s for s in visible_tool_sources() if s.name == "github")
    assert src.logo_url == "/studio/assets/logos/github.svg", (
        f"got {src.logo_url}"
    )
    assert (served / "github.svg").exists(), (
        f"missing {served / 'github.svg'}"
    )
    assert _is_public_path("/studio/assets/logos/github.svg") is True


def test_logo_http_serves() -> None:
    from tests.test_studio_serving import _get

    resp = _get("/studio/assets/logos/github.svg")
    assert resp.status == 200
    body = resp.encoded()
    assert b"<svg" in body
    assert "image/svg+xml" in (resp.content_type or "")


def test_logo_route_rejects_traversal() -> None:
    from tests.test_studio_serving import _get

    for bad in ("../settings.json", "foo/bar.svg", "..svg", "foo\\bar.svg"):
        matched = _get.__globals__["ROUTER"].match(
            "GET", f"/studio/assets/logos/{bad}"
        )
        if matched is None:
            continue
        route, params = matched
        from kater.api import Request

        request = Request(
            method="GET",
            path=f"/studio/assets/logos/{bad}",
            query={},
            headers={},
            raw_body=b"",
            client_ip="127.0.0.1",
            base_url="http://127.0.0.1:9091",
            params={"name": bad},
        )
        resp = route.handler(request)
        assert resp.status == 400, (
            f"name {bad!r} should be rejected, got {resp.status}"
        )
        assert b"invalid logo name" in resp.encoded()