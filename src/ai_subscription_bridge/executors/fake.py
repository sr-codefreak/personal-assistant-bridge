"""Deterministic fake executor for tests and smoke flows."""

from __future__ import annotations

from time import monotonic

from ai_subscription_bridge.protocol import ExecutionResult, Job


class FakeExecutor:
    name = "fake"

    def capabilities(self) -> dict[str, object]:
        return {"name": self.name, "fake": True}

    def execute(self, job: Job) -> ExecutionResult:
        start = monotonic()
        return ExecutionResult(
            status="succeeded",
            result_payload={"text": f"fake bridge result for job {job.id}", "executor": "fake"},
            latency_ms=int((monotonic() - start) * 1000),
        )
