#!/usr/bin/env python3
"""Local E2E harness for standalone bridge against the dev backend.

Creates a disposable user, creates a Codex local-bridge setup session, pairs
through the standalone CLI, inserts a queued local-agent job directly into the
local dev database, runs the bridge once, and prints sanitized evidence.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

API_BASE = os.environ.get("PA_API_BASE", "http://localhost:8081/api/v1")
REPO = Path("/Users/sairajesh/Desktop/workspace/personal-assistant-bridge")
BRIDGE_HOME = Path(os.environ.get("BRIDGE_E2E_HOME", "/tmp/pa-bridge-e2e-home"))
EXECUTOR = os.environ.get("BRIDGE_E2E_EXECUTOR", "fake")


def post(path: str, data: dict, token: str | None = None) -> dict:
    req = urllib.request.Request(
        API_BASE + path,
        data=json.dumps(data).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode()
            return json.loads(body or "{}")
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"POST {path} failed: {exc.code} {exc.read().decode()}") from exc


def get(path: str, token: str | None = None) -> dict:
    req = urllib.request.Request(API_BASE + path, method="GET")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode() or "{}")


def run(
    cmd: list[str], *, cwd: Path | None = None, env: dict | None = None, check: bool = True
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(cmd, cwd=cwd, env=env, text=True, capture_output=True, check=False)
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"command failed ({completed.returncode}): {' '.join(cmd)}\n"
            f"STDOUT:\n{completed.stdout}\nSTDERR:\n{completed.stderr}"
        )
    return completed


def psql(sql: str) -> str:
    cmd = [
        "docker",
        "exec",
        "-i",
        "personal-assistant-postgres",
        "psql",
        "-U",
        "postgres",
        "-d",
        "personal_assistant",
        "-Atc",
        sql,
    ]
    return run(cmd).stdout.strip()


def main() -> int:
    stamp = int(time.time())
    email = f"bridge-e2e-{stamp}@example.com"
    password = "Password123!"
    post("/auth/register", {"email": email, "password": password})
    login = post("/auth/login", {"email": email, "password": password})
    token = login.get("token") or login.get("access_token")
    if not token:
        raise RuntimeError("login response did not include token")

    setup = post(
        "/ai/providers/codex_cli/setup-session",
        {"setup_method": "local_bridge_pairing", "instance_name": "Codex CLI E2E"},
        token,
    )
    code = setup["public_setup_payload"]["pairing_code"]

    BRIDGE_HOME.mkdir(mode=0o700, parents=True, exist_ok=True)
    env = {**os.environ, "AI_SUBSCRIPTION_BRIDGE_HOME": str(BRIDGE_HOME)}
    pair = run(
        [
            "uv",
            "run",
            "personal-assistant-bridge",
            "pair",
            "--api-url",
            API_BASE,
            "--executor",
            "codex",
            "--name",
            "Codex CLI E2E",
            "--code",
            code,
        ],
        cwd=REPO,
        env=env,
    )
    config = json.loads((BRIDGE_HOME / "config.json").read_text())
    bridge_id = config["bridge_id"]
    provider_instance_id = config["provider_instance_id"]

    prompt = "Reply exactly with BRIDGE_E2E_OK. Do not include any extra text."
    input_text = "privacy_sentinel_should_not_leak_to_logs"
    safe_prompt = "'" + prompt.replace("'", "''") + "'"
    safe_input_text = "'" + input_text.replace("'", "''") + "'"
    sql = f"""
    INSERT INTO ai_local_agent_jobs (
      id, user_id, bridge_id, provider_instance_id, feature, capability, status,
      idempotency_key, attempt, max_attempts, timeout_seconds, input_ref,
      request_payload, result_payload, created_at, updated_at
    )
    SELECT gen_random_uuid(), b.user_id, b.id, b.provider_instance_id,
      'ai_rules', 'rules', 'queued', 'bridge-e2e-{stamp}', 0, 2, 120,
      '{{}}'::jsonb,
      jsonb_build_object('prompt', {safe_prompt}, 'input_text', {safe_input_text}),
      '{{}}'::jsonb, now(), now()
    FROM ai_local_agent_bridges b
    WHERE b.id = '{bridge_id}'
    RETURNING id;
    """
    job_output = psql(sql).splitlines()
    job_id = next(
        (line.strip() for line in job_output if line.strip() and " " not in line.strip()), ""
    )
    if not job_id:
        raise RuntimeError(f"failed to create queued local-agent job: {job_output!r}")

    bridge_run = run(
        [
            "uv",
            "run",
            "personal-assistant-bridge",
            "run",
            "--once",
            "--executor",
            EXECUTOR,
        ],
        cwd=REPO,
        env=env,
        check=False,
    )

    row = psql(
        "SELECT json_build_object("
        "'id', id, 'status', status, 'attempt', attempt, 'error_code', error_code, "
        "'result_payload', result_payload, 'completed', completed_at IS NOT NULL) "
        f"FROM ai_local_agent_jobs WHERE id = '{job_id}';"
    )
    health = get("/ai/providers/health", token)

    evidence = {
        "api_base": API_BASE,
        "email": email,
        "setup_status": setup.get("status"),
        "pair_stdout": pair.stdout.strip().splitlines(),
        "bridge_id": bridge_id,
        "provider_instance_id": provider_instance_id,
        "executor_used_for_run": EXECUTOR,
        "bridge_run_exit": bridge_run.returncode,
        "bridge_run_stdout": bridge_run.stdout.strip().splitlines(),
        "bridge_run_stderr": bridge_run.stderr.strip().splitlines(),
        "job": json.loads(row),
        "health": health,
        "bridge_home": str(BRIDGE_HOME),
    }
    print(json.dumps(evidence, indent=2, sort_keys=True))
    return 0 if json.loads(row)["status"] == "succeeded" else 2


if __name__ == "__main__":
    raise SystemExit(main())
