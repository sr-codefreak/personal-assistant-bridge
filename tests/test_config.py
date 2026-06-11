import os
import stat

from ai_subscription_bridge.config import (
    BridgeConfig,
    load_config,
    migrate_legacy_to_generic,
    resolve_config_path,
    save_config,
)


def cfg(token="secret-token"):
    return BridgeConfig(
        api_url="http://localhost:8080/api/v1",
        adapter="personal-assistant",
        bridge_id="bridge-1",
        bridge_token=token,
        executor="fake",
        bridge_name="local",
        profile="default",
        capabilities={"x": True},
        paired_at=1,
    )


def test_env_home_save_load_and_private_permissions(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_SUBSCRIPTION_BRIDGE_HOME", str(tmp_path / "home"))
    path = save_config(cfg())
    loaded = load_config()
    assert loaded is not None and loaded.bridge_id == "bridge-1"
    if os.name == "posix":
        assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_legacy_migration_preserves_source(tmp_path, monkeypatch):
    generic = tmp_path / "generic"
    legacy = tmp_path / "legacy"
    monkeypatch.setenv("AI_SUBSCRIPTION_BRIDGE_HOME", str(generic))
    monkeypatch.setenv("PERSONAL_ASSISTANT_BRIDGE_HOME", str(legacy))
    legacy_path = legacy / "config.json"
    save_config(cfg("legacy-token"), legacy_path)
    result = migrate_legacy_to_generic()
    assert result.copied
    assert legacy_path.exists()
    assert (generic / "config.json").exists()


def test_resolve_generic_env_wins(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_SUBSCRIPTION_BRIDGE_HOME", str(tmp_path / "generic"))
    resolved = resolve_config_path(alias_mode=True)
    assert resolved.source == "generic_env"
