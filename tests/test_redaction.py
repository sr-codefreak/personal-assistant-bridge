from ai_subscription_bridge.redaction import (
    REDACTED,
    contains_sentinel_leak,
    redact_mapping,
    sanitize_url,
)


def test_redacts_sensitive_nested_values():
    sentinels = ["tok_secret", "prompt_secret", "stderr_secret"]
    data = {
        "bridge_token": sentinels[0],
        "nested": {"prompt": sentinels[1], "ok": "visible"},
        "items": [{"stderr": sentinels[2]}],
    }
    redacted = redact_mapping(data)
    text = str(redacted)
    assert REDACTED in text
    assert not contains_sentinel_leak(text, sentinels)
    assert redacted["nested"]["ok"] == "visible"


def test_sanitize_url_removes_userinfo_query_fragment():
    assert (
        sanitize_url("https://user:pass@example.com:8443/api/v1?token=x#frag")
        == "https://example.com:8443/api/v1"
    )
