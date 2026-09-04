# Changelog

## Unreleased (post-rc.2) — 2026-09-05

### ASPASIA TRUE CHIEF LAYER: amaç taşımı + kanonik sonuç döngüsü + UI köprüsü
- **Goal sözleşmesinin TEK kaynağı** `CognitiveRouter.GOAL_FOCUS` (7 goal id;
  her biri router'ın GERÇEK uzmanlarına harita — uydurma capability yok).
  `AspasiaIntent.goals` bu sözlükten türetilen Literal allowlist; drift testli.
- **Amaç kaybı fix:** `USER → Aspasia(intent+goals) → CommandGateway →
  InitiatePayload.aspasia_goals → input_data["aspasia_goals"] → CognitiveRouter`.
  Goal YOKSA plan birebir eski; uydurma goal şemada reddedilir (dispatch doğmaz);
  `/api/initiate` üzerinden gelen bilinmeyen goal planı değiştiremez (not düşer).
- **Kanıt kapısı üstünlüğü:** goals yalnız tercih bacaklarını daraltır;
  `autonomous_verifier` (policy) ve kanıt-kapılı `authenticity_auditor`
  goal'la eklenmez/silinmez; kanıt yoksa honest-skip notu — sahte yürütme yok.
- **Sonuç döngüsü (paralel store YOK):** `MissionResultReader` yalnız
  `CanonicalMemory.get_task_memory` okur; bozuk kayıt "corrupted + kurtarma
  gerekir" olarak taşınır. `room["active_tasks"]` terminal durumdaysa digest
  `"BAYAT-snapshot"` etiketler (kanonik = memory).
- **Model-mismatch görünürlüğü:** DENETİM bloğu artık `SUBSTITUTION DENIED:
  istenen=X — dönen=Y (provider)` satırını taşır (kaynak: mevcut call_log).
- **UI köprüsü:** ASPASIA seçiliyken serbest metin ÖNCE `/api/aspasia/command`;
  `accepted && task_id` → görev kartına bağlanır; değilse chat fallback (mesaj
  kaybı yok). Yapılandırılmış form `/api/initiate`'te kalır (programatik hat).
- Cancel/halt: bu fazda YOK (yalnız extension noktası: gateway dispatch şeması).
- Testler: `tests/unit/test_aspasia_chief_layer.py` 19/19; promosyon 16/16;
  routing regresyonu (provider-aware+firewall+compliance+policy+aspasia+wiring)
  92/92.

### ASPASIA-PROMOTION: merkezi doğal-dil arayüzü + komut ağzı (orkestrasyon yetkisi DEĞİL)
- `agent_core/aspasia/interface.py` (yeni): salt-okur denetçiler
  (Routing/Telemetry/Quota/Cost/Agent) mevcut SoT'ları okur; Governor'u olmayan
  gateway'den "HEALTHY" uydurulmaz (`unavailable`), unknown kota asla
  unlimited sayılmaz.
- `AspasiaCommandGateway`: doğal dil → `AspasiaIntent` (extra=forbid; model/
  agent/quota alanları şema düzeyinde reddedilir) → hedef URL doğrulaması →
  TEK dispatch kanalı `api._aspasia_command_dispatch`, ki bu `/api/initiate`
  akışının kendisidir (lifecycle + mission_tasks + run_mission; ikinci
  orchestrator yok). Niyet çıkarımı gerçek `aspasia` dialogue zincirinden
  geçer ve `capture_calls` ile `agent_id=aspasia` etiketlenir.
- `AspasiaChief`: `commands`/`executor` bağlama + chat promptuna DENETİM
  KATMANI digest'i (yalnız gerçek içerik varsa; uydurma blok yok). Sistem
  promptu persona + SINIR korunarak "merkezi arayüz ve denetim" rolüyle
  genişletildi.
- Uçlar: `POST /api/aspasia/command`, `GET /api/aspasia/state`.
- Gateway gözlemlenebilirlik düzeltmesi: `MODEL_SUBSTITUTION_DENIED` artık
  call_log'a `requested → returned` detayıyla yazılıyor (detay eski halinde
  yalnız exception metnindeydi, log'da kayboluyordu).
- Testler: `tests/unit/test_aspasia_promotion.py` 16/16 (görünürlük, komut
  akışı, şema güvenliği, dispatch tek kanalı, statik mutasyon-yüzeyi taraması,
  chat geri dönüşüm uyumu). Tam süit: 749P/32F(env-only)/2S — yeni başarısızlık yok.

### FINAL-SPEC: agent-level bypass kapıları (F-1/F-2/F-3/F-4) + transport-kanıtlı uygunluk

- **F-1 Aspasia:** `AspasiaChief.chat()` artık kimliksiz `query()` yerine
  `query_chain(task="dialogue", agent_name="aspasia")` yürütüyor →
  `AGENT_CHAINS["aspasia"]` + provider merdiveni + fallback zinciri devrede.
  Kullanıcının AÇIK `preferred_model`/`model_override` pini bilinçli olarak
  korunur (pin = tercih, bypass değil).
- **F-2:** `authenticity_auditor` ve `depth_analyst` çağrıları
  `agent_name=None + task fallback` olmaktan çıkarıldı; kendi matrix
  satırlarına bağlandı (depth zinciriyle BİLİNÇLİ paylaşım, matrix değişimi
  artık bu iki ajanın davranışını otomatik taşır).
- **F-3:** `human_behavior`, `mirror_truth`, `pattern_interrupt` tek-model
  tier-default yolundan zincirli agent-aware yola geçirildi (dönüş sözleşmesi
  aynı; mock dikişleri güncellendi).
- **F-4:** `get_agent_chain` zincirin KAYNAĞINI (`agent_matrix` /
  `env_override` / `task_chain`) her telemetri kaydına `chain_source` olarak
  yazıyor; RUNBOOK'a precedence sözleşmesi eklendi. ENV override kaldırılmadı
  — belgeli, testli, işaretli acil durum düğmesi.
- **Substitution firewall genişletildi (spec #27):** sessiz model ikamesi
  reddi artık OpenRouter legacy yolunda da geçerli ve hem iç retry'ı hem
  zincir fallback'ini tetiklemeyen non-retryable politika kararı
  (`model_substitution_denied` guard marker'ı).
- **Kota agregasyon hatası düzeltildi:** routed taşıma denemeleri governor'a
  provider-agrega pencerede (`*`) yazılıyor; `status(provider)` okuması artık
  gerçek akışta görünebilir (önceki per-model yazım, resolver skip'ini fiilen
  etkisiz bırakıyordu).
- **Liste vs effective fiyat:** `GatewayRoute.list_*` alanları + telemetri
  `route_key / pricing_* / list_pricing_* / discount_pct` backward-compatible
  alanları; Nous indirimi spend accounting'in TEK fiyat kaynağı (test: OR
  çağrısı sıfır, $3.20/$1M+0.2M settlement).
- Yeni: `tests/unit/test_final_spec_compliance.py` (23 test; transport
  boundary'de HTTP-level provider kanıtı dahil).

### MP-ROUTING: ajan hattı gerçek çok-sağlayıcılı yürütmeye geçti

- **OpenRouter artık santral değil, havuzun bir üyesi:** `LLMGateway.query()` ve
  `query_chain`/`query_json_chain` zincirleri, her model için önce o modelin
  `MODEL@PROVIDER` taşıma merdivenini yürür (Groq/Cerebras/Nous/DeepSeek doğrudan
  API'leri; kendi base_url, anahtar, fiyat ve kotasıyla). Kaynak:
  `agent_core/services/llm_gateway.py::agent_route_variants`.
- **Maliyet merdiveni free → indirimli → OpenRouter:** fiyat sıralaması
  `final_routing_policy.ROUTES` + provider kataloğundan; fiyatı bilinmeyen rota
  en sonda teklif edilir, spend-cap aktifse hiç teklif edilmez.
- **Kapılar aynı, bypass yok:** doğrudan rota ancak (1) credential env tanımlıysa,
  (2) katalog o modeli gerçekten sunuyorsa, (3) politika `is_paid` fail-closed
  kontrolünden (ücretli rota yalnız `PINEAL_ALLOW_PAID_ESCALATION=1`) ve kota
  sayacı EXHAUSTED değilse geçerse merdivene girer. Geçici hatada sıradaki taşıma,
  o da biterse zincirdeki sıradaki MODEL denenir; SpendCap/paid-escalation/
  unknown-pricing reddi tüm merdiveni DURDURUR (mevcut `_is_fallback_allowed`
  doktrini korunur).
- **Sessiz model ikamesi firewall'u `query()` routed yoluna da bağlandı**
  (`MODEL_SUBSTITUTION_DENIED`), telemetri `requested_model`/`actual_model`
  ayrımı sağlayıcı-gerçek kimliğiyle yazılır.
- **Anahtarsız varsayılan = birebiren eski davranış:** `agent_route_variants()`
  credential yoksa `[None]` döner; üretim yolunda sıfır değişiklik riski.
- Yeni env: `DEEPSEEK_API_KEY` (`.env.example`); test:
  `tests/unit/test_provider_aware_agent_chains.py` (12 test).

## Unreleased (post-rc.2) — 2026-09-03

### G7 release gate'leri koşulabilir hale getirildi (mekanizma onarımı)

- **`.github/workflows/release-gates.yml` eklendi** — gövde kanonik kaynakla
  (`release/release-gates.yml`) birebir. Önceki durumda dosya yalnız `release/` altındaydı;
  GitHub `on:` anahtarını default branch'in `.github/workflows/` dizininden okuduğu için
  `Actions → Release Gates` hiç görünmüyor, dolayısıyla **Gate A (`live_llm_openrouter_e2e`) ve
  Gate B (`docker_chromium_smoke`) koşulamıyordu** ("yeşil koşu kaydı yok" kırmızısının kök nedeni).
  "Operatör `cp`'lesin" adımı böylece kaldırıldı.
- **`tests/unit/test_release_gates_workflow.py`** (7 test) — dosya konumu, kaynak↔kopya bayt
  eşitliği (gövde kayması yasağı), **yalnızca** `workflow_dispatch` (push/PR/`schedule` yasağı —
  Gate A paralı çağrı içerir), Gate A fail-closed secret kontrolü + `LIVE_LLM_E2E=1` +
  `OPENROUTER_MAX_SPEND_USD`, Gate B'nin gerçek imaj/health/production-auth/Chromium/teardown
  adımları ve `concurrency.cancel-in-progress: false`.
- **Belge hizalama** — `RELEASE_EVIDENCE.md` §12'ye 2026-09-03 güncelleme tablosu (mekanizma
  kapandı ≠ gate kapandı; run URL'si işlenmeden gate'ler açık sayılır),
  `docs/reports/SON_HUKUM_DENETIM.md`'ye eski "kırmızı" hükümlerinin `f1e4602` üzerindeki yeniden
  ölçümü (`723 passed, 2 skipped` · coverage `%84.13` · ruff clean · main CI `success`).
- **Kapanmayan (bilinçli, operatörde):** `OPENROUTER_API_KEY` secret'ı + manuel dispatch (Gate A);
  docker'lı runner + Instagram initiate (Gate B). Bu ikisi yeşil olmadan stable ilan edilmez.

## Unreleased (post-rc.2) — 2026-09-02

### FINAL-KARAR-MATRIX production routing

- **`final_routing_policy.py`** — the FINAL decision matrix becomes the runtime
  economic source of truth: verified free routes (Groq/Cerebras GPT-OSS + Nous
  `:free` routes), paid routes (Nous Step/Solar/LongCat/Luna/Sonnet + OpenRouter
  Gemini 3.7 Flash / GPT-5.6 Sol Pro) with the fixed Nous discounts (Luna 80%,
  Sonnet 20%). Free-first task ordering; paid escalation `DENY` by default,
  gated by `PINEAL_ALLOW_PAID_ESCALATION=1`.
- **`quota_governor.py`** — header-aware RPM/TPM/RPD/TPD accounting seeded from
  the account-verified Groq (30 RPM / 14,400 RPD) and Cerebras (5 RPM / 30K TPM
  / 1M TPD) quotas. Unknown quota is reported `unknown`, never unlimited.
- **`routed_chat.py`** — `default_routing_mapping` is now policy-driven (free
  first); Nous connections are policy-gated so catalog presence alone never
  turns a paid route into an executable fallback; the executor enforces the
  FINAL policy before leasing, records quota state, and annotates
  `fallback_reason`/`quota_status` on every call.
- **`llm_gateway.py`** — telemetry contract extended (`requested_model`,
  `actual_model`, `fallback_reason`, `quota_status`); provider default-model
  substitution is denied; `query_chain`/`query_json_chain` now fall back only
  on transient errors (and genuine JSON parse/schema failures) — never on auth,
  spend-cap, unknown-pricing, paid-escalation, or model-unavailable.
- **`config/provider_catalog.json`** — added `nous-research` provider with
  verified free + paid models and effective Nous prices.
- **`scripts/verify_openrouter_catalog.py`** + CI step — deterministic local
  catalog contract gate (plus a live OpenRouter cross-check when a key is
  present). OpenRouter absence is never treated as Nous evidence.

### FINAL policy hardening (review follow-up)

- Canonical policy key is now `model@provider`; `routed_chat.default_routing_mapping`
  translates to the catalog's `provider/model` form at the boundary.
- Fail-closed by construction: `is_paid`/`is_free` treat unknown model/provider
  as DENY (never free, never order-dependent); `verification_status` defaults to
  `unverified` (opt-in); `quota_limit()` raises `UnknownQuotaDenied` for unknown
  quota instead of allowing an `inf`/unlimited interpretation.
- Import-time `_validate_catalog()`: every task-group candidate must resolve to a
  verified spec (no silent catalog-drift swallowing), forbidden aliases and
  vision/video capability cross-checks are enforced.
- `assert_executable(explicit=True)` is audited (logs a warning) and a `frontier`
  tier requires **both** `PINEAL_ALLOW_PAID_ESCALATION=1` and `explicit=True`.
- Nous Step 3.7 Flash catalogued as vision-capable (matches the policy's
  vision/video task groups).

### Cross-audit fixes + consolidated verdict

- **JSON repair exception scope** (`llm_gateway.query_json`): repair path now catches only parse/schema failures (`ValueError`, `ValidationError`, `TypeError`, `KeyError`, `JSONDecodeError`). Transport/auth/spend-cap/cancellation errors re-raise immediately — no second paid repair call on a dead upstream.
- **Depth failure wiring** (`task_executor`): `depth_analyst` success/failure is recorded on `status.agent_runs` + `evidence_chain` (execution_failure) + explicit `depth_report.available=False` metadata. Silent WARNING-only gaps removed so DecisionEngine sees the miss.
- **Prompt injection close-out**:
  - `autonomous_verifier`: bio + search snippets fenced as `<UNTRUSTED_*>`; model told content is not instructions.
  - `memory_injector`: operator rules no longer claim "KUTSAL OVERRIDE"; sanitised, fence-safe, injection-pattern rejected; host system prompt remains supreme.
- **Authentic vector epistemic marker**: successful vectors stamped `_epistemic=model_estimate` + status metadata; unavailable path carries `epistemic=unavailable`.
- **Slug drift fix**: docs/`.env.example`/`router.example.json`/`interpreter_agent` defaults aligned to the 2026-09-02 decision matrix (`claude-sonnet-5` / `deepseek-v4-flash` / `gemini-3.7-flash` / `grok-4.6`). Retired promo slugs (`solar-pro4`, `ling-3.0-flash`, `glm-5.2`) are not bare defaults.
- **G7 release gates**: `.github/workflows/release-gates.yml` (kaynak kopya: `release/release-gates.yml` — GitHub App `workflows` izni olmadığı için bu PR workflow dosyasını doğrudan yazamaz; yazma yetkili aktör `cp release/release-gates.yml .github/workflows/release-gates.yml` ile ekler) (workflow_dispatch only) wires Gate A live LLM E2E + Gate B docker/Chromium smoke. Docs already described Section 12; workflow file is now present.
- Audit reports: `docs/reports/CROSS_AUDIT_FIXES_2026-09-02.md`, `docs/reports/SON_HUKUM_DENETIM.md`.
- Verification: **645 passed, 2 skipped** · **%83.32** coverage · ruff clean.

### Release gates (G7)

- Added `.github/workflows/release-gates.yml` (kaynak kopya: `release/release-gates.yml` — GitHub App `workflows` izni olmadığı için bu PR workflow dosyasını doğrudan yazamaz; yazma yetkili aktör `cp release/release-gates.yml .github/workflows/release-gates.yml` ile ekler) — manual-only (`workflow_dispatch`) wiring for the two open rc.2 live gates; never triggers on push/PR (Gate A is a paid live LLM call); single-flight concurrency (no cancellation of a running paid gate).
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
- A live third-party OpenRouter credential gate remains operator-triggered; the mandatory hermetic E2E uses the actual HTTP/SDK/runtime path against a deterministic local provider and does not claim external-provider availability.## [Unreleased] - 2026-09-04 (routing-hardening)
- O-1: substitution denials now carry structured requested_model/actual_model call-log
  fields in BOTH query() and legacy chat_completion (single-log doctrine kept);
  ModelSubstitutionDeniedError introduced; Aspasia TelemetryReader reads fields first,
  regex only as legacy fallback.
- O-2: bounded transient-only provider health breaker (env-tunable threshold/cooldown);
  consumed by agent_route_variants; policy denials and auth errors never counted;
  provider_health() surfaces remaining cooldown, Aspasia digest gains a SAĞLIK line only
  while blocked.
- O-3: model ladder filters direct candidates by RouteSpec.capabilities against
  required_capabilities (single source); quota/api-key isolation unchanged.
- O-4: guard test asserts ROUTES<->provider_catalog effective-price equality for every
  dual-priced route (precedence untouched; ROUTES remains SoT).
- Evidence: targeted 170/170, full suite 809P/0F/0S, ruff clean; proofs use fake transport
  only (no live/paid calls). CI not verified (session push-disabled). See
  docs/reports/ROUTING_HARDENING_2026-09-04.md.


