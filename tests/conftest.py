"""Shared pytest fixtures for the Kater test-suite.

Consolidates the near-identical autouse "clean state" fixtures that were
duplicated across ~10 test files. Resets the settings cache (so cached
KaterSettings cannot leak between tests), the storage/db cache, OAuth state,
the API rate-limiter, and the on-disk .kater/ working dir.

Test files that defined their own local ``clean_state``/``clean_oauth``
fixture still work — a local autouse fixture shadows this one — but most can
now drop the boilerplate entirely.
"""

from __future__ import annotations

import os

# Load optional private deployment extensions before Kater profile catalog import.
os.environ.setdefault("KATER_EXTENSIONS_MODULE", "tests.fixtures.private_extension")

import shutil
from pathlib import Path

import pytest

KATER_DIR = Path.cwd() / ".kater"


def _rmtree_robust(path: Path) -> None:
    import time
    import gc
    gc.collect()
    for _ in range(15):
        try:
            if path.exists():
                shutil.rmtree(path)
            return
        except PermissionError:
            time.sleep(0.05)
            gc.collect()
    if path.exists():
        shutil.rmtree(path)


@pytest.fixture(autouse=True)
def clean_kater_state():
    """Reset all module-global state before and after every test."""
    from kater import api as api_mod
    from kater.oauth import reset_state
    from kater.settings import invalidate_settings_cache
    from kater.storage import reset_db_cache

    reset_db_cache()
    reset_state()
    invalidate_settings_cache()
    api_mod._reset_rate_limiter()
    _rmtree_robust(KATER_DIR)
    yield
    reset_db_cache()
    reset_state()
    invalidate_settings_cache()
    api_mod._reset_rate_limiter()
    _rmtree_robust(KATER_DIR)

