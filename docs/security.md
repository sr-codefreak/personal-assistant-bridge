# Security

The bridge moves local AI subscription execution to a user-controlled machine. Treat the backend as trusted because it can send prompts to the local executor.

## Secrets

- The backend receives no Codex/OpenAI API key from this bridge.
- Pairing codes are one-time secrets; prefer `--code-stdin` over `--code` to avoid shell history exposure.
- Bridge tokens are stored only in the local config file and sent as bearer auth headers to lease/result endpoints.
- Doctor output and errors redact bridge tokens, pairing codes, prompts, input text, backend bodies, Codex stdout/stderr on failure, and secret-looking environment values.

## Transport

- Localhost HTTP URLs are allowed for development.
- Non-localhost HTTP is rejected; use HTTPS for remote backends.
- URL userinfo, query strings, and fragments are rejected/sanitized before endpoint construction.

## Local execution boundary

Codex receives prompts on stdin with `codex exec -`; prompts are not passed as command-line argv. The executor uses `shell=False`, a temporary working directory, and a minimal environment allowlist. Variables with names containing token/key/secret/password or known provider token names are dropped.

The installed Codex CLI exposes `--sandbox`. This bridge uses `--sandbox read-only`, `--skip-git-repo-check`, and `--ephemeral` for noninteractive execution in an empty temporary directory. That is safer than granting workspace-write access for backend-supplied jobs.

## Config permissions

On POSIX platforms the config directory is written as `0700` and `config.json` as `0600`. Loading attempts to repair overly broad file modes and fails closed if repair is not possible.
