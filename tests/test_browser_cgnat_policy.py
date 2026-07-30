from __future__ import annotations

import pytest

from kater.browser.policy import BrowserPolicy, PolicyViolation


@pytest.mark.parametrize(
    "address",
    [
        "100.64.0.0",
        "100.64.1.1",
        "100.127.255.255",
        "::ffff:100.64.1.1",
    ],
)
def test_cgnat_addresses_are_rejected(address: str) -> None:
    with pytest.raises(PolicyViolation, match="non-public address"):
        BrowserPolicy().check_url(f"http://[{address}]/" if ":" in address else f"http://{address}/")


@pytest.mark.parametrize("address", ["100.63.255.255", "100.128.0.0"])
def test_addresses_outside_cgnat_range_remain_public(address: str) -> None:
    BrowserPolicy().check_url(f"http://{address}/")
