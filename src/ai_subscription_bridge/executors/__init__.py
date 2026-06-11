"""Executor factory."""

from __future__ import annotations

from ai_subscription_bridge.executors.codex import CodexExecutor
from ai_subscription_bridge.executors.fake import FakeExecutor


def build_executor(name: str) -> CodexExecutor | FakeExecutor:
    if name == "codex":
        return CodexExecutor()
    if name == "fake":
        return FakeExecutor()
    raise ValueError("unsupported_executor")


__all__ = ["CodexExecutor", "FakeExecutor", "build_executor"]
