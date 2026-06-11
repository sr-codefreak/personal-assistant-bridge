"""Bridge runner orchestration."""

from __future__ import annotations

from time import sleep

from ai_subscription_bridge.adapters.base import BackendRequestError, BridgeAdapter
from ai_subscription_bridge.config import BridgeConfig
from ai_subscription_bridge.executors.base import Executor
from ai_subscription_bridge.protocol import ExecutionResult, JobResult, validate_job


def _invalid_result(attempt: int) -> JobResult:
    return ExecutionResult("failed", {}, "invalid_job", "invalid_job", 0).to_job_result(attempt)


def submit_with_retry(
    adapter: BridgeAdapter,
    cfg: BridgeConfig,
    job_id: str,
    result: JobResult,
    attempts: int = 3,
    delay: float = 1.0,
) -> bool:
    for index in range(attempts):
        try:
            adapter.submit_result(cfg, job_id, result)
            return True
        except BackendRequestError:
            if index + 1 == attempts:
                return False
            sleep(delay)
    return False


def run_bridge(
    cfg: BridgeConfig,
    adapter: BridgeAdapter,
    executor: Executor,
    once: bool = False,
    poll_interval: float = 5.0,
    local_max_timeout_seconds: int = 600,
) -> int:
    backoff = poll_interval
    while True:
        try:
            raw_job = adapter.lease(cfg, max_jobs=1)
        except BackendRequestError as exc:
            print(f"Lease failed: {exc.code}.")
            if once:
                return 3
            sleep(backoff)
            backoff = min(backoff * 2, 60)
            continue
        backoff = poll_interval
        if raw_job is None:
            print("No jobs available.")
            if once:
                return 0
            sleep(poll_interval)
            continue
        validation = validate_job(raw_job, local_max_timeout_seconds=local_max_timeout_seconds)
        if not validation.ok:
            print("Invalid job received.")
            if validation.submit_eligible and validation.job_id and validation.attempt:
                submitted = submit_with_retry(
                    adapter,
                    cfg,
                    validation.job_id,
                    _invalid_result(validation.attempt),
                    attempts=1 if once else 3,
                )
                if not submitted and once:
                    return 3
            if once:
                return 2
            continue
        assert validation.job is not None
        job = validation.job
        print(f"Leased job {job.id} ({job.feature}/{job.capability}).")
        execution = executor.execute(job).to_job_result(job.attempt)
        submitted = submit_with_retry(adapter, cfg, job.id, execution, attempts=1 if once else 3)
        if not submitted:
            print(f"Failed to submit job {job.id} result.")
            if once:
                return 3
            continue
        print(f"Submitted job {job.id} result: {execution.status}.")
        if once:
            return 0
