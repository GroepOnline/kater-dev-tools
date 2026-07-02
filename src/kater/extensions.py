from __future__ import annotations

import importlib
import os
from typing import Any


def load_extensions_module() -> Any | None:
    """Load optional deployment extensions (private profiles, native tools, chains).

    Set ``KATER_EXTENSIONS_MODULE`` to a Python module path, for example
    ``your_package.extensions``. The module may export:

    - ``TOOL_SOURCES``: extra ``ToolSource`` entries
    - ``PRIVATE_PROFILES``: profile names hidden when ``KATER_PUBLIC=1``
    - ``NATIVE_TOOLS``: extra ``NativeTool`` entries for ``build_native_tools``
    - ``CHAINS``: extra ``ChainDefinition`` entries
    """
    name = os.environ.get("KATER_EXTENSIONS_MODULE", "").strip()
    if not name:
        return None
    return importlib.import_module(name)


def extension_attr(name: str, default: Any) -> Any:
    mod = load_extensions_module()
    if mod is None:
        return default
    return getattr(mod, name, default)
