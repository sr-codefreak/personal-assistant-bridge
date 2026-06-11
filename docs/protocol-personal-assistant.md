# Personal Assistant protocol

Use an API base URL that includes `/api/v1`, for example `http://localhost:8080/api/v1` for local development or an HTTPS URL for remote environments.

## Pair

`POST {api_url}/ai/bridges/pair`

Request fields: `pairing_code`, `bridge_name`, `bridge_kind`, `version`, `active_profile`, `host_fingerprint`, and `capabilities`.

Response fields: `bridge_id`, `bridge_token`, optional `bridge_kind`, and optional `provider_instance_id`.

## Lease

`POST {api_url}/ai/bridges/{bridge_id}/jobs/lease`

Header: bearer authorization header containing the bridge token.

Body: `{ "max_jobs": 1 }`

Response: `{ "job": object | null }`. A valid v1 job must include a string ID, feature `ai_rules`, capability `rules`, a positive integer lease attempt, an object `request_payload`, a non-empty prompt, and a bounded timeout.

## Result

`POST {api_url}/ai/bridges/{bridge_id}/jobs/{job_id}/result`

Header: bearer authorization header containing the bridge token.

Body fields: `status`, `lease_attempt`, `result_payload`, `error_code`, `error_message`, and `latency_ms`.

The lease attempt is a fence. Backends should reject stale or expired result submissions rather than overwriting newer/final states.

## Invalid jobs

If a malformed job still has a safe job ID and positive integer attempt, the bridge submits a failed `invalid_job` result. If the ID or attempt is missing/unsafe, the bridge reports only a local safe error and does not submit a result.
