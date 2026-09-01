# Changelog

## 3.0.0-rc.1 — 2026-09-01

### Production repair

- Made backend coverage, frontend check/build, Rust check/test, Android lint/test/assemble, and uvicorn smoke mandatory CI gates.
- Restored a reproducible Android Gradle wrapper/toolchain and validated a real APK build on clean CI runners.
- Replaced gateway-global LLM provenance with immutable call IDs and task/agent-local call scopes.
- Added atomic concurrent spend reservations, fail-closed unknown pricing, cancellation release, and settlement-before-parse for malformed paid responses.
- Distinguished empty canonical memory from corruption, preserved corrupt bytes, and added explicit quarantine/reset recovery.
- Classified missing dependencies separately from broken imports and made required startup failures machine-readable.
- Enforced deterministic task lifecycle sequencing, terminal-state immutability, idempotent termination, and visible queue degradation metrics.
- Added production fail-closed authentication, first-message WebSocket auth, DNS-pinned outbound requests, redirect/private-address rejection, path containment, secret redaction, and bounded rate/timeout/retry controls.
- Classified `rust_core/` as CI-validated experimental/optional code with no Python product-runtime or product-decision effect.
- Added a no-method-mock cross-stack test using a real OpenAI-compatible local HTTP provider through API, executor, agent, LLM gateway, provenance, canonical memory, telemetry, WebSocket, and UI protocol contracts.
- Added task IDs to initiation/results, cancellable mission handles, cancellation/halt APIs, and a UI cancellation control.

### Regression evidence

- Local release suite: 515 passed, 2 skipped; 85.64% backend coverage before final RC-only regressions.
- Frontend: `npm run check` and `npm run build` pass with zero diagnostics.
- Phase 10 CI: GitHub Actions run `33462022412` passed backend, frontend, Rust, Android, and smoke jobs.
- The final `v3.0.0-rc.1` tag is created only after the release-candidate commit passes the same mandatory CI matrix.

### Deliberate boundaries

- `rust_core/` and the Tauri draft are not product-integrated.
- X scraping and experimental OSINT/code-execution routes remain disabled or explicit opt-ins.
- A live third-party OpenRouter credential gate remains operator-triggered; the mandatory hermetic E2E uses the actual HTTP/SDK/runtime path against a deterministic local provider and does not claim external-provider availability.
