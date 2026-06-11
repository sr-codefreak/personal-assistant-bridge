from ai_subscription_bridge.protocol import validate_job


def valid_job(**overrides):
    job = {
        "id": "job-1",
        "feature": "ai_rules",
        "capability": "rules",
        "lease_attempt": 2,
        "request_payload": {"prompt": "summarize", "input_text": "hello"},
        "timeout_seconds": 30,
    }
    job.update(overrides)
    return job


def test_valid_job_parses():
    result = validate_job(valid_job())
    assert result.ok
    assert result.job is not None
    assert result.job.id == "job-1"
    assert result.job.attempt == 2


def test_missing_id_or_attempt_not_submit_eligible():
    assert not validate_job(valid_job(id="")).submit_eligible
    assert not validate_job(valid_job(lease_attempt=0)).submit_eligible
    assert not validate_job(valid_job(lease_attempt="1")).submit_eligible


def test_invalid_with_id_attempt_submit_eligible():
    result = validate_job(valid_job(feature="other"))
    assert not result.ok
    assert result.submit_eligible
    assert result.job_id == "job-1"
    assert result.attempt == 2


def test_rejects_prompt_timeout_model_and_command_payloads():
    for job in [
        valid_job(request_payload={"prompt": ""}),
        valid_job(timeout_seconds=9999),
        valid_job(request_payload={"prompt": "x", "model": "--bad"}),
        valid_job(request_payload={"prompt": "x", "model": "bad space"}),
        valid_job(request_payload={"prompt": "x", "shell": True}),
    ]:
        result = validate_job(job, local_max_timeout_seconds=60)
        assert not result.ok
        assert result.submit_eligible
