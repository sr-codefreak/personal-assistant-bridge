"""Private local configuration storage for the bridge."""

from __future__ import annotations

import json
import os
import stat
import tempfile
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from ai_subscription_bridge.redaction import redact_mapping

GENERIC_ENV = "AI_SUBSCRIPTION_BRIDGE_HOME"
LEGACY_ENV = "PERSONAL_ASSISTANT_BRIDGE_HOME"
GENERIC_HOME = Path.home() / ".ai-subscription-bridge"
LEGACY_HOME = Path.home() / ".personal-assistant-bridge"
CONFIG_FILE = "config.json"
CONFIG_VERSION = 1


class ConfigError(RuntimeError):
    pass


class ConfigPermissionError(ConfigError):
    pass


@dataclass(frozen=True)
class ResolvedConfigPath:
    path: Path
    source: Literal["generic_env", "legacy_env", "generic", "legacy_fallback", "missing"]
    legacy_config_used: bool
    migration_available: bool


@dataclass(frozen=True)
class MigrationResult:
    copied: bool
    source: Path | None
    destination: Path | None
    message: str


@dataclass(frozen=True)
class BridgeConfig:
    api_url: str
    adapter: str
    bridge_id: str
    bridge_token: str
    executor: str
    bridge_name: str
    profile: str
    capabilities: dict[str, Any]
    paired_at: int
    config_version: int = CONFIG_VERSION
    provider_instance_id: str | None = None

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> BridgeConfig:
        required = (
            "api_url",
            "adapter",
            "bridge_id",
            "bridge_token",
            "executor",
            "bridge_name",
            "profile",
        )
        missing = [k for k in required if not isinstance(data.get(k), str) or not data.get(k)]
        if missing:
            raise ConfigError("config_missing")
        capabilities = data.get("capabilities")
        if not isinstance(capabilities, dict):
            capabilities = {}
        paired_at = data.get("paired_at")
        if not isinstance(paired_at, int):
            paired_at = int(time.time())
        provider_instance_id = data.get("provider_instance_id")
        return cls(
            api_url=data["api_url"],
            adapter=data["adapter"],
            bridge_id=data["bridge_id"],
            bridge_token=data["bridge_token"],
            executor=data["executor"],
            bridge_name=data["bridge_name"],
            profile=data["profile"],
            capabilities=capabilities,
            paired_at=paired_at,
            config_version=int(data.get("config_version", CONFIG_VERSION)),
            provider_instance_id=provider_instance_id
            if isinstance(provider_instance_id, str)
            else None,
        )

    def to_mapping(self) -> dict[str, Any]:
        return asdict(self)

    def redacted(self) -> dict[str, Any]:
        return redact_mapping(self.to_mapping())


def _config(home: Path) -> Path:
    return home / CONFIG_FILE


def generic_home() -> Path:
    return Path(os.environ.get(GENERIC_ENV, str(GENERIC_HOME))).expanduser()


def legacy_home() -> Path:
    return Path(os.environ.get(LEGACY_ENV, str(LEGACY_HOME))).expanduser()


def resolve_config_path(alias_mode: bool = False) -> ResolvedConfigPath:
    if os.environ.get(GENERIC_ENV):
        path = _config(generic_home())
        return ResolvedConfigPath(path, "generic_env", False, False)
    if alias_mode and os.environ.get(LEGACY_ENV):
        path = _config(legacy_home())
        return ResolvedConfigPath(path, "legacy_env", True, False)
    generic = _config(GENERIC_HOME)
    legacy = _config(LEGACY_HOME)
    if generic.exists():
        return ResolvedConfigPath(generic, "generic", False, legacy.exists())
    if legacy.exists():
        return ResolvedConfigPath(legacy, "legacy_fallback", True, True)
    return ResolvedConfigPath(_config(generic_home()), "missing", False, False)


def write_config_path() -> Path:
    if os.environ.get(GENERIC_ENV):
        return _config(generic_home())
    return _config(GENERIC_HOME)


def _chmod_private_dir(path: Path) -> None:
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name == "posix":
        os.chmod(path, 0o700)


def _repair_file_mode(path: Path) -> None:
    if os.name != "posix" or not path.exists():
        return
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & 0o077:
        try:
            os.chmod(path, 0o600)
        except OSError as exc:  # pragma: no cover - platform/permission dependent
            raise ConfigPermissionError("config_permission_error") from exc


def load_config(
    allow_legacy_fallback: bool = True, alias_mode: bool = False
) -> BridgeConfig | None:
    resolved = resolve_config_path(alias_mode=alias_mode)
    if resolved.source == "legacy_fallback" and not allow_legacy_fallback:
        return None
    if not resolved.path.exists():
        return None
    _repair_file_mode(resolved.path)
    try:
        data = json.loads(resolved.path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError("config_missing") from exc
    if not isinstance(data, dict):
        raise ConfigError("config_missing")
    return BridgeConfig.from_mapping(data)


def save_config(config: BridgeConfig, path: Path | None = None) -> Path:
    target = path or write_config_path()
    _chmod_private_dir(target.parent)
    fd, tmp_name = tempfile.mkstemp(prefix="config-", suffix=".tmp", dir=str(target.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            if os.name == "posix":
                os.fchmod(handle.fileno(), 0o600)
            json.dump(config.to_mapping(), handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        Path(tmp_name).replace(target)
        if os.name == "posix":
            os.chmod(target, 0o600)
        return target
    except Exception:
        Path(tmp_name).unlink(missing_ok=True)
        raise


def migrate_legacy_to_generic(overwrite: bool = False) -> MigrationResult:
    source = _config(legacy_home())
    destination = _config(generic_home())
    if not source.exists():
        return MigrationResult(False, None, destination, "legacy_config_missing")
    if destination.exists() and not overwrite:
        return MigrationResult(False, source, destination, "generic_config_exists")
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ConfigError("config_missing")
    cfg = BridgeConfig.from_mapping(data)
    save_config(cfg, destination)
    return MigrationResult(True, source, destination, "copied")


def doctor_payload(
    executor_caps: dict[str, Any], alias_mode: bool = False, migrated: MigrationResult | None = None
) -> dict[str, Any]:
    resolved = resolve_config_path(alias_mode=alias_mode)
    cfg = load_config(alias_mode=alias_mode)
    warnings: list[str] = []
    if resolved.legacy_config_used:
        warnings.append("legacy_config_used")
    if resolved.migration_available and not resolved.legacy_config_used:
        warnings.append("legacy_config_available")
    payload: dict[str, Any] = {
        "config_path": str(resolved.path),
        "paired": cfg is not None,
        "legacy_config_used": resolved.legacy_config_used,
        "migration_available": resolved.migration_available,
        "generic_config_exists": _config(GENERIC_HOME).exists(),
        "warnings": warnings,
        "config": cfg.redacted() if cfg else None,
        "executor": redact_mapping(executor_caps),
    }
    if migrated is not None:
        payload["migration"] = {
            "copied": migrated.copied,
            "source": str(migrated.source) if migrated.source else None,
            "destination": str(migrated.destination) if migrated.destination else None,
            "message": migrated.message,
        }
    return redact_mapping(payload)
