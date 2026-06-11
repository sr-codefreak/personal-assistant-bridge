import json
import stat

from ai_subscription_bridge.executors.codex import CodexExecutor, minimal_env
from ai_subscription_bridge.protocol import Job


def job(**payload):
    return Job("job1", "ai_rules", "rules", 1, {"prompt": "prompt-secret", **payload}, 5)


def make_fake_codex(tmp_path, body):
    path = tmp_path / "codex"
    path.write_text(body, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)
    return str(path)


def test_missing_codex_maps_safe_failure():
    result = CodexExecutor(codex_path="").execute(job())
    assert result.status == "failed"
    assert result.error_code == "codex_not_found"


def test_codex_receives_prompt_on_stdin_not_argv_and_minimal_env(tmp_path, monkeypatch):
    capture = tmp_path / "capture.json"
    codex = make_fake_codex(
        tmp_path,
        f"""#!/usr/bin/env python3
import json, os, sys
if '--version' in sys.argv:
    print('fake-codex 1.0')
    raise SystemExit(0)
stdin=sys.stdin.read()
json.dump({{'argv':sys.argv,'stdin':stdin,'env':dict(os.environ)}}, open({str(capture)!r}, 'w'))
print('codex result')
""",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "env-secret")
    result = CodexExecutor(codex).execute(job(model="gpt-5.1", input_text="input-secret"))
    assert result.status == "succeeded"
    assert result.result_payload["text"] == "codex result"
    data = json.loads(capture.read_text(encoding="utf-8"))
    assert data["argv"][-1] == "-"
    assert "prompt-secret" not in " ".join(data["argv"])
    assert "input-secret" not in " ".join(data["argv"])
    assert "prompt-secret" in data["stdin"]
    assert "input-secret" in data["stdin"]
    assert "OPENAI_API_KEY" not in data["env"]
    assert "env-secret" not in str(data["env"])
    assert "--model" in data["argv"] and "gpt-5.1" in data["argv"]


def test_codex_failure_and_timeout_are_redacted(tmp_path):
    fail = make_fake_codex(
        tmp_path,
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import sys",
                "print('stdout-secret')",
                "print('stderr-secret', file=sys.stderr)",
                "sys.exit(7)",
                "",
            ]
        ),
    )
    result = CodexExecutor(fail).execute(job())
    assert result.status == "failed"
    assert result.error_message == "codex_failed"
    assert "stdout-secret" not in str(result)
    slow = make_fake_codex(tmp_path, "#!/usr/bin/env python3\nimport time\ntime.sleep(5)\n")
    timeout_job = Job("job1", "ai_rules", "rules", 1, {"prompt": "p"}, 1)
    timeout = CodexExecutor(slow).execute(timeout_job)
    assert timeout.error_code == "codex_timeout"


def test_minimal_env_drops_secret_names(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "token-secret")
    assert "GITHUB_TOKEN" not in minimal_env()
