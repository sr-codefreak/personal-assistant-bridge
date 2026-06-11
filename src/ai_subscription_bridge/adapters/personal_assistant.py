"""Personal Assistant-compatible HTTP adapter."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from ai_subscription_bridge.adapters.base import BackendRequestError
from ai_subscription_bridge.config import BridgeConfig
from ai_subscription_bridge.protocol import JobResult, PairRequest, PairResponse

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def _validate_base_url(api_url: str) -> str:
    try:
        parts = urlsplit(api_url)
    except ValueError as exc:
        raise BackendRequestError("invalid_api_url", "CONFIG", api_url) from exc
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise BackendRequestError("invalid_api_url", "CONFIG", api_url)
    if parts.username or parts.password or parts.query or parts.fragment:
        raise BackendRequestError("invalid_api_url", "CONFIG", api_url)
    if parts.scheme == "http" and parts.hostname not in LOCAL_HOSTS:
        raise BackendRequestError("insecure_api_url", "CONFIG", api_url)
    path = parts.path.rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _endpoint(api_url: str, path: str) -> str:
    base = _validate_base_url(api_url)
    return base + "/" + path.lstrip("/")


class PersonalAssistantAdapter:
    name = "personal-assistant"

    def _json_request(
        self, method: str, url: str, payload: dict[str, Any], token: str | None = None
    ) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(url, data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310 - URL is locally validated.
                data = response.read()
        except HTTPError as exc:
            raise BackendRequestError(f"backend_http_{exc.code}", method, url, exc.code) from exc
        except URLError as exc:
            raise BackendRequestError("backend_unreachable", method, url) from exc
        try:
            decoded = json.loads(data.decode("utf-8") or "{}")
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise BackendRequestError("backend_invalid_json", method, url) from exc
        if not isinstance(decoded, dict):
            raise BackendRequestError("backend_invalid_json", method, url)
        return decoded

    def pair(self, request: PairRequest, api_url: str) -> PairResponse:
        url = _endpoint(api_url, "/ai/bridges/pair")
        response = self._json_request(
            "POST",
            url,
            {
                "pairing_code": request.pairing_code,
                "bridge_name": request.bridge_name,
                "bridge_kind": request.bridge_kind,
                "version": request.version,
                "active_profile": request.active_profile,
                "host_fingerprint": request.host_fingerprint,
                "capabilities": request.capabilities,
            },
        )
        bridge_id = response.get("bridge_id") or response.get("id")
        token = response.get("bridge_token") or response.get("token")
        if (
            not isinstance(bridge_id, str)
            or not bridge_id
            or not isinstance(token, str)
            or not token
        ):
            raise BackendRequestError("pairing_response_invalid", "POST", url)
        provider_instance_id = response.get("provider_instance_id")
        return PairResponse(
            bridge_id=bridge_id,
            bridge_token=token,
            bridge_kind=str(response.get("bridge_kind") or request.bridge_kind),
            provider_instance_id=provider_instance_id
            if isinstance(provider_instance_id, str)
            else None,
        )

    def lease(self, cfg: BridgeConfig, max_jobs: int = 1) -> Mapping[str, Any] | None:
        bridge_id = quote(cfg.bridge_id, safe="")
        url = _endpoint(cfg.api_url, f"/ai/bridges/{bridge_id}/jobs/lease")
        response = self._json_request("POST", url, {"max_jobs": max_jobs}, cfg.bridge_token)
        job = response.get("job")
        if job is None:
            return None
        if not isinstance(job, Mapping):
            raise BackendRequestError("backend_invalid_job", "POST", url)
        return job

    def submit_result(self, cfg: BridgeConfig, job_id: str, result: JobResult) -> None:
        bridge_id = quote(cfg.bridge_id, safe="")
        escaped_job_id = quote(job_id, safe="")
        url = _endpoint(cfg.api_url, f"/ai/bridges/{bridge_id}/jobs/{escaped_job_id}/result")
        self._json_request("POST", url, result.to_payload(), cfg.bridge_token)
