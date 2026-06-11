"""Redaction helpers for safe CLI diagnostics."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

REDACTED = "[REDACTED]"
SENSITIVE_KEY_FRAGMENTS = (
    "token",
    "secret",
    "password",
    "pairing_code",
    "code",
    "prompt",
    "input_text",
    "request_payload",
    "authorization",
    "stdout",
    "stderr",
)


def is_sensitive_key(key: str) -> bool:
    folded = key.lower().replace("-", "_")
    return any(fragment in folded for fragment in SENSITIVE_KEY_FRAGMENTS)


def redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively redact sensitive mapping values."""
    redacted: dict[str, Any] = {}
    for key, item in value.items():
        if is_sensitive_key(str(key)):
            redacted[str(key)] = REDACTED
        elif isinstance(item, Mapping):
            redacted[str(key)] = redact_mapping(item)
        elif isinstance(item, list):
            redacted[str(key)] = [redact_mapping(v) if isinstance(v, Mapping) else v for v in item]
        else:
            redacted[str(key)] = item
    return redacted


def sanitize_url(url: str) -> str:
    """Return a URL safe for diagnostics: no userinfo, query, or fragment."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return "invalid-url"
    host = parts.hostname or ""
    netloc = host
    if parts.port is not None:
        netloc = f"{netloc}:{parts.port}"
    path = parts.path or ""
    return urlunsplit((parts.scheme, netloc, path, "", ""))


def safe_error(code: str) -> str:
    return f"bridge_error:{code}"


def contains_sentinel_leak(text: str, sentinels: Iterable[str]) -> bool:
    return any(sentinel and sentinel in text for sentinel in sentinels)
