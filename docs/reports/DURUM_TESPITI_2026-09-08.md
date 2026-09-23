# PINEAL — TEPEDEN TIRNAĞA DURUM TESPİTİ
**Denetçi:** Bağımsız (önceki hiçbir rapora/changelog'a güvenilmedi; her iddia canlı ölçümle doğrulandı)
**Tarih:** 2026-09-08 · **Kapsam:** HEAD `85839da` tam çalışma ağacı
**Kod değişikliği:** HİÇBİRİ YAPILMADI (`git status` temiz). Bu rapor yalnızca ölçüm + teşhistir.

---

## 1. Zemin: HEAD, commit ilişkisi, CI gerçek durumu (kanıtlı)

### 1.1 HEAD ve köken

| Soru | Ölçüm | Kanıt |
|---|---|---|
| HEAD SHA | `85839dac0ae83f0d36da5004e5d2bce83c9808cb` | `git log -1` |
| Tarih / yazar | 2026-09-08 06:09:20 +0300, Salim Gümüş | `git log -1 --format=fuller` |
| Mesaj | `feat(routing): integrate task_routing.json with pure resolver and gateway precedence` | aynı |
| Branch | `arena/01a07f2a-pineal-clean` (== `origin/main` == `main`, hepsi `85839da`) | `git branch`, `git ls-remote origin` |
| Tarih derinliği | Shallow clone'dı; `git fetch --unshallow` ile 369 commit geldi | `git rev-list --count HEAD` |

### 1.2 HEAD ↔ `1f1ea89` ("production-ready, CI green" olarak kapatılan commit)

- `1f1ea892ce0e1480731a226decef2a972232ab1b` — **2026-09-06 00:55:31 UTC**, mesaj `S1: production spend-cap fail-closed (PRODUCTION_SPEND_CAP_REQUIRED) + N7 rate-limit identity docs`.
- **HEAD, `1f1ea89`'un 27 commit alt torunudur** (merge-base == `1f1ea89`; `git rev-list --count 1f1ea89..HEAD` = 27). Alakasız dal değil, üzerine bina edilmiş.
- `1f1ea89`'da CI **gerçekten yeşildi**: GitHub Actions run **#503 / id `34002549846`** → `frontend: success, backend: success, rust-core: success, android: success, smoke: success`. Yani kapanış iddiası o an için doğruydu.
- HEAD'de CI **kırmızı** (run **#55 / id `34182589597`**, 51 dk önce tamamlanmış):

| Job | Sonuç | Açıklama |
|---|---|---|
| backend | **failure** | adım **"Lint with ruff"** exit 1 (test adımına hiç geçilmedi) |
| rust-core | **failure** | adım **"Cargo test"** exit 101 ("Cargo check" PASS) |
| frontend | success | — |
| android | success | — |
| smoke | skipped | `needs: [backend, frontend]` — backend kırmızı olduğu için hiç koşmadı |

### 1.3 CI'ın yerel birebir kopyası (her leg ayrı)

CI komutu: `pip install -r requirements.txt ruff pytest pytest-asyncio pytest-cov` → `ruff check .` → `pytest -q -p no:cacheprovider --cov=agent_core --cov=backend --cov-report=term-missing:skip-covered --cov-fail-under=80` (+ frontend `npm ci && npm run check && npm run build`, smoke uvicorn, rust `cargo check --all-targets && cargo test --locked`, android gradle). Tümü aynen çalıştırıldı:

| Leg | Yerel sonuç | Çıktı kanıtı |
|---|---|---|
| backend lint (`ruff check .`) | **FAIL** | exit 1 — `F401` `pathlib.Path` unused (`tests/unit/test_llm_gateway_rtk_integration.py:3`) + `F401` `_RTK_POLICY_PATH` unused (`:5`) → "Found 2 errors" |
| backend pytest + %80 kapı | **PASS** | `1089 passed, 3 skipped` · `TOTAL 11414 stmts, 85.68%` · "Required test coverage of 80% reached." (68.6 sn) |
| tests/audit (N1–N6/P1-7 türü kapı testleri) | **PASS** | `84 passed` |
| frontend `npm run check` | **PASS** | `svelte-check found 0 errors and 0 warnings` |
| frontend `npm run build` + dist grep | **PASS** | 118 modules, `DIST_GREP_OK` (`PINEAL-HERETIC` dist/assets içinde) |
| smoke (uvicorn, `PINEAL_ENV=development`) | **PASS** | `/api/telemetry` 200 · `/` içinde `id="app"` · `POST /api/aspasia/chat` → 200 · `/health` → `status=ready` |
| rust `cargo test --locked` | **NOT EXECUTABLE** (ortam) | `static.rust-lang.org` TLS engelli; apt cargo 1.63 `Cargo.lock` v4'ü okuyamaz. **Ama hata kod okumasıyla deterministik** (bkz. §2.2) |
| android | **NOT REPRODUCIBLE** (JDK/Android SDK yok) | GitHub HEAD run'ında `android: success` — CI kanıtı kullanıldı |
| "Verify provider catalog contract" adımı | NOT EXECUTED | `OPENROUTER_API_KEY` secret gerektirir; HEAD run'ında backend lint'te durduğu için hiç koşmadı |

> **Sonuç:** HEAD'de CI **KIRMIZI**. Yerelde yeniden üretilen birebir hata = CI'ınki. Kod tarafı (pytest/cov), frontend ve smoke legleri bağımsız çalıştırıldığında yeşil; kırık olan **lint** ve **rust test** kapılarıdır.

---

## 2. Regresyon var mı — EVET. Ne zaman/nerede girdi

### 2.1 İki kapı da aynı commit'te kırıldı: `024c82b0`

`git log --oneline d81ca594..HEAD` → 6 commit (hepsi main'de, Salim Gümüş):

```
85839dac feat(routing): integrate task_routing.json ...
f6346264 test(rtk): lock vision task explicitly ...
a0bbbb59 test(rtk): strengthen bypass lock ...
95bfc51e test(rtk): lock default bypass contract ...
0f2a564c fix(rtk): add human_behavior to policy bypass ...
024c82b0 feat(rtk): integrate token_compressor mirror pattern ...   ← KIRILMA NOKTASI
d81ca594 Merge pull request #70 ... (SON YEŞİL)
```

Kanıt zinciri (her commit'te `ruff` çalıştırıldı):
- `d81ca594` (merge, HEAD'in babası): **ruff PASS** ("All checks passed!")
- `024c82b0` (2026-09-08 05:08:17 +0300): **ruff FAIL** (dosya bu commit'te 2 kullanılmayan import ile eklendi)
- `0f2a564c` → `85839da` (5 commit): **ruff FAIL** (her biri ayrı çalıştırıldı)
- `1f1ea89` + `024c82b0` arası tüm ara noktalarda ruff PASS → regresyon tam `024c82b0`'de başladı.

GitHub Actions da aynı hikayeyi doğruluyor: `024c82b0` run `34179081633`'ten itibaren **6 ardışık main push'u kırmızı** (sonuncusu HEAD `34182589597`); kırılmadan önceki son yeşil main run'ı `34169901688` (merge #70). **"Ne zamandır kırık": 2026-09-08 05:08 (+03) — rapor anında ~1 saattir; 6 commit boyunca kırmızı push'lanmış.**

### 2.2 Rust kapağının kırılma nedeni (deterministik, kod okumasıyla kanıt)

`rust_core/tests/purity_scan.rs` (`024c82b0`'de eklenen yeni test) şunu iddia eder: `src/token_compressor.rs` içinde `"std::fs"` geçmemeli (`assert!(!source.contains(token))`). Ancak aynı commit'in eklediği `rust_core/src/token_compressor.rs` **iki yerde** `std::fs` içerir:
- satır 39 (yorum: `"std::fs KULLANILMAZ — testler hariç"`)
- satır 192 (`use std::fs;` — `#[cfg(test)] mod tests` içinde, fixture okumak için)

Test dosyayı **yorumlar ve `#[cfg(test)]` bölgesi dahil** ham metin olarak taradığı için assert her koşuda patlar → `cargo test` exit 101. CI'ın HEAD run'ında tam bu adım kırmızı (`gh run view --job …`: "Cargo check" ✓, "Cargo test" ✗ exit 101). `git diff 024c82b0 HEAD -- rust_core/` boş → Rust leg'i `024c82b0`'den beri aynı nedenle kırmızı. (Not: Python tarafındaki simetrik test `test_token_compressor_purity.py` AST tabanlıdır ve `std::fs` kelimesini yasaklamaz — bu yüzden Python paketi yeşil, Rust kapağı kırmızı.)

### 2.3 Sınıflandırma: regresyon mu, yanlış kapanış mı?

**Regresyon.** `1f1ea89` kapanışı o an doğruydu (run #503 5/5 yeşil). `024c82b0` sonrası iki kapı açıldı. Kapanış raporu yanlış değildi; sonraki commit'ler kapıyı kırdı ve kırmızı CI'la main'e girdi.

---

## 3. Ölü kod / registry envanteri (uçtan uca çağrı zinciri izlendi)

### 3.1 `PinealExecutor.agents` registry'si (task_executor.py:66-93) — HEPSİ ÇAĞRILIYOR

| Registry anahtarı | Sınıf | Nasıl tetikleniyor | Ölü? |
|---|---|---|---|
| `passion_mapper` | PassionMapperAgent | `CognitiveRouter` rotası (has_target + goal; `profile_analysis` şemsiyesi) → ana döngü `agent.execute(...)` → evidence_chain + `HolisticProfile.passions` | HAYIR |
| `friction_detector` | FrictionDetectorAgent | aynı döngü → `input_data["frictions"]` + `holistic_profile.frictions` | HAYIR |
| `cognitive_profiler` | CognitiveProfilerAgent | aynı döngü → `input_data["cognitive"]` + `holistic_profile.cognitive` | HAYIR |
| `human_behavior` | HumanBehaviorAnalyzer | router (goal-selected) → döngü → target_analysis + target vektörü | HAYIR |
| `mirror_truth` | MirrorOfTruth | router (has_user) → döngü → user_mirror + user vektörü; `critical_agents` listesinde | HAYIR |
| `resonance_calc` | ResonanceCalculator | router (has_user+target) → döngü; <0.70 → `halted_frequency` | HAYIR |
| `pattern_interrupt` | PatternInterrupt | router → **deferred** alt-döngü (bağımlılık sıralı) | HAYIR |
| `resonance_synthesizer` | ResonanceSynthesizerAgent | router → deferred alt-döngü → `AuthenticBridge` | HAYIR |
| `autonomous_verifier` | AutonomousVerifier | router (has_target, her planda — policy bacağı) → döngü | HAYIR |
| `authenticity_auditor` | AuthenticityAuditorAgent | router: yalnız `visual_evidence` var ise (kanıt-yoksa dürüst atlama, sahte denetim üretilmez) | HAYIR (koşullu, tasarım) |
| `osint_investigator` | OsintInvestigatorAgent | router'da DEĞİL; ana döngü **sonrası** sabit blok (`_execute_task_impl` ~satır 855) | HAYIR |
| `shadow_executor` | ShadowExecutor | aynı sabit post-loop bloğu | HAYIR |
| `depth_analyst` | DepthAnalyst | aynı sabit post-loop bloğu (depth_report + quote_guard) | HAYIR |
| `interpreter` | InterpreterAgent | **yalnız** `ENABLE_INTERPRETER=true` ise registry'ye eklenir; router da ayrıca `PINEAL_ROUTE_INTERPRETER` ister — varsayılan ikisi de kapalı | Tasarım gereği kapalı |

Router'ın üretebileceği her isim (`GOAL_FOCUS` dahil: autonomous_verifier, human_behavior, passion_mapper, friction_detector, cognitive_profiler, authenticity_auditor, resonance_calc, pattern_interrupt, resonance_synthesizer) registry'de var → `KeyError` rotası (`task_executor.py:632`) çalışma zamanında tetiklenmiyor. **Registry'de durup hiç çağrılmayan ajan yok.**

### 3.2 Registry dışı modüller

- **7 pillar motoru**: `PillarOrchestrator.run` → `asyncio.gather` ile frequency/seismos/void/strata/gravity/pulse + key — 7'si de gerçekten çağrılıyor (pillar_orchestrator.py:49-66). `rust_core` Python ürün hattına bağlı değil (dokümanla uyumlu, CI'da deneysel kapak).
- **LilithGrowthAgent**: executor registry'sinde yok; yalnız `run_lilith.py` CLI'ı. Ölü değil, ürün-dışı bilinçli.
- **Servis taraması** (69 modül, import-graf analizi): `run_scraper` hariç her modül en az bir çağırana sahip; `run_scraper` CLI (`sys.argv`) ve testlerce kullanılıyor. Kayda değer ölü kod bulunmadı.

### 3.3 P1-7 paterninin (tanımlı ama çağrılmayan kapı) sistematik taraması

- **Ana güven kapısı ÇAĞRILIYOR**: her routed ajandan sonra `uncertainty.evaluate(result, agent_name)` + `check.confidence < agent_cfg.min_llm_confidence` halt (task_executor.py:645 ve deferred döngüde tekrar) — P1-7 paterni bu yolda YOK.
- **AMA config seviyesinde kalıntı var** (aynı aile, düşük şiddet): `config/decision_config.yaml` şu anahtarları beyan ediyor ama `DecisionConfig.load()` (config_loader.py:44-77) **bunları hiç okumuyor**:
  - `pipeline.default.require_data_confidence: true` → hiçbir kodda okunmuyor
  - `agents.mirror_truth.min_final_confidence: 0.65` → hiçbir kodda okunmuyor
  - `agents.osint_investigator.fallback_enabled: true` → hiçbir kodda okunmuyor
  - `agents.mirror_truth.critical: true` → loader sadece `pipeline.critical_agents` listesini kullanıyor (mirror_truth zaten listede; agent-seviyesi bayrak atıl)
  
  Yürürlükteki gerçek kapılar (`min_data_score`, `min_llm_confidence`, `graceful_degradation`, `data_confidence=False` yolu) kodda doğrulanmıştır. Etki güvenlik değil, "beyan edilen ama uygulanmayan ayar" tutarsızlığıdır.

### 3.4 Frontend ↔ backend sözleşmesi (F3 paterni taraması)

- Frontend'in kullandığı **tüm** endpoint'ler backend'de mevcut: `POST /api/initiate`, `POST /api/aspasia/chat`, `POST /api/aspasia/command`, `GET /api/telemetry`, `GET /api/tasks`, `DELETE /api/tasks/{id}`, `POST /api/tasks/{id}/cancel`, `WS /ws/{client_id}` → 8/8 eşleşti (listeler karşılaştırıldı, eksik yok). F3 tarzı **eksik endpoint regresyonu YOK**.
- **AMA görüntü sözleşmesi sapmış** (kozmik değil, kozmetik ama ölçülebilir): `frontend/src/components/UnifiedCompactPanel.svelte:66-80` "13 AJAN LİSTESİ" model etiketleri, yürürlükteki model SoT'si ile **13 satırdan 6'sında uyuşmuyor** (karşılaştırma: UI satırı ↔ `AGENT_CHAINS` + `config/task_routing.json` delta'sı):
  - `passion_mapper`: UI `claude-sonnet-5 / gemini-3.7-flash` ↔ kod `gemini-3.7-flash / deepseek-v4-flash` **uyumsuz**
  - `cognitive_profiler`: UI `claude-sonnet-5 / grok-4.6` ↔ kod `gemini-3.7-flash / deepseek-v4-flash` **uyumsuz**
  - `autonomous_verifier`: UI `deepseek-v4-flash/claude…` (extract ile judgment karıştırılmış) ↔ kod judgment `claude / grok` **uyumsuz**
  - `human_behavior` yedek: UI `deepseek-v4-pro` ↔ yürürlükte (task_routing delta) `gemini-3.7-flash` **uyumsuz**
  - `pattern_interrupt`: UI `deepseek-v4-flash` ↔ kod `gemini-3.7-flash` **uyumsuz**
  - `authenticity_auditor`: UI `gemini/claude` ↔ kod `deepseek-v4-flash/gemini/claude` **uyumsuz** (birincil farklı)
  - `friction_detector`, `resonance_synthesizer`, `osint_investigator`, `depth_analyst` (delta sonrası), `mirror_truth`, `vision_analyzer`: **uyumlu** ✓
  - "Kod 09-02 matrisinde passion/cognitive'ı ucuz katmana çekti" (llm_gateway.py:346-349 yorumu) — UI bu taşımayı yansıtmıyor.

---

## 4. Mimari MERGE iddiasının doğrulanmış hali (blast radius'lı)

Önceki oturum iddiası: *"PassionMapper, FrictionDetector, CognitiveProfiler aynı iskeleti paylaşıyor → MERGE edilmeli."* Kör kabul edilmedi; üç ayrı ölçüm yapıldı.

### 4.1 İskelet gerçekten aynı mı? — KISMEN EVET, ama üçü de eşit değil

Kontrol akışı üçünde de birebir: `execute(payload)` → bio/posts/visual_evidence çıkar → boş-veri guard (`fallback_reason="no_target_data"`) → prompt → `llm_gateway.query_json_chain(task="depth", temperature=0.3)` → `data_confidence`/`fallback_reason` post-processing → `except` → `llm_unavailable` fallback. Nicel ölçüm (isim/şema/prompt maskelenmiş difflib):

| Çift | Normalleştirilmiş benzerlik | Ham benzerlik |
|---|---|---|
| passion ↔ friction | **0.842** | 0.716 |
| passion ↔ cognitive | **0.697** | 0.593 |
| friction ↔ cognitive | **0.667** | 0.613 |

Yani "aynı iskelet" iddiası yön olarak doğru ama abartılı: passion+friction en yakın çift; cognitive (farklı şema alanları, `evidence_quotes` yok, opsiyonel `humor_style`) daha uzak.

### 4.2 KRİTİK SORU — önceki raporun atladığı: prod'da bağımsız tetikleniyorlar mı, model/maliyet profilleri farklı mı?

**Evet, üç kanıt katmanı:**

1. **Routing/tetikleme bağımsız**: Router'da ayrı goal kapıları (`GOAL_FOCUS`: `passion_friction` = passion+friction; `cognitive_tone` = cognitive; `profile_analysis` şemsiyesi üçünü de seçebilir) ve ayrı `RoutePlan` girdileri. Executor'da her biri ayrı `AgentRun`, ayrı `evidence_chain` kaydı, ayrı uncertainty/data-score değerlendirmesi (agent_name anahtarlı) üretir.
2. **Model/maliyet profilleri GERÇEKTEN farklı** (llm_gateway.py:339-371 `AGENT_CHAINS`; bu 3 lens için `task_routing.json` delta'sı yok → matris SoT'si yürürlükte):

| Lens | Zincir | Maliyet (in/out $/MTok, MODEL_PRICING) | Katman |
|---|---|---|---|
| passion_mapper | gemini-3.7-flash → deepseek-v4-flash | 0.75/3.75 → 0.0679/0.168 | ucuz |
| cognitive_profiler | gemini-3.7-flash → deepseek-v4-flash | aynı | ucuz |
| friction_detector | **claude-sonnet-5 → deepseek-v4-pro** | **2/10 → 0.4679/0.9358** | **pahalı/üst akıl** |

   Kod yorumu bunu bilinçli ilan ediyor: *"Karar matrisi: Passion/Cognitive/Audit hızlı & ucuz katmana çekildi, Friction/HumanBehavior/Aspasia/Lilith yüksek akıl katmanında."* **3'lü kör merge, friction'ın bilinçli premium katmanını sessizce ezer** — maliyet ve kalite profili değişir. 2'li merge (passion+cognitive) model profili açısından savunulabilir; friction hariç tutulmalı ya da merge parametrik (lens→zincir eşlemesi korunur) olmalı.
3. **Config kimliği ayrı**: `decision_config.yaml`'da yalnız `passion_mapper`'ın özel eşikleri/ağırlıkları var (0.57/0.70 + field_weights + `critical_agents` listesinde). `friction_detector` ve `cognitive_profiler` genel varsayılanı (0.60/0.65) kullanır. Merge, agent_name kimliğini korumazsa bu ayrım da kaybolur.

### 4.3 Blast radius (ölçüldü: isim bazında referans sayıları)

| Yüzey | passion_mapper | friction_detector | cognitive_profiler |
|---|---|---|---|
| Python dosyası | 15 | 20 | 15 |
| Frontend | 1 (UnifiedCompactPanel satırı: isim/renk/glyph/UI model etiketleri) | 1 | 1 |
| Doküman (.md) | 4 | 3 | 5 |
| Config | 1 (`decision_config.yaml`) | 0 (yok = varsayılan eşik) | 0 |
| Test dosyası | 10 | 14 | 10 |

Ek kontrat yüzeyleri (isim geçmese de merge'den etkilenir): `HolisticProfile.passions/frictions/cognitive` alanları (memory_models.py:76-88), executor'ın `holistic_profile` kurulum bloğu (task_executor.py:~1090), `input_data["passions"/"frictions"/"cognitive"]` ara anahtarları, GOAL_FOCUS tuple'ları, `tests/unit/test_config_contract.py` (şema ↔ ağırlık sözleşmesi), `live_llm_gate.py` zincir dizesi. Toplam etki ≈ 31-38 isim-referansı + 3 API şema alanı + UI 3 satır + 3 config/gate kimliği. **"134 referanslı client_id" vakası kadar büyük değil ama aynı sınıftan**: merge kararı öncesi bu yüzeylerin tamamı taşınmadan yapılırsa UI/API/config kontratı kırılır. Merge ancak parametrik "lens" mimarisi + zincir/şema/eşik enjeksiyonu + isim geriye-dönük alias'ları ile risksizdir; düz kopya birleştirme **önerilmez**.

### 4.4 MirrorOfTruth "core frequency" iddiası — DOĞRU, ama karar zinciri farklı bir aileden

- `_extract_core_frequency` gerçekten **`Counter(words).most_common(3)`** seviyesinde (mirror_truth.py:121-140; `re.findall(r"\b\w+\b")`, >3 harf, `"_"` ile birleştirme); `_find_anchors` da aynı (`most_common(3)` + `_anchor`). "Counter(most_common(n))" iddiası **teyit edildi**.
- **Ama karara giden sayı o değil**: deterministik frekans yalnız prompt sinyali; asıl karar sayıları `_calculate_authentic_vector`'un **LLM'den ürettiği** `depth`/`energy` float'ları → `ResonanceCalculator._cosine_similarity` (2 boyut) → `compatibility_score` → `<0.70 → halted_frequency`. Yani "LLM hipotezini cosine ile sayıya çevirme" ailesi **yapısal olarak hâlâ mevcut** — AuthenticVector sorunuyla aynı aile, teyit edildi. Nötrleştiriciler ölçüldü: vektörler `_epistemic=model_estimate` damgalı, kullanılamaz vektör `None` + `AUTHENTIC_VECTOR_UNAVAILABLE` (sahte default üretilmiyor — AUTHENTIC_VECTOR_FIX_REPORT ile uyumlu), ResonanceCalculator eksik boyutta hata fırlatıyor. Özet: **eski "sahte vektör" kapanmış; "tahmin→karar" epistemik kalıntısı dürüstçe etiketlenmiş halde duruyor** — kapatılmış iddia edilemez, ama gizli de değil.

---

## 5. Güvenlik/performans regresyon taraması (canlı doğrulandı)

| Kapalı kalem | Durum | Canlı kanıt |
|---|---|---|
| **Auth fail-closed** (P2-10) | ✅ HÂLÂ KAPALI | uvicorn `PINEAL_ENV` boş + token yok → **exit 3**, log `PRODUCTION_AUTH_REQUIRED: PINEAL_TOKEN must be configured...`, "Application startup failed. Exiting". `_is_production()` yalnız açık dev listesini dev sayıyor (security.py:75-83). |
| **Spend-cap fail-closed (S1)** | ✅ HÂLÂ KAPALI | `PINEAL_ENV=production` + token + cap 0 → **exit 3** `PRODUCTION_SPEND_CAP_REQUIRED`; cap 50 → boot, `/health` `ready`. (security.py:110-125; api.py lifespan raise) |
| **Rate-limit kimlik tutarlılığı (P1-18a)** | ✅ HÂLÂ KAPALI | `request.state.rate_identity = sha256(presented_token or client_ip)[:16]` (api.py:250-253) — client_id ASLA rate anahtarı değil; handler'lara middleware'den geçer. Kovalar: `api(300/60) initiate(5/60) aspasia(20/60) experimental(10/60) openai(60/60)` (api.py:327-338). |
| **Bare except temizliği (P1-18c)** | ✅ HÂLÂ KAPALI | `grep "except:"` → 1 sonuç, o da P1-18c'yi anlatan **yorum** (api.py:1553). Gerçek bare except: **0**. |
| **Sınırsız büyüme paternleri** | ✅ HÂLÂ KAPALI (hepsi tavanlı/TTL'li) | odalar: `_MAX_ROOMS` 512 + `_ROOM_TTL` 1800 sn + aktif görevli/WS'li oda dokunulmaz (api.py:640-710); dialogue: `max_sessions` 512 + TTL 1800 + eviction (dialogue_manager.py:22-65); rate bucket: `_MAX_RATE_BUCKETS` 100k + periyodik sweep (api.py:356-420); `call_log` 500 kayıtta kesilir (llm_gateway.py:584-586); response_cache `PINEAL_CACHE_MAX_ROWS` 50k; canonical_memory `_locks` waiters==0'da silinir (canonical_memory.py:61-78); learnings yedeği `BACKUP_KEEP` 5 (api.py:1955). |
| **N1** (aktif görev trim'i terminal-only + 503 ACTIVE_TASKS_FULL) | ✅ KAPALI | api.py:1259-1326 `_snapshot_status()` `.value` tabanlı; aktif kayıt terminale düşmeden silinmez. Audit testleri: 84/84 PASS. |
| **N2** (RecursionError → quarantine) | ✅ KAPALI | api.py:1921 catch tuple'ında `RecursionError`. |
| **N3** (yedek birikimi sınırlı) | ✅ KAPALI | api.py:1955 `keep = max(1, env BACKUP_KEEP=5)`. |
| **N4** (host substring → tam eşleşme) | ✅ KAPALI | platform_registry.py:61-71 `_is_instagram_host`: `host == "instagram.com" or host.endswith(".instagram.com")`. |
| **N5/N6/N7** (doküman maddeleri) | ✅ KAPALI | api.py:2147 `target_message: str = Field(max_length=32_000)`; `.env.example` PINEAL_TOKEN kimlik dokümanı mevcut. |

**Bu bölümde açılmış hiçbir kalem yok.** §1-2'deki regresyonlar bu güvenlik kalemlerinden bağımsızdır (lint + rust test kapağı).

---

## 6. "Şu an gerçekte nerede olduğumuz" — tek paragraf

Repo, "1f1ea89'da CI yeşil ve production-ready" kapanışından sonraki 27 commit içinde **CI'ı kırmızıya düşüren iki regresyonla** duruyor: `024c82b0` (2026-09-08 05:08) ile backend lint kapağı (2 kullanılmayan import) ve rust-core test kapağı (purity_scan'ın kendi test ettiği dosyada `std::fs`'i yasaklayıp o dosyanın test modülünde `std::fs` kullanması — her koşuda patlayan bir assert) kırıldı ve **6 ardışık commit kırmızı CI ile main'e girdi** (HEAD run #55: backend FAIL, rust-core FAIL, smoke hiç koşmadı); yerelde aynı komutlarla doğrulandı — kod/test tarafı ise sağlam: 1089 test geçiyor, %85.68 coverage, frontend check/build ve bağımsız smoke leg'i yeşil, güvenlik kalemlerinin tamamı (auth ve spend-cap fail-closed dahil) canlı boot testleriyle hâlâ kapalı, executor registry'sinde ölü ajan yok, frontend-backend endpoint sözleşmesi tam. Mimari cephede ise "üç lens aynı iskelet, merge edilmeli" iddiası yön olarak doğru ama kör merge için yetersiz: passion+cognitive aynı ucuz model zincirini paylaşıyor, friction bilinçli olarak pahalı üst-akıl katmanında ve üçü de routing/config/evidence/UI yüzeylerinde ayrı kimlikler (~31-38 referans + API şema alanları + UI satırları) taşıyor; ayrıca UI'ın 13 ajanlık model etiketi 6 satırda yürürlükteki model SoT'sinden sapmış ve `decision_config.yaml`'daki birkaç kapı anahtarı (`require_data_confidence`, `min_final_confidence`, `fallback_enabled`, agent-level `critical`) kod tarafından hiç okunmuyor. Özet: **çekirdek mühendislik ve güvenlik sağlam ve doğrulanabilir durumda; ama "CI green / production-ready" iddiası şu an doğru değil — iki kapı ~1 saattir kırmızı ve bu durumla yayınlanmış son 6 commit var.**

---

## 7. Fix önerileri (öncelikli — UYGULANMADI, yalnızca öneri)

**P0 — CI'ı yeşile döndür (regresyonun kendisi):**
1. `tests/unit/test_llm_gateway_rtk_integration.py:3,5` — kullanılmayan `pathlib.Path` ve `_RTK_POLICY_PATH` importlarını kaldır (2 satır; ruff `--fix` yeter).
2. `rust_core/tests/purity_scan.rs` — purity taramasını `#[cfg(test)]` bölgesini (ve/veya yorumları) hariç tutacak şekilde düzelt ya da "std::fs" token'ını kaldırıp test-only kullanımı açıkça kabul et; Python'daki simetrik test (AST tabanlı, sadece gerçek importları sayan) doğru modeldir — Rust tarafı ona hizalanmalı.
3. Düzeltmeyi tek commit'te yapıp main'i yeşil run ile doğrula (backend+rust-core+smoke dahil 5/5).

**P1 — 1-2 gün:**
4. UI ajans destesi (`UnifiedCompactPanel.svelte:66-80`) model etiketlerini yürürlükteki SoT'ye hizala (passion/cognitive → gemini-flash/deepseek-flash; verifier judgment → claude/grok; human_behavior backup → gemini; pattern_interrupt backup → gemini; authenticity birincil → deepseek-flash) veya "gösterge amaçlı, SoT değil" notu ekle — F3 ailesi tekrar kırılmasın diye mekanik bir kontrat testi önerilir.
5. `decision_config.yaml`'daki okunmayan anahtarları ya `DecisionConfig.load()`'da gerçekten uygula ya da YAML'dan kaldır (tek doğruluk kaynağı iddiası için).
6. Merge kararı verilecekse: passion+cognitive model profili açısından birleştirilebilir, friction **ayrı kalmalı** ya da tamamı parametrik lens mimarisiyle (zincir+şema+eşik enjeksiyonu, isim alias'ları) taşınmalı; §4.3'teki yüzeylerin tamamı taşınmadan merge yapılmamalı.

**P2 — dokümantasyon/kalıntı:**
7. "LLM tahmini → cosine → halted_frequency" epistemik kalıntısını (dürüstçe etiketlenmiş durumda) bir mimari notla kalıcılaştır; MirrorOfTruth'un Counter tabanlı frekansı ile karar sayıları arasındaki farkı README'de açıkla.
8. Son 6 commit'in kırmızı CI ile girildiği gerçeğini changelog'a işle (yeniden "green" denmemesi için).

*Ölçüm sınırları:* android leg'i yalnız GitHub Actions kanıtıyla (HEAD run'ında success); "Verify provider catalog" adımı secret'sız yerelde çalıştırılamadı; rust leg'i toolchain indirme engeli nedeniyle yerelde koşulamadı ancak hata deterministik kod okumasıyla + CI adım çıktısıyla kanıtlandı.
