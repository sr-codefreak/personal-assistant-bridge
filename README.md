# Personal Assistant Bridge

Standalone local AI subscription bridge for Personal Assistant-compatible backends.

This repository will package a generic `ai-subscription-bridge` CLI plus a compatibility alias named `personal-assistant-bridge`. The bridge lets a trusted backend lease jobs while execution happens locally through an already-authenticated Codex CLI subscription, avoiding provider API keys in the backend.

## Status

Initial package skeleton for the approved BUILD implementation. Full protocol, config, adapter, executor, runner, tests, and documentation are implemented in follow-up commits on this feature branch.

## Security posture

- Pairing and bridge tokens are local secrets.
- Prompts are sent to Codex over stdin, not argv.
- Backend payloads must pass local validation before execution.
- User-facing diagnostics must redact tokens, pairing codes, prompts, backend bodies, Codex failure output, malformed payload strings, and secret-looking environment values.

## Development

```bash
uv sync --all-extras --dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```
