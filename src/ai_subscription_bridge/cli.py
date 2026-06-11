"""Command-line entry points for the AI subscription bridge."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import socket
import sys
import time

from ai_subscription_bridge import __version__
from ai_subscription_bridge.adapters import build_adapter
from ai_subscription_bridge.adapters.base import BackendRequestError
from ai_subscription_bridge.config import (
    BridgeConfig,
    ConfigError,
    doctor_payload,
    load_config,
    migrate_legacy_to_generic,
    save_config,
)
from ai_subscription_bridge.executors import build_executor
from ai_subscription_bridge.protocol import MIN_POLL_INTERVAL, PairRequest
from ai_subscription_bridge.redaction import safe_error
from ai_subscription_bridge.runner import run_bridge


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-subscription-bridge",
        description="Standalone local AI subscription bridge.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    pair = subparsers.add_parser("pair", help="Pair this local bridge with a trusted backend.")
    pair.add_argument("--api-url", required=True)
    pair.add_argument("--adapter", default="personal-assistant", choices=["personal-assistant"])
    pair.add_argument("--executor", default="codex", choices=["codex", "fake"])
    pair.add_argument("--name", default=None)
    pair.add_argument("--profile", default="default")
    pair.add_argument("--code-stdin", action="store_true")
    pair.add_argument("--code", default=None)

    doctor = subparsers.add_parser("doctor", help="Print bridge readiness diagnostics.")
    doctor.add_argument("--format", choices=["json"], default="json")
    doctor.add_argument("--migrate-config", action="store_true")
    doctor.add_argument("--executor", choices=["codex", "fake"], default=None)
    doctor.add_argument("--adapter", choices=["personal-assistant"], default="personal-assistant")

    run = subparsers.add_parser("run", help="Lease and execute backend jobs locally.")
    run.add_argument("--once", action="store_true")
    run.add_argument("--poll-interval", type=float, default=5.0)
    run.add_argument("--executor", choices=["codex", "fake"], default=None)
    run.add_argument("--max-job-timeout-seconds", type=int, default=600)
    return parser


def _pairing_code(args: argparse.Namespace) -> str:
    if args.code_stdin:
        return sys.stdin.read().strip()
    if isinstance(args.code, str) and args.code:
        return args.code.strip()
    if sys.stdin.isatty():
        return str(getpass.getpass("Pairing code: ")).strip()
    raise ValueError("pairing_code_required")


def _host_fingerprint() -> str:
    seed = f"{socket.gethostname()}:{getpass.getuser()}".encode("utf-8", "ignore")
    return hashlib.sha256(seed).hexdigest()


def _cmd_pair(args: argparse.Namespace, alias_mode: bool) -> int:
    try:
        code = _pairing_code(args)
        if not code:
            raise ValueError("pairing_code_required")
        executor = build_executor(args.executor)
        adapter = build_adapter(args.adapter)
        request = PairRequest(
            pairing_code=code,
            bridge_name=args.name or socket.gethostname() or "local-bridge",
            bridge_kind="codex" if args.executor == "codex" else "hermes",
            version=__version__,
            active_profile=args.profile,
            host_fingerprint=_host_fingerprint(),
            capabilities=executor.capabilities(),
        )
        response = adapter.pair(request, args.api_url)
        cfg = BridgeConfig(
            api_url=args.api_url,
            adapter=args.adapter,
            bridge_id=response.bridge_id,
            bridge_token=response.bridge_token,
            executor=args.executor,
            bridge_name=request.bridge_name,
            profile=args.profile,
            capabilities=request.capabilities,
            paired_at=int(time.time()),
            provider_instance_id=response.provider_instance_id,
        )
        path = save_config(cfg)
    except (ValueError, BackendRequestError, ConfigError) as exc:
        code = exc.code if isinstance(exc, BackendRequestError) else str(exc)
        print(safe_error(code), file=sys.stderr)
        return 1
    print("Paired bridge successfully.")
    print(f"Bridge ID: {response.bridge_id}")
    print(f"Config path: {path}")
    return 0


def _cmd_doctor(args: argparse.Namespace, alias_mode: bool) -> int:
    migrated = migrate_legacy_to_generic() if args.migrate_config else None
    cfg = load_config(alias_mode=alias_mode)
    executor_name = args.executor or (cfg.executor if cfg else "codex")
    executor = build_executor(executor_name)
    payload = doctor_payload(executor.capabilities(), alias_mode=alias_mode, migrated=migrated)
    print(json.dumps(payload, indent=2, sort_keys=True))
    if executor_name == "codex" and not payload["executor"].get("codex_cli"):
        return 2
    return 0


def _cmd_run(args: argparse.Namespace, alias_mode: bool) -> int:
    try:
        cfg = load_config(alias_mode=alias_mode)
        if cfg is None:
            print(safe_error("config_missing"), file=sys.stderr)
            return 1
        executor_name = args.executor or cfg.executor
        cfg = BridgeConfig(**{**cfg.to_mapping(), "executor": executor_name})
        adapter = build_adapter(cfg.adapter)
        executor = build_executor(executor_name)
        poll = max(MIN_POLL_INTERVAL, args.poll_interval)
        return run_bridge(
            cfg,
            adapter,
            executor,
            once=args.once,
            poll_interval=poll,
            local_max_timeout_seconds=args.max_job_timeout_seconds,
        )
    except (ValueError, BackendRequestError, ConfigError) as exc:
        code = exc.code if isinstance(exc, BackendRequestError) else str(exc)
        print(safe_error(code), file=sys.stderr)
        return 1


def main(argv: list[str] | None = None, alias_mode: bool = False) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    if args.command == "pair":
        return _cmd_pair(args, alias_mode)
    if args.command == "doctor":
        return _cmd_doctor(args, alias_mode)
    if args.command == "run":
        return _cmd_run(args, alias_mode)
    return 1


def main_pa_alias(argv: list[str] | None = None) -> int:
    return main(argv, alias_mode=True)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
