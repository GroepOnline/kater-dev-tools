from __future__ import annotations

import subprocess
from types import SimpleNamespace
from typing import Any

from kater.github_transport import (
    ERROR_AUTH_PERMANENT,
    ERROR_NOT_FOUND,
    ERROR_TIMEOUT,
    ERROR_TRANSIENT_NETWORK,
    GitHubTransportError,
    TransportConfig,
    classify_github_failure,
    github_error_payload,
    github_token_identity,
    run_github_command,
)
from kater.pr_control import _run_gh

GRAPHQL_DIAL_TIMEOUT = "Post https://api.github.com/graphql: dial tcp 4.225.11.201:443: i/o timeout"


def test_classify_exact_graphql_dial_timeout() -> None:
    err = classify_github_failure(
        args=["pr", "view", "42"],
        returncode=1,
        stderr=GRAPHQL_DIAL_TIMEOUT,
    )
    assert err.error_class == ERROR_TRANSIENT_NETWORK
    assert err.retryable is True
    assert err.transport == "graphql"
    assert "ghp_" not in str(err)


def test_run_gh_timeout_expired_classified(monkeypatch) -> None:
    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise subprocess.TimeoutExpired(cmd=["gh", "pr", "view", "1"], timeout=2)

    monkeypatch.setattr(subprocess, "run", boom)
    try:
        _run_gh(["pr", "view", "1"])
    except subprocess.TimeoutExpired:
        pass
    else:
        raise AssertionError("expected TimeoutExpired")

    err = classify_github_failure(args=["pr", "view", "1"], timeout=True)
    assert err.error_class == ERROR_TIMEOUT
    assert err.retryable is True


def test_run_github_command_classifies_timeout_expired() -> None:
    def invoke(_args: list[str]) -> Any:
        raise subprocess.TimeoutExpired(cmd=["gh"], timeout=2)

    cfg = TransportConfig(extra_retries=0, sleeper=lambda _: None, rng=lambda: 0.5)
    try:
        run_github_command(["pr", "view", "1"], invoke=invoke, config=cfg)
    except GitHubTransportError as exc:
        assert exc.error_class == ERROR_TIMEOUT
        assert exc.retryable is True
        assert exc.attempts == 1
    else:
        raise AssertionError("expected GitHubTransportError")


def test_read_retries_transient_then_succeeds() -> None:
    calls = {"n": 0}

    def invoke(args: list[str]) -> Any:
        calls["n"] += 1
        if calls["n"] < 3:
            return SimpleNamespace(returncode=1, stdout="", stderr=GRAPHQL_DIAL_TIMEOUT)
        return SimpleNamespace(returncode=0, stdout='{"ok":true}', stderr="")

    sleeps: list[float] = []
    cfg = TransportConfig(
        extra_retries=2,
        backoff_base_sec=0.2,
        sleeper=sleeps.append,
        rng=lambda: 0.5,
    )
    proc = run_github_command(["pr", "view", "1"], invoke=invoke, config=cfg)
    assert proc.returncode == 0
    assert calls["n"] == 3
    assert sleeps == [0.2, 0.4]


def test_retry_exhaustion_raises_no_pass() -> None:
    def invoke(_args: list[str]) -> Any:
        return SimpleNamespace(returncode=1, stdout="", stderr=GRAPHQL_DIAL_TIMEOUT)

    cfg = TransportConfig(extra_retries=2, sleeper=lambda _: None, rng=lambda: 0.5)
    try:
        run_github_command(["api", "graphql"], invoke=invoke, config=cfg)
    except GitHubTransportError as exc:
        assert exc.retryable is True
        assert exc.attempts == 3
        payload = exc.as_dict()
        assert payload["ok"] is False
        assert payload["error_class"] == ERROR_TRANSIENT_NETWORK
    else:
        raise AssertionError("expected GitHubTransportError")


def test_permanent_auth_is_not_retried() -> None:
    calls = {"n": 0}

    def invoke(_args: list[str]) -> Any:
        calls["n"] += 1
        return SimpleNamespace(returncode=1, stdout="", stderr="HTTP 401: Bad credentials")

    cfg = TransportConfig(extra_retries=3, sleeper=lambda _: None)
    try:
        run_github_command(["api", "repos/o/r/pulls/1"], invoke=invoke, config=cfg)
    except GitHubTransportError as exc:
        assert exc.error_class == ERROR_AUTH_PERMANENT
        assert exc.retryable is False
    else:
        raise AssertionError("expected GitHubTransportError")
    assert calls["n"] == 1


def test_write_is_never_retried() -> None:
    calls = {"n": 0}

    def invoke(_args: list[str]) -> Any:
        calls["n"] += 1
        return SimpleNamespace(returncode=1, stdout="", stderr=GRAPHQL_DIAL_TIMEOUT)

    cfg = TransportConfig(extra_retries=4, sleeper=lambda _: None)
    try:
        run_github_command(["pr", "merge", "1"], invoke=invoke, mutate=True, config=cfg)
    except GitHubTransportError:
        pass
    else:
        raise AssertionError("expected GitHubTransportError")
    assert calls["n"] == 1


def test_not_found_is_distinct() -> None:
    err = classify_github_failure(
        args=["api", "repos/o/r/branches/main/protection"],
        returncode=1,
        stderr="HTTP 404: Not Found",
    )
    assert err.error_class == ERROR_NOT_FOUND
    assert err.is_not_found is True
    assert err.retryable is False


def test_redacts_tokens_from_errors_and_payload(monkeypatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "ghp_abcdefghijklmnopqrstuvwxyz0123456789")
    err = classify_github_failure(
        args=["pr", "view", "1"],
        returncode=1,
        stderr="boom ghp_abcdefghijklmnopqrstuvwxyz0123456789 github_pat_abc",
    )
    text = str(err)
    payload = github_error_payload(err)
    blob = str(payload)
    assert "ghp_" not in text
    assert "github_pat_" not in text
    assert "ghp_" not in blob
    assert payload["ok"] is False
    assert payload["identity"]["token_env"] == "GH_TOKEN"
    assert payload["identity"]["fingerprint"]
    assert "ghp_" not in str(payload["identity"]["fingerprint"])


def test_poison_gh_token_wins_over_pat(monkeypatch) -> None:
    monkeypatch.setenv("GH_TOKEN", "keep-me")
    monkeypatch.setenv("GITHUB_PERSONAL_ACCESS_TOKEN", "ignored-pat-value")
    ident = github_token_identity()
    assert ident["token_env"] == "GH_TOKEN"
    assert "ignored-pat-value" not in str(ident)
    assert "GH_TOKEN wins" in ident["precedence"]
