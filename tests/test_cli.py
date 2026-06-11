import json

from ai_subscription_bridge import cli
from ai_subscription_bridge.protocol import PairResponse


class FakeAdapter:
    def pair(self, request, api_url):
        assert request.pairing_code == "pair-secret"
        return PairResponse("bridge-1", "token-secret", "codex", "provider-1")


def test_pair_code_stdin_saves_config_without_printing_secret(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AI_SUBSCRIPTION_BRIDGE_HOME", str(tmp_path))
    monkeypatch.setattr(cli, "build_adapter", lambda name: FakeAdapter())
    monkeypatch.setattr(
        cli.sys,
        "stdin",
        type("S", (), {"read": lambda self: "pair-secret\n", "isatty": lambda self: False})(),
    )
    code = cli.main(
        ["pair", "--api-url", "http://localhost:1/api/v1", "--executor", "fake", "--code-stdin"]
    )
    assert code == 0
    out = capsys.readouterr().out
    assert "Paired bridge successfully" in out
    assert "pair-secret" not in out
    assert "token-secret" not in out
    data = json.loads((tmp_path / "config.json").read_text())
    assert data["bridge_token"] == "token-secret"


def test_pair_non_tty_without_code_stdin_fails_safely(monkeypatch, capsys):
    monkeypatch.setattr(cli.sys, "stdin", type("S", (), {"isatty": lambda self: False})())
    code = cli.main(["pair", "--api-url", "http://localhost:1/api/v1"])
    assert code == 1
    err = capsys.readouterr().err
    assert "pairing_code_required" in err


def test_doctor_redacts_config(tmp_path, monkeypatch, capsys):
    from ai_subscription_bridge.config import BridgeConfig, save_config

    monkeypatch.setenv("AI_SUBSCRIPTION_BRIDGE_HOME", str(tmp_path))
    save_config(
        BridgeConfig(
            "http://localhost:1/api/v1",
            "personal-assistant",
            "bridge",
            "token-secret",
            "fake",
            "name",
            "default",
            {},
            1,
        )
    )
    assert cli.main(["doctor", "--executor", "fake"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["paired"] is True
    assert payload["config"]["bridge_token"] == "[REDACTED]"
    assert "token-secret" not in json.dumps(payload)


def test_run_missing_config_exits_one(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AI_SUBSCRIPTION_BRIDGE_HOME", str(tmp_path))
    assert cli.main(["run", "--once"]) == 1
    assert "config_missing" in capsys.readouterr().err
