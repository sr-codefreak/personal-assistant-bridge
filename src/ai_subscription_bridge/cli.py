"""Command-line entry points for the AI subscription bridge."""

from __future__ import annotations

import argparse

from ai_subscription_bridge import __version__


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-subscription-bridge",
        description="Standalone local AI subscription bridge.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("doctor", help="Print bridge readiness diagnostics.")
    subparsers.add_parser("pair", help="Pair this local bridge with a trusted backend.")
    subparsers.add_parser("run", help="Lease and execute backend jobs locally.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command is None:
        parser.print_help()
        return 0
    # Placeholder until implementation tasks T2-T6 fill in behavior.
    print(f"{args.command}: not implemented yet")
    return 1


def main_pa_alias(argv: list[str] | None = None) -> int:
    return main(argv)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
