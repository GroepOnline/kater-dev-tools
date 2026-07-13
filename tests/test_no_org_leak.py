from __future__ import annotations

import scripts.no_org_leak as nol

# Files/contents that must be rejected outside the allowlist.
LEAK_SAMPLES = {
    "src/kater/evil.py": "BASE = 'https://chefgroep.nl/x'",
    "src/kater/evil2.py": "owner = 'onlinechefgroep'",
    "src/kater/evil3.py": "DB = 'postgres://user:pass@host/db'",
}
# Files/contents that are allowed (attribution / audit docs).
CLEAN_SAMPLES = {
    "README.md": "OnlineChefGroep maintains Kater.",
    "docs/deploy-server.md": "Point DNS at chefgroep.online",
    "src/kater/ok.py": "print('hello kater')",
}


def test_scan_flags_leaks(tmp_path):
    targets = []
    for rel, body in LEAK_SAMPLES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        targets.append(str(p))
    errors = nol.scan(targets)
    assert len(errors) == len(LEAK_SAMPLES)
    assert all("leak" in e or "connection" in e for e in errors)


def test_scan_allows_attribution_and_clean(tmp_path):
    targets = []
    for rel, body in CLEAN_SAMPLES.items():
        p = tmp_path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        targets.append(str(p))
    assert nol.scan(targets) == []


def test_scan_ignores_directories(tmp_path):
    d = tmp_path / "src" / "kater"
    d.mkdir(parents=True)
    (d / "x.py").write_text("chefgroep.nl")
    assert nol.scan([str(d)]) == []
