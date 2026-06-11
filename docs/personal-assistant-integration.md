# Personal Assistant integration

Phase 1 ships this standalone package without removing the current Personal Assistant platform bridge script.

## Recommended local smoke flow

1. Start the Personal Assistant backend and generate a local bridge setup session/pairing code from the provider settings UI or API.
2. Pair this package using the API base URL with `/api/v1`:
   ```bash
   printf '%s' '<pairing-code>' | ai-subscription-bridge pair --api-url http://localhost:8080/api/v1 --code-stdin
   ```
3. Run diagnostics:
   ```bash
   ai-subscription-bridge doctor
   ```
4. Execute one leased job:
   ```bash
   ai-subscription-bridge run --once
   ```

## Later wrapper/deprecation plan

- Keep `personal-assistant-bridge` as a compatibility alias.
- Once downstream platform scripts depend on this package, replace duplicated bridge logic with a thin wrapper.
- Preserve legacy config fallback from `~/.personal-assistant-bridge/config.json`; users can copy it to the generic path with `doctor --migrate-config`.
- Do not remove old scripts until the standalone package has passed local pairing and one-job smoke tests.
