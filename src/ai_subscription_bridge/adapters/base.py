"""Adapter protocol and safe backend errors."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol

from ai_subscription_bridge.config import BridgeConfig
from ai_subscription_bridge.protocol import JobResult, PairRequest, PairResponse
from ai_subscription_bridge.redaction import sanitize_url


class BackendRequestError(RuntimeError):
    def __init__(self, code: str, method: str, url: str, status: int | None = None):
        self.code = code
        self.method = method
        self.url = sanitize_url(url)
        self.status = status
        status_part = f" status={status}" if status is not None else ""
        super().__init__(f"{code} {method} {self.url}{status_part}")


class BridgeAdapter(Protocol):
    def pair(self, request: PairRequest, api_url: str) -> PairResponse: ...
    def lease(self, cfg: BridgeConfig, max_jobs: int = 1) -> Mapping[str, Any] | None: ...
    def submit_result(self, cfg: BridgeConfig, job_id: str, result: JobResult) -> None: ...
