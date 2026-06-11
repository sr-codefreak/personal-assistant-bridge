"""Executor protocol."""

from __future__ import annotations

from typing import Any, Protocol

from ai_subscription_bridge.protocol import ExecutionResult, Job


class Executor(Protocol):
    name: str

    def capabilities(self) -> dict[str, Any]: ...
    def execute(self, job: Job) -> ExecutionResult: ...
