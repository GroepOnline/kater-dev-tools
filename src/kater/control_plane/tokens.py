"""HMAC-signed, short-lived tokens bound to remote contexts.

Token format: ``base64url(payload).base64url(hmac_sha256)`` where payload is
JSON ``{ctx, principal, scopes, exp, iat, v:1}``. The store remains
authoritative for revocation, expiry, scopes and capability allowlists.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from typing import Any

from kater.control_plane.contexts import ContextRecord, get_context
from kater.settings import load_settings

_TOKEN_VERSION = 1
_process_secret: bytes | None = None
_derived_secret: bytes | None = None
_secret_lock = threading.Lock()

# Parameters for deriving the fallback signing key from a configured API key.
# The API key is high-entropy input, but we still run it through PBKDF2-HMAC-
# SHA256 (a deliberately expensive KDF) instead of a bare SHA-256: this keeps
# the derived key stable across restarts while staying off the "fast hash over a
# credential" path that static analysis flags. Fixed salt/iterations keep the
# output deterministic; the derived key is cached per process (see below).
_CONTEXT_TOKEN_KDF_SALT = b"kater-context-token-hkdf-salt-v1"
_CONTEXT_TOKEN_KDF_ITERATIONS = 200_000


def reset_token_secret_cache() -> None:
    """Drop the cached fallback signing secrets (tests)."""
    global _process_secret, _derived_secret
    with _secret_lock:
        _process_secret = None
        _derived_secret = None


def _b64url_encode(raw: bytes) -> str:
    """Encode bytes as an unpadded Base64URL string."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(text: str) -> bytes | None:
    """
    Decode a Base64url-encoded string.
    
    Parameters:
        text (str): The encoded text.
    
    Returns:
        bytes | None: The decoded bytes, or `None` if the text is invalid.
    """
    padded = text + "=" * (-len(text) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (ValueError, UnicodeEncodeError):
        return None


def _token_secret() -> bytes:
    """
    Resolve the HMAC signing key for context tokens.
    
    The key is selected from the configured environment secret, the first configured API key, or a random process-local secret.
    """
    global _process_secret, _derived_secret
    env = os.environ.get("KATER_CONTEXT_TOKEN_SECRET", "").strip()
    if env:
        return env.encode("utf-8")
    try:
        keys = list(load_settings().auth.api_keys)
    except Exception:  # pragma: no cover - settings should always load
        keys = []
    if keys:
        with _secret_lock:
            if _derived_secret is None:
                _derived_secret = hashlib.pbkdf2_hmac(
                    "sha256",
                    keys[0].encode("utf-8"),
                    _CONTEXT_TOKEN_KDF_SALT,
                    _CONTEXT_TOKEN_KDF_ITERATIONS,
                    dklen=32,
                )
            return _derived_secret
    with _secret_lock:
        if _process_secret is None:
            _process_secret = secrets.token_bytes(32)
        return _process_secret


def _sign(payload_b64: str) -> str:
    """Create a base64url-encoded HMAC-SHA256 signature for an encoded token payload.
    
    Parameters:
    	payload_b64 (str): Base64url-encoded token payload.
    
    Returns:
    	str: Base64url-encoded HMAC-SHA256 signature.
    """
    digest = hmac.new(_token_secret(), payload_b64.encode("ascii"), hashlib.sha256).digest()
    return _b64url_encode(digest)


def issue_token(record: ContextRecord, *, ttl_seconds: int = 3600) -> str:
    """
    Issue a signed token for an active context.
    
    Parameters:
    	record (ContextRecord): The context record to encode in the token.
    	ttl_seconds (int): The requested token lifetime in seconds.
    
    Returns:
    	str: A signed token containing the context, principal, scopes, and expiration.
    
    Raises:
    	ValueError: If the context is inactive or expired, or the requested lifetime is not positive.
    """
    if not record.is_active():
        raise ValueError("context is not active")
    ttl = int(ttl_seconds)
    if ttl <= 0:
        raise ValueError("ttl_seconds must be positive")
    now = int(time.time())
    exp = now + ttl
    if record.expires_at is not None:
        ctx_exp = int(record.expires_at.timestamp())
        if ctx_exp <= now:
            raise ValueError("context is expired")
        exp = min(exp, ctx_exp)
    payload: dict[str, Any] = {
        "ctx": record.context_id,
        "principal": record.principal_id,
        "scopes": sorted(record.scopes),
        "exp": exp,
        "iat": now,
        "v": _TOKEN_VERSION,
    }
    payload_b64 = _b64url_encode(
        json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    )
    return f"{payload_b64}.{_sign(payload_b64)}"


def verify_token(token: str) -> ContextRecord | None:
    """
    Verify a signed context token and retrieve its active context record.
    
    Returns:
        ContextRecord | None: The active context record when the token is valid;
        otherwise, `None`.
    """
    if not token or not isinstance(token, str) or token.count(".") != 1:
        return None
    payload_b64, sig_b64 = token.split(".", 1)
    expected = _sign(payload_b64)
    if not hmac.compare_digest(expected, sig_b64):
        return None
    raw = _b64url_decode(payload_b64)
    if raw is None:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("v") != _TOKEN_VERSION:
        return None
    try:
        exp = int(payload["exp"])
    except (KeyError, TypeError, ValueError):
        return None
    if exp <= int(time.time()):
        return None
    context_id = payload.get("ctx")
    if not isinstance(context_id, str) or not context_id:
        return None
    record = get_context(context_id)
    if record is None or not record.is_active():
        return None
    principal = payload.get("principal")
    if isinstance(principal, str) and principal and principal != record.principal_id:
        return None
    return record


def token_expires_at(token: str) -> float | None:
    """
    Extracts the expiration time from a token without verifying its signature.
    
    Parameters:
        token (str): Token containing an encoded payload with an ``exp`` claim.
    
    Returns:
        float | None: The expiration time as a Unix timestamp, or ``None`` if the payload or claim cannot be read.
    """
    if not token or token.count(".") != 1:
        return None
    payload_b64, _sig = token.split(".", 1)
    raw = _b64url_decode(payload_b64)
    if raw is None:
        return None
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    try:
        return float(payload["exp"])
    except (KeyError, TypeError, ValueError):
        return None
