from ai_subscription_bridge.config import BridgeConfig
from ai_subscription_bridge.runner import run_bridge


class Adapter:
    def __init__(self, job=None, fail_submit=False):
        self.job = job
        self.fail_submit = fail_submit
        self.submitted = []

    def lease(self, cfg, max_jobs=1):
        return self.job

    def submit_result(self, cfg, job_id, result):
        if self.fail_submit:
            from ai_subscription_bridge.adapters.base import BackendRequestError

            raise BackendRequestError("backend_http_500", "POST", cfg.api_url, 500)
        self.submitted.append((job_id, result))


class Executor:
    name = "fake"

    def capabilities(self):
        return {}

    def execute(self, job):
        from ai_subscription_bridge.protocol import ExecutionResult

        return ExecutionResult("succeeded", {"text": "ok"}, latency_ms=1)


def cfg():
    return BridgeConfig(
        "http://localhost:1/api/v1", "personal-assistant", "b", "t", "fake", "n", "default", {}, 1
    )


def valid_job():
    return {
        "id": "job1",
        "feature": "ai_rules",
        "capability": "rules",
        "lease_attempt": 4,
        "request_payload": {"prompt": "p"},
        "timeout_seconds": 5,
    }


def test_no_job_once_exits_zero(capsys):
    assert run_bridge(cfg(), Adapter(None), Executor(), once=True) == 0
    assert "No jobs" in capsys.readouterr().out


def test_fake_success_submits_attempt():
    adapter = Adapter(valid_job())
    assert run_bridge(cfg(), adapter, Executor(), once=True) == 0
    assert adapter.submitted[0][0] == "job1"
    assert adapter.submitted[0][1].lease_attempt == 4
    assert adapter.submitted[0][1].status == "succeeded"


def test_invalid_submits_when_id_attempt_valid():
    adapter = Adapter({**valid_job(), "feature": "bad"})
    assert run_bridge(cfg(), adapter, Executor(), once=True) == 2
    assert adapter.submitted[0][1].error_code == "invalid_job"


def test_invalid_missing_attempt_does_not_submit(capsys):
    adapter = Adapter(
        {**valid_job(), "lease_attempt": 0, "request_payload": {"prompt": "leaky-secret"}}
    )
    assert run_bridge(cfg(), adapter, Executor(), once=True) == 2
    assert adapter.submitted == []
    assert "leaky-secret" not in capsys.readouterr().out


def test_submit_failure_returns_three():
    assert run_bridge(cfg(), Adapter(valid_job(), fail_submit=True), Executor(), once=True) == 3
