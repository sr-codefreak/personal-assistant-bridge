"""Protocol dataclasses and validation for AI subscription bridge jobs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Literal

SUPPORTED_JOBS = {("ai_rules", "rules")}
MIN_POLL_INTERVAL = 1.0
DEFAULT_JOB_TIMEOUT_SECONDS = 180
MAX_JOB_TIMEOUT_SECONDS = 600
MODEL_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
FORBIDDEN_PAYLOAD_KEYS = {"cwd", "env", "args", "command", "executable", "shell"}


@dataclass(frozen=True)
class PairRequest:
    pairing_code: str
    bridge_name: str
    bridge_kind: str
    version: str
    active_profile: str
    host_fingerprint: str
    capabilities: dict[str, Any]


@dataclass(frozen=True)
class PairResponse:
    bridge_id: str
    bridge_token: str
    bridge_kind: str
    provider_instance_id: str | None = None


@dataclass(frozen=True)
class Job:
    id: str
    feature: str
    capability: str
    attempt: int
    request_payload: dict[str, Any]
    timeout_seconds: int


@dataclass(frozen=True)
class ExecutionResult:
    status: Literal["succeeded", "failed"]
    result_payload: dict[str, Any]
    error_code: str = ""
    error_message: str = ""
    latency_ms: int = 0

    def to_job_result(self, attempt: int) -> JobResult:
        return JobResult(
            status=self.status,
            lease_attempt=attempt,
            result_payload=self.result_payload,
            error_code=self.error_code,
            error_message=self.error_message,
            latency_ms=self.latency_ms,
        )


@dataclass(frozen=True)
class JobResult:
    status: Literal["succeeded", "failed"]
    lease_attempt: int
    result_payload: dict[str, Any]
    error_code: str
    error_message: str
    latency_ms: int

    def to_payload(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "lease_attempt": self.lease_attempt,
            "result_payload": self.result_payload,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "latency_ms": self.latency_ms,
        }


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    job: Job | None = None
    error_code: str = ""
    submit_eligible: bool = False
    job_id: str | None = None
    attempt: int | None = None


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def validate_job(
    raw_job: Any, local_max_timeout_seconds: int = MAX_JOB_TIMEOUT_SECONDS
) -> ValidationResult:
    if not isinstance(raw_job, dict):
        return ValidationResult(False, error_code="invalid_job")

    job_id = raw_job.get("id") or raw_job.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        return ValidationResult(False, error_code="invalid_job", submit_eligible=False)
    job_id = job_id.strip()

    attempt = _positive_int(raw_job.get("lease_attempt", raw_job.get("attempt")))
    if attempt is None:
        return ValidationResult(
            False, error_code="invalid_job", job_id=job_id, submit_eligible=False
        )

    feature = raw_job.get("feature")
    capability = raw_job.get("capability")
    payload = raw_job.get("request_payload") or raw_job.get("payload")
    timeout_raw = raw_job.get("timeout_seconds", DEFAULT_JOB_TIMEOUT_SECONDS)
    if (
        not isinstance(feature, str)
        or not isinstance(capability, str)
        or (feature, capability) not in SUPPORTED_JOBS
        or not isinstance(payload, dict)
    ):
        return ValidationResult(
            False, error_code="invalid_job", job_id=job_id, attempt=attempt, submit_eligible=True
        )

    if FORBIDDEN_PAYLOAD_KEYS.intersection(payload):
        return ValidationResult(
            False, error_code="invalid_job", job_id=job_id, attempt=attempt, submit_eligible=True
        )

    prompt = payload.get("prompt")
    if not isinstance(prompt, str) or not prompt.strip():
        return ValidationResult(
            False, error_code="invalid_job", job_id=job_id, attempt=attempt, submit_eligible=True
        )

    timeout = _positive_int(timeout_raw)
    if timeout is None or timeout > local_max_timeout_seconds:
        return ValidationResult(
            False, error_code="invalid_job", job_id=job_id, attempt=attempt, submit_eligible=True
        )

    model = payload.get("model")
    if model is not None and (
        not isinstance(model, str) or model.startswith("-") or not MODEL_ID_PATTERN.fullmatch(model)
    ):
        return ValidationResult(
            False, error_code="invalid_job", job_id=job_id, attempt=attempt, submit_eligible=True
        )

    return ValidationResult(
        True,
        job=Job(
            id=job_id,
            feature=feature,
            capability=capability,
            attempt=attempt,
            request_payload=dict(payload),
            timeout_seconds=timeout,
        ),
        submit_eligible=True,
        job_id=job_id,
        attempt=attempt,
    )
