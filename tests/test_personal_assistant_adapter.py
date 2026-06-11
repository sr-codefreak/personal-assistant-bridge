from ai_subscription_bridge.adapters.base import BackendRequestError
from ai_subscription_bridge.adapters.personal_assistant import _endpoint
from ai_subscription_bridge.config import BridgeConfig
from ai_subscription_bridge.protocol import JobResult


def cfg():
    return BridgeConfig(
        api_url="http://localhost:8080/api/v1",
        adapter="personal-assistant",
        bridge_id="bridge/id",
        bridge_token="secret-token",
        executor="fake",
        bridge_name="local",
        profile="default",
        capabilities={},
        paired_at=1,
    )


def test_endpoint_preserves_api_prefix():
    assert (
        _endpoint("http://localhost:8080/api/v1", "/ai/bridges/pair")
        == "http://localhost:8080/api/v1/ai/bridges/pair"
    )


def test_rejects_insecure_non_localhost_and_userinfo_query_fragment():
    for url in [
        "http://example.com/api/v1",
        "https://user:pass@example.com/api/v1",
        "https://example.com/api/v1?x=y",
        "https://example.com/api/v1#frag",
    ]:
        try:
            _endpoint(url, "/ai/bridges/pair")
        except BackendRequestError as exc:
            text = str(exc)
            assert "secret-token" not in text
            assert "user:pass" not in text
        else:
            raise AssertionError("expected error")


def test_submit_url_escapes_identifiers(monkeypatch):
    seen = {}
    from ai_subscription_bridge.adapters.personal_assistant import PersonalAssistantAdapter

    def fake_request(self, method, url, payload, token=None):
        seen.update(method=method, url=url, payload=payload, token=token)
        return {}

    monkeypatch.setattr(PersonalAssistantAdapter, "_json_request", fake_request)
    PersonalAssistantAdapter().submit_result(
        cfg(), "job/id", JobResult("succeeded", 3, {}, "", "", 1)
    )
    assert "bridge%2Fid" in seen["url"]
    assert "job%2Fid" in seen["url"]
    assert seen["token"] == "secret-token"
    assert "secret-token" not in seen["url"]
