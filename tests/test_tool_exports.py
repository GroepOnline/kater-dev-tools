from __future__ import annotations

import json
import time
from dataclasses import replace

import pytest
from jsonschema import Draft202012Validator

from kater.mcp.tool_exports import (
    InvalidToolArguments,
    ProductExportsDisabled,
    ProductToolRegistry,
    ToolNotExported,
)
from kater.resource_auth import (
    InsufficientScope,
    InvalidToken,
    ResourceAuthConfig,
    ResourceAuthDisabled,
    parse_introspection,
)

SCOPES = {
    "kater_status": "kater:read",
    "kater_tool_search": "kater:read",
    "brain_query": "brain:read",
    "brain_doctor": "brain:read",
    "chefshare_list": "chefshare:read",
    "chefshare_meta": "chefshare:read",
}
ARGUMENTS = {
    "kater_status": {},
    "kater_tool_search": {"query": "read"},
    "brain_query": {"query": "project history"},
    "brain_doctor": {},
    "chefshare_list": {},
    "chefshare_meta": {"item_id": "share-123"},
}


@pytest.fixture
def auth():
    return ResourceAuthConfig(
        enabled=True,
        issuer="https://auth.example.test",
        resource="https://tools.example.test/mcp",
        allowed_scopes=tuple(sorted(set(SCOPES.values()))),
    )


@pytest.fixture
def principal(auth):
    # Use the actual introspection parser, not a permissive auth mock.
    return parse_introspection(
        {
            "active": True,
            "sub": "account-123",
            "plane": "internal",
            "scope": " ".join(auth.allowed_scopes),
            "aud": auth.resource,
            "exp": int(time.time()) + 300,
        },
        config=auth,
        required_scopes=frozenset(auth.allowed_scopes),
    )


@pytest.fixture
def registry(auth):
    return ProductToolRegistry(auth=auth, enabled=True)


def paths(registry, principal):
    return (
        lambda: registry.list_tools(principal=principal),
        lambda: registry.search_tools({"query": "read"}, principal=principal),
        lambda: registry.call_tool("kater_status", {}, principal=principal),
    )


def test_product_exports_require_explicit_enable(auth, principal):
    for registry in (ProductToolRegistry(), ProductToolRegistry(auth=auth)):
        for operation in paths(registry, principal):
            with pytest.raises(ProductExportsDisabled):
                operation()


def test_resource_auth_cannot_be_bypassed(principal):
    registry = ProductToolRegistry(enabled=True)
    for operation in paths(registry, principal):
        with pytest.raises(ResourceAuthDisabled):
            operation()


def test_exact_descriptor_contract(registry, principal):
    descriptors = registry.list_tools(principal=principal)
    assert {tool.name for tool in descriptors} == SCOPES.keys()
    assert len(descriptors) == 6
    for descriptor in descriptors:
        tool = descriptor.model_dump(by_alias=True, exclude_none=True)
        security = [{"type": "oauth2", "scopes": [SCOPES[tool["name"]]]}]
        assert tool["securitySchemes"] == security
        assert tool["_meta"]["securitySchemes"] == security
        assert tool["annotations"] == {
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
        }
        assert tool["inputSchema"]["additionalProperties"] is False
        Draft202012Validator.check_schema(tool["inputSchema"])
        Draft202012Validator(tool["inputSchema"]).validate(ARGUMENTS[tool["name"]])


@pytest.mark.parametrize("scope", sorted(set(SCOPES.values())))
def test_same_scope_allowlist_for_list_search_and_calls(registry, principal, scope):
    principal = replace(principal, scopes=frozenset({scope}))
    expected = {name for name, required in SCOPES.items() if required == scope}
    assert {tool.name for tool in registry.list_tools(principal=principal)} == expected
    assert {
        tool.name for tool in registry.search_tools({"query": "read"}, principal=principal)
    } == expected
    for name in SCOPES:
        if name in expected:
            registry.call_tool(name, ARGUMENTS[name], principal=principal)
        else:
            with pytest.raises(InsufficientScope):
                registry.call_tool(name, ARGUMENTS[name], principal=principal)


def test_no_scopes_discloses_no_tools(registry, principal):
    principal = replace(principal, scopes=frozenset())
    assert registry.list_tools(principal=principal) == []
    assert registry.search_tools({"query": "read"}, principal=principal) == []
    for name in SCOPES:
        with pytest.raises(InsufficientScope):
            registry.call_tool(name, ARGUMENTS[name], principal=principal)


@pytest.mark.parametrize(
    "change",
    [
        {"issuer": "https://untrusted.example.test"},
        {"audience": "https://another.example.test/mcp"},
        {"plane": "public"},
        {"expires_at": 0},
        {"scopes": frozenset({"admin:write"})},
    ],
)
def test_principal_contract_is_checked_on_every_path(registry, principal, change):
    for operation in paths(registry, replace(principal, **change)):
        with pytest.raises(InvalidToken):
            operation()


@pytest.mark.parametrize("principal", [None, {}, {"scopes": ["kater:read"]}])
def test_no_anonymous_or_caller_dict_principal(registry, principal):
    for operation in paths(registry, principal):
        with pytest.raises(InvalidToken):
            operation()


def test_principal_expiry_rechecked_without_caching(registry, principal, monkeypatch):
    assert registry.list_tools(principal=principal)
    monkeypatch.setattr("kater.mcp.tool_exports.time.time", lambda: principal.expires_at)
    for operation in paths(registry, principal):
        with pytest.raises(InvalidToken):
            operation()


@pytest.mark.parametrize(
    "name",
    ["brain__query", "chefshare__meta", "kater__status", "kater_execute", "kater_pr_merge", ""],
)
def test_unknown_and_backend_names_never_dispatch(registry, principal, name):
    with pytest.raises(ToolNotExported):
        registry.call_tool(name, {}, principal=principal)
    assert registry.search_tools({"query": name or "missing"}, principal=principal) == []


@pytest.mark.parametrize("name", SCOPES)
@pytest.mark.parametrize("extra", ["profile", "principal", "principal_id", "backend_url", "token"])
def test_caller_authority_and_routing_arguments_are_rejected(registry, principal, name, extra):
    args = {**ARGUMENTS[name], extra: "DO-NOT-ECHO"}
    with pytest.raises(InvalidToolArguments) as error:
        registry.call_tool(name, args, principal=principal)
    assert "DO-NOT-ECHO" not in str(error.value)
    descriptor = next(
        tool for tool in registry.list_tools(principal=principal) if tool.name == name
    )
    assert not Draft202012Validator(descriptor.input_schema).is_valid(args)


@pytest.mark.parametrize(
    "name,args",
    [
        ("kater_status", None),
        ("kater_status", []),
        ("kater_tool_search", {}),
        ("kater_tool_search", {"query": ""}),
        ("kater_tool_search", {"query": "   "}),
        ("kater_tool_search", {"query": 1}),
        ("kater_tool_search", {"query": "read", "limit": True}),
        ("kater_tool_search", {"query": "read", "limit": "2"}),
        ("kater_tool_search", {"query": "read", "limit": 0}),
        ("kater_tool_search", {"query": "read", "limit": 26}),
        ("brain_query", {"query": "x" * 4097}),
        ("brain_query", {"query": None}),
        ("brain_doctor", {"fix": True}),
        ("chefshare_list", {"limit": -1}),
        ("chefshare_meta", {}),
        ("chefshare_meta", {"item_id": "https://example.test/secret"}),
        ("chefshare_meta", {"item_id": "../secret"}),
    ],
)
def test_strict_input_validation(registry, principal, name, args):
    with pytest.raises(InvalidToolArguments):
        registry.call_tool(name, args, principal=principal)


def test_search_input_is_strict_on_direct_path(registry, principal):
    with pytest.raises(InvalidToolArguments):
        registry.search_tools({"query": "read", "profile": "core"}, principal=principal)


def test_search_tool_uses_only_authorized_product_descriptors(registry, principal):
    principal = replace(principal, scopes=frozenset({"kater:read"}))
    result = registry.call_tool("kater_tool_search", {"query": "READ"}, principal=principal)
    assert result.is_error is False
    assert result.structured_content == {
        "tools": [
            tool.model_dump(mode="json", by_alias=True, exclude_none=True)
            for tool in registry.search_tools({"query": "READ"}, principal=principal)
        ]
    }
    assert {tool["name"] for tool in result.structured_content["tools"]} == {
        "kater_status",
        "kater_tool_search",
    }
    assert len(registry.search_tools({"query": "read", "limit": 1}, principal=principal)) == 1


@pytest.mark.parametrize("name", [name for name in SCOPES if name != "kater_tool_search"])
def test_backend_calls_report_typed_unavailable_without_claiming_success(registry, principal, name):
    result = registry.call_tool(name, ARGUMENTS[name], principal=principal)
    assert result.is_error is True
    assert result.structured_content == {
        "status": "unavailable",
        "code": "backend_unavailable",
        "tool": name,
    }
    assert json.loads(result.content[0].text) == result.structured_content


def test_descriptor_mutation_cannot_change_allowlist_or_scope(registry, principal):
    descriptor = registry.list_tools(principal=principal)[0]
    descriptor.name = "kater_execute"
    descriptor.input_schema["additionalProperties"] = True
    descriptor.meta["securitySchemes"][0]["scopes"] = []
    assert {tool.name for tool in registry.list_tools(principal=principal)} == SCOPES.keys()
    test_exact_descriptor_contract(registry, principal)


def test_generic_discovery_and_backend_dispatch_are_never_used(registry, principal, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("Product export must not consult core tools, profiles, extensions or backends")

    monkeypatch.setattr("kater.registry.tools_for_profile", forbidden)
    monkeypatch.setattr("kater.executor.search_tools", forbidden)
    monkeypatch.setattr("kater.executor.execute", forbidden)
    monkeypatch.setattr("kater.extensions.load_extensions_module", forbidden)
    monkeypatch.setattr("kater.proxy.get_proxy", forbidden)
    assert len(registry.list_tools(principal=principal)) == 6
    assert len(registry.search_tools({"query": "read"}, principal=principal)) == 6
    for name in SCOPES:
        registry.call_tool(name, ARGUMENTS[name], principal=principal)


def test_default_registry_ignores_enable_environment(auth, principal, monkeypatch):
    monkeypatch.setenv("KATER_PRODUCT_EXPORTS_ENABLED", "1")
    monkeypatch.setenv("KATER_EXTENSIONS_MODULE", "kater.chefgroep_extension")
    registry = ProductToolRegistry(auth=auth)
    for operation in paths(registry, principal):
        with pytest.raises(ProductExportsDisabled):
            operation()


def test_narrow_resource_contract_cannot_authorize_other_product_scopes(auth, principal):
    narrow = auth.model_copy(update={"allowed_scopes": ("kater:read",)})
    registry = ProductToolRegistry(auth=narrow, enabled=True)
    for operation in paths(registry, principal):
        with pytest.raises(InvalidToken):
            operation()
    principal = replace(principal, scopes=frozenset({"kater:read"}))
    assert {tool.name for tool in registry.list_tools(principal=principal)} == {
        "kater_status",
        "kater_tool_search",
    }


def test_authorization_precedes_bad_arguments_and_unknown_names(registry, principal):
    with pytest.raises(InvalidToken):
        registry.call_tool("private__tool", {"token": "DO-NOT-ECHO"}, principal=None)
    with pytest.raises(InsufficientScope):
        registry.call_tool(
            "brain_query",
            {"profile": "DO-NOT-ECHO"},
            principal=replace(principal, scopes=frozenset({"kater:read"})),
        )
    with pytest.raises(InvalidToken):
        registry.search_tools(None, principal=None)


def test_invalid_clock_fails_closed(registry, principal, monkeypatch):
    from kater.resource_auth import AuthUnavailable

    monkeypatch.setattr("kater.mcp.tool_exports.time.time", lambda: float("nan"))
    for operation in paths(registry, principal):
        with pytest.raises(AuthUnavailable):
            operation()
