"""Codex CLI executor."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from time import monotonic

from ai_subscription_bridge.protocol import MODEL_ID_PATTERN, ExecutionResult, Job

SECRET_ENV_RE = re.compile(r"(TOKEN|KEY|SECRET|PASSWORD|AWS_|OPENAI|ANTHROPIC|GITHUB_TOKEN)", re.I)
ALLOW_ENV = {
    "PATH",
    "HOME",
    "USER",
    "LOGNAME",
    "TMPDIR",
    "TEMP",
    "TMP",
    "LANG",
    "LC_ALL",
    "SSL_CERT_FILE",
    "REQUESTS_CA_BUNDLE",
    "CODEX_HOME",
}


def minimal_env() -> dict[str, str]:
    env: dict[str, str] = {}
    for key, value in os.environ.items():
        if key in ALLOW_ENV and not SECRET_ENV_RE.search(key):
            env[key] = value
    if "PATH" not in env:
        env["PATH"] = os.defpath
    return env


class CodexExecutor:
    name = "codex"

    def __init__(self, codex_path: str | None = None) -> None:
        self.codex_path = shutil.which("codex") if codex_path is None else (codex_path or None)

    def capabilities(self) -> dict[str, object]:
        caps: dict[str, object] = {"name": self.name, "codex_cli": self.codex_path is not None}
        if self.codex_path:
            caps["codex_path"] = self.codex_path
            try:
                completed = subprocess.run(
                    [self.codex_path, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    check=False,
                    env=minimal_env(),
                )
                caps["codex_version"] = (completed.stdout or completed.stderr).strip()
            except (OSError, subprocess.SubprocessError):
                caps["codex_version"] = "unknown"
        return caps

    def execute(self, job: Job) -> ExecutionResult:
        start = monotonic()
        if not self.codex_path:
            return ExecutionResult(
                "failed",
                {},
                "codex_not_found",
                "codex_not_found",
                int((monotonic() - start) * 1000),
            )
        prompt = str(job.request_payload["prompt"]).strip()
        input_text = job.request_payload.get("input_text")
        if isinstance(input_text, str) and input_text:
            prompt = f"{prompt}\n\nInput:\n{input_text}"
        command = [
            self.codex_path,
            "exec",
            "--sandbox",
            "read-only",
            "--skip-git-repo-check",
            "--ephemeral",
        ]
        model = job.request_payload.get("model")
        if (
            isinstance(model, str)
            and not model.startswith("-")
            and MODEL_ID_PATTERN.fullmatch(model)
        ):
            command.extend(["--model", model])
        command.append("-")
        try:
            with tempfile.TemporaryDirectory(prefix="ai-subscription-bridge-") as cwd:
                completed = subprocess.run(
                    command,
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=job.timeout_seconds,
                    cwd=cwd,
                    env=minimal_env(),
                    shell=False,
                    check=False,
                )
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                "failed", {}, "codex_timeout", "codex_timeout", int((monotonic() - start) * 1000)
            )
        except OSError:
            return ExecutionResult(
                "failed", {}, "codex_failed", "codex_failed", int((monotonic() - start) * 1000)
            )
        if completed.returncode != 0:
            return ExecutionResult(
                "failed", {}, "codex_failed", "codex_failed", int((monotonic() - start) * 1000)
            )
        return ExecutionResult(
            "succeeded",
            {"text": completed.stdout.strip(), "executor": "codex"},
            latency_ms=int((monotonic() - start) * 1000),
        )
