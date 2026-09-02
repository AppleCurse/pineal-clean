# Changelog

## Unreleased (post-rc.2) — 2026-09-02

### Release gates (G7)

- Added `.github/workflows/release-gates.yml` — manual-only (`workflow_dispatch`) wiring for the two open rc.2 live gates; never triggers on push/PR (Gate A is a paid live LLM call); single-flight concurrency (no cancellation of a running paid gate).
  - `live-llm-e2e` (`live_llm_openrouter_e2e`): runs `live_llm_gate.py` with `secrets.OPENROUTER_API_KEY` + `LIVE_LLM_E2E=1`. Fail-closed: rejects the run up front when the secret is missing; bounded by `OPENROUTER_MAX_SPEND_USD=5`.
  - `docker-chromium-smoke` (`docker_chromium_smoke`): real `docker compose up --build`; health gate (`ready|degraded` → 200); real Svelte dist served (`id="app"`); production auth verified both ways (no token → 401, `X-API-Key` → 200); in-container Playwright/Chromium smoke via `scripts/smoke_test_browser.py`.
- `RELEASE_EVIDENCE.md` — added post-seal **Section 12**: gate execution mechanism + honest scope note (the Instagram-initiate leg of Gate B stays operator-manual; GitHub runner IPs hit platform limits).
- `docs/reports/GENEL_DURUM_HARITASI_2026-09-02.md` — G7 rows updated: mechanism established; closure now requires a green manual run (Gate A) plus the manual Instagram leg (Gate B).
- Gates remain **open** until a green workflow run is recorded — this change wires the button, it does not claim the gates passed.

## 3.0.0-rc.2 — 2026-09-02

### Release evidence

- Integrated the sealed rc.2 evidence record (`RELEASE_EVIDENCE.md` + `release/3.0.0-rc.2.json`, sealed 2026-09-01 on branch `8e3b2918`): 14/14 static + runtime checks PASS, 6 negative security tests PASS, DR 63→0→63 verified, deployment gates PASS; 2 live gates remain open (live LLM E2E + Docker/Chromium smoke).
- `VERSION` bumped `3.0.0-rc.1` → `3.0.0-rc.2`.

### Routing (post-seal main work)

- `#50` — WebSocket/token handling + UnifiedRouter gap closures.
- `#52` — UnifiedRouter connected to `/v1`, capability-based agent routing, catalog auto-config.
- `#53` — 2026-09-02 decision matrix: Sonnet-5 primaries (profiler/mapper/aspasia/synthesizer+friction, V4-Pro fallback), vision = Gemini 3.7 Flash + Grok 4.6, OSINT synthesis = Grok 4.6, verifier extract (V4-Flash) split from judgment (Sonnet-5); catalog/pricing + `claude_sonnet_5`, `grok_4_6`; retired slugs (`solar-pro4`, `ling-3.0-flash`, `glm-5.2`) out of every chain.

### Performance / fixes

- Hindsight Memory semantic index: batched inserts via single-connection `executemany` (revived from PR #49) — O(N) commits → 1 commit.
- WaterHoseVisualizer: PR #49's implicit-`any` fix confirmed **superseded** — current main already types particles via the `Particle` interface (no code change needed).

### Re-validation at `b14a8e16`

- Backend: 634 passed, 2 skipped, 0 failed; coverage 83.31% ≥ 80%; `ruff check .` clean.
- Main CI matrix green (run `33590408702`): backend · frontend · rust-core · android · smoke.
- Open gates unchanged: `live_llm_openrouter_e2e`, `docker_chromium_smoke` → GO LIVE pending.

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
