from __future__ import annotations

from kater.extensions import extension_attr, load_extensions_module


def test_load_extensions_module_returns_none_when_no_env(monkeypatch) -> None:
    """When KATER_EXTENSIONS_MODULE is not set, load returns None."""
    monkeypatch.delenv("KATER_EXTENSIONS_MODULE", raising=False)
    assert load_extensions_module() is None


def test_load_extensions_module_imports_when_set(monkeypatch) -> None:
    """When KATER_EXTENSIONS_MODULE is set to a real module, it is imported."""
    monkeypatch.setenv("KATER_EXTENSIONS_MODULE", "tests.fixtures.private_extension")
    mod = load_extensions_module()
    assert mod is not None
    # The private_extension fixture exports PRIVATE_PROFILES
    assert hasattr(mod, "PRIVATE_PROFILES")


def test_extension_attr_returns_default_when_no_module() -> None:
    """extension_attr returns the default when no extension module is loaded."""
    result = extension_attr("NONEXISTENT", [])
    assert result == []


def test_extension_attr_returns_attribute_when_set(monkeypatch) -> None:
    """extension_attr returns the attribute from the extension module when loaded."""
    monkeypatch.setenv("KATER_EXTENSIONS_MODULE", "tests.fixtures.private_extension")
    profiles = extension_attr("PRIVATE_PROFILES", [])
    # private_extension fixture defines PRIVATE_PROFILES = {"demo_private"}
    assert isinstance(profiles, frozenset)
    assert "demo_private" in profiles


def test_extension_attr_falls_back_to_default_for_missing_attr(monkeypatch) -> None:
    """extension_attr returns default when attr is missing from the module."""
    monkeypatch.setenv("KATER_EXTENSIONS_MODULE", "tests.fixtures.private_extension")
    result = extension_attr("UNDEFINED_ATTR_XYZ", "fallback-value")
    assert result == "fallback-value"
