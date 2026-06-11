from __future__ import annotations

import subprocess
import sys

import ai_subscription_bridge


def test_version_is_available() -> None:
    assert ai_subscription_bridge.__version__ == "0.1.0"


def test_cli_help_runs() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "ai_subscription_bridge.cli", "--help"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "ai-subscription-bridge" in result.stdout
