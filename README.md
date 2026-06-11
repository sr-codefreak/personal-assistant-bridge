# Personal Assistant Bridge

Standalone local AI subscription bridge for Personal Assistant-compatible backends.

The package exposes a generic `ai-subscription-bridge` CLI plus a compatibility alias named `personal-assistant-bridge`. A trusted backend leases jobs to this local process while execution happens through a locally authenticated Codex CLI subscription. Backend services do not need provider API keys for the local Codex execution path.

## Install

```bash
uv tool install git+https://github.com/sr-codefreak/personal-assistant-bridge.git
# or from a checkout
uv sync --all-extras --dev
```

## Personal Assistant quickstart

Use the API base URL including `/api/v1`:

```bash
printf '%s' '<pairing-code>' | ai-subscription-bridge pair \
  --api-url http://localhost:8080/api/v1 \
  --executor codex \
  --code-stdin

ai-subscription-bridge doctor
ai-subscription-bridge run --once
```

For deterministic smoke tests without Codex:

```bash
ai-subscription-bridge run --once --executor fake
```

## Security posture

- Pairing codes and bridge tokens are local secrets.
- Prompts are sent to Codex over stdin, not argv.
- Backend payloads must pass local validation before execution.
- User-facing diagnostics redact tokens, pairing codes, prompts, backend bodies, Codex failure output, malformed payload strings, and secret-looking environment values.
- Non-localhost HTTP API URLs are rejected; use HTTPS for remote backends.
- Config is stored in `~/.ai-subscription-bridge/config.json` with private POSIX permissions when supported.

## Development

```bash
uv sync --all-extras --dev
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv build
```
