# PINEAL — BAĞIMSIZ FORENSIC DENETİM RAPORU (ZERO-KNOWLEDGE / CODE-FIRST)

- **Denetim tarihi:** 2026-09-08
- **Denetlenen sürüm:** repo HEAD `2006f696` (branch `arena/01a07f2a-pineal-clean`)
- **Yöntem:** PASS 1–9; README/raporlar **kanıt değil**; yalnızca kod + config + CI + çalıştırma + test.
- **Kapsam dışı / UNKNOWN listesi:** rapor sonunda (madde 11). Dolar tahmini üretilmedi; yalnızca kanıtlanabilir oranlar/koşullar verildi.

> **KABUL / DONDURMA (2. ajan, 2026-09-08):** rapor **2 satır eklemeyle KABUL**, veto yok, **DONDURULDU** (eklenen satırlar: §11 restart-runtime davranışı + paralel görev/çok-oda yük davranışı). Veto hükümleri: (1) "P0 yok" AYNEN; (2) F1/F2 **MEDIUM** AYNEN; (3) TOP 10 sıralaması (#3 UI > #4 kaçak > #5 katalog) AYNEN; (4) UNKNOWN'a 2 satır eklendi (Android satırı zaten yeterli). Sonraki değişiklik yalnız yeni karar turuyla. FAZ-3 sicili: `FAZ3_GIRDI_2026-09-08.md`.
>
> **ERRATUM + FAZ-2.1 (2026-09-08, komutan emri):** model taşıyan sağlayıcı sayısı **5**'tir (openrouter 9, nous-research 8, deepseek 3, groq 2, cerebras 1) — tablolardaki "6" yazımı düzeltildi. Dondurma sonrası komutan emriyle iki açık madde kapatıldı (rapor HEAD `2006f696` durumunu belgeler): D2/OR-legacy liste engeli + D1/UI canlı model-via — uygulama kaydı `FAZ3_GIRDI_2026-09-08.md` §3'te.

---

## 1. PASS LOGU (yapılanlar, kanıtla)

### PASS 1 — DISCOVERY
- 5 dil/runtime bloğu: Python (FastAPI `backend/api.py`, `agent_core/`), Svelte/TS (`frontend/`), Rust (`rust_core/`), Android/Kotlin (`android/`), Bash/CI.
- Entrypoint adayları: `backend/api.py` (Dockerfile `CMD uvicorn backend.api:app`), `main.py`, `live_llm_gate.py`, `run_lilith.py`, `scraper.py`, `scripts/*`.
- 143 pytest dosyası; manşet dokümanlar: `README.md`, `ARCHITECTURE.md`, `RUNBOOK.md`, `CHANGELOG.md`, eski denetim raporları (kanıt olarak KULLANILMADI).

### PASS 2 — EXECUTION GRAPH (production)
Gerçek üretim girişi (Dockerfile + compose): `uvicorn backend.api:app`.
```
Browser (Svelte dist) / OpenAI-uyumlu istemci
  → /api/* , /ws/{client_id} , /v1/*  (FastAPI)
  → auth middleware (fail-closed) + rate limit (kimlik: token|IP, sunucu-türevli)
  → get_room(client_id): PinealExecutor + Kasa(vault) + AspasiaChief   [process-local]
  → /api/initiate → run_mission → (ops. Instagram kazıma) → executor.execute_task
  → 7-PILLAR (deterministik) → CognitiveRouter route → uzman ajanlar (LLM)
  → depth_analyst + shadow_executor + osint_investigator (derinlik turu)
  → HolisticProfile + kanıt zinciri + memory/
  → WS üzerinden log/event/snapshot akışı → UI
```
- OpenAI-uyumlu ikincil yol: `/v1/chat/completions` → `PINEAL_LLM_BACKEND=unified` → `RoutedChatExecutor` (katalogdan otomatik config) → gateway → provider. Legacy mod `PINEAL_LLM_BACKEND=legacy`.
- İkinci/üçüncü girişler CLI/demo: `main.py` (örnek görev), `run_lilith.py` (CLI üretim), `live_llm_gate.py` (canlı kapı, `LIVE_LLM_E2E=1`).

### PASS 3 — STATIC FORENSICS (özet, ayrıntı tablolarda)
- Model zinciri SoT: `AGENT_CHAINS` + `task_routing.json` (delta) + env override → `get_agent_chain`. `agent_tiers.json` tier etiketi: her ajan okunur (18/18). Zengin: zincir çözümü 18 ajan için PASS-3 teyidi.
- Çift yönlendirici katmanı tespit edildi: (a) `LLMGateway.agent_route_variants/query_json_chain` (ajan yolu, `final_routing_policy.ROUTES`), (b) `RoutedChatExecutor` (`/v1`, otomatik config) + `UnifiedRouter` (`PINEAL_ROUTER_CONFIG`). Ayrı `MODEL_PRICING`/`ROUTES`/katalog üçlüsü aynı fiyat gerçeğini üç yerde taşıyor — senkron testlerle korunuyor (PASS 5).

### PASS 4 — RUNTIME (canlı, anahtarsız dev)
`PINEAL_ENV=development`, anahtarsız, local uvicorn :8098 (kayıt: `PASS-4` bölümü):
- `/health` → 200 `ready`; bağımlılık listesi dürüst: `sentence-transformers/interpreter/maigret/holehe/crawl4ai` = `disabled` (+kapı bayrağı).
- `/v1/models` → `{"object":"list","data":[]}` (anahtar yok → hiçbir grup connectable değil; fail-closed, sessiz değil).
- `POST /v1/chat/completions {model:gpt-oss-120b}` → HTTP 400 `unknown unified model group` (grup yoksa sessiz yönlendirme yok).
- `POST /api/aspasia/chat` → HTTP 200 ama **uydurma yok**: yanıt açıkça `REAL_LLM_CALL_NOT_EXECUTED` diyor, `confidence_assessment=fallback`. Canlı-kapı davranışı çalışıyor.
- Sunucu temiz başladı/kapandı (log'da exception yok).

### PASS 5 — TEST FORENSICS (ayrıntı madde 8)
- Tam suite (CI eşdeğeri, root): **1132 passed, 3 skipped** (66.9 s). README "1014 test" iddiası güncel değil (fiilen 1135 collect).
- CI backend job: `pytest --cov=agent_core --cov=backend --cov-fail-under=80` + "shadows committed fresh" + `verify_openrouter_catalog.py`. Frontend job: `svelte-check` + `vite build` + dist içinde `PINEAL-HERETIC` araması. smoke job: gerçek uvicorn + 4 curl (bu denetimde birebir tekrarlandı).
- Mutasyon kanıtı (bu oturumda): M-C1-full (simple zincire paid ekle) → `test_t1_faz2_simple_chains_free_only_static_golden` KIRMIZI; ENFORCE-bypass (guard'ı kaldır) → `test_t1_faz2_simple_enforce_paid_returns_empty_ladder` KIRMIZI. Her ikisi restore → yeşil. (Kilitlerin gerçek olduğuna dair doğrudan kanıt.)
- Güçlü regresyon kültürü: `tests/audit/*` (P0-1…P2-10 vb. kapatılan bulguların geri-gelme koruması), `test_no_mock_in_production.py`, `test_no_secret_leak.py`, `test_wiring_*.py`, tier/shadow/honesty kontratları.

### PASS 6 — SECURITY (ayrıntı madde 3)
- Auth: `PINEAL_ENV` allowlist dışı her değer → production; token yoksa startup fail-closed. `token_matches` timing-safe (`secrets.compare_digest`). WS ilk mesajda token (5 sn), hatalı → 1008/1013.
- Rate limit: sunucu-türevli kimlik; genel kova yalnız mutasyon; experimental kendi kovası; LRU + periyodik süpürme; bucket tavanları.
- Kaynak tavanları: oda sayısı/TTL/client_id format+uzunluk/aktif görev tavanı; kuyruk maxsize 2000.
- SSRF: `resolve_public_url` DNS-pin + redirect başına doğrulama + global-IP zorunluluğu; `safe_get` kullananlar: vision_analyzer, task_executor (_download_images), search/crawl/socid, human_behavior. Not: `holehe_scanner` sabit üçüncü-taraf site listesine ham httpx (kullanıcı URL'si değil) ve env kapalı.
- Harcama: üretimde pozitif `OPENROUTER_MAX_SPEND_USD` zorunlu (startup); runtime `spend_cap` + rezervasyon sayacı + `PaidEscalationDenied`; unpriced model `PINEAL_ALLOW_UNPRICED_MODELS=1` şart.
- Secret hijyeni: `redact_structure` log/telemetri öncesi; Kasa anahtarları oda belleginde, `_load_vault` raw dict'leri odadan düşürüyor; `/api/vault` anahtarları asla loglamıyor.
- Kalan inceleme noktaları (bulgu olarak madde 3'te).

### PASS 7 — CROSS-CHECK (README vs kod/runtime) — madde 9.
### PASS 8 — ROOT CAUSE — bulgular madde 3'te kök neden kümelerine indirildi.
### PASS 9 — FINAL VERDICT — madde 2 (A) ve madde 10.

---

## 2. A. EXECUTIVE VERDICT

```text
Production readiness:       ORTA-YÜKSEK. Tek parça tek-imajlı FastAPI servisi; başlangıç
                            kapıları (auth/spend-cap/bagimlilik) fail-closed; çalışma
                            zamanı anahtarsız durumda dürüstçe duruyor (runtime kanıtı).
                            CANLI sağlayıcı çağrısı (gerçek anahtar) bu oturumda doğrulanamadı.
Architecture integrity:     ORTA-YÜKSEK. Tek SoT iddiası büyük ölçüde doğru (snapshot/shadow
                            üretici + kontrat testleri + tier/görev dosyaları). Yine de
                            routing mantığı 3 katmanda (LLMGateway/ROUTES, RoutedChatExecutor,
                            UnifiedRouter) ve fiyat gerçeği 3 dosyada yaşıyor -> senkron testlere
                            bağımlı; duplication drift riski düşük ama sıfır değil.
Runtime correctness:        Anahtarsız/yetkisiz durumda ölçülen davranış beklenenle birebir.
                            Canlı LLM doğruluğu UNKNOWN (anahtar yok).
Security posture:           YÜKSEK (kod seviyesinde): fail-closed env, timing-safe token,
                            SSRF pin, path traversal, redaction, kaynak tavanları.
Test confidence:            YÜKSEK-ORTA: 1132/1135 yeşil, audit-regresyon + kontrat +
                            mutasyon kültürü güçlü; zayıf noktalar madde 8'de.
Main risk:                  Tek-process oda/kasa modeli (memory/ + rate + kasa + kuyruk)
                            => yatay ölçek yok; canlı sağlayıcı davranışı ve kazıma akışı
                            (gerçek cookie/Playwright) CI'da kapsanmıyor; canlı üretim
                            yalnızca release-gates/live_llm_gate ile (manuel).
```

## B. GERÇEK MİMARİ (koddan)

```
[UI: Svelte dist]───X-API-Key(localStorage|VITE)──>[FastAPI]──/ws→[oda: PinealExecutor]
[OpenAI uyumlu istemci]──────/v1/*──────>RoutedChatExecutor (unified) | LLMGateway (legacy)
oda = {executor: PinealExecutor, vault, ws set, queue, AspasiaChief, mission_tasks, lifecycle}
PinealExecutor:
  - 7 deterministik "dalga" motoru (PillarOrchestrator; LLM YOK — PASS 3 doğrulandı)
  - forensikler: follower_audit, timing_forensics, psychodynamic_depth (deterministik)
  - CognitiveRouter (GOAL_FOCUS) -> ajan listesi; 18 ajan tier etiketli
  - ajanlar LLMGateway.query_json_chain üzerinden zincir (AGENT_CHAINS+task_routing)
  - depth_analyst / shadow_executor / osint_investigator derinlik turu (LLM'li/LLM'siz)
  - HolisticProfile + evidence_chain + CanonicalMemory(diskte) / HindsightMemory(ops.)
Bellek: memory/ (kanonik JSON/SQLite), response cache cache/ (SQLite), vault .pineal_vault.json
Sağlayıcı: OpenRouter (zorunlu taşıyıcı) + direct (groq/deepseek/cerebras/nous/... env anahtarı)
```

## C. CRITICAL / HIGH FINDINGS

Kod seviyesinde **doğrulanmış CRITICAL çalışma-hatası bulunamadı** (fail-closed varsayılanlar, dürüst-eksik davranış, güçlü regresyon koruması). Aşağıdakiler HIGH/MEDIUM adayları; her biri kanıtlıdır:

| ID | Severity | Bulgu | Kanıt |
|---|---|---|---|
| F1 | MEDIUM | `/v1/models` anahtarsız runtime'da boş liste döner ama UI/README'de "14-provider routing" ve zengin model seti ima edilir; modele erişim **anahtara** bağlıdır, katalogda "tanımlı" olması "erişilebilir" demek değildir. | PASS-4 `{"data":[]}`; PASS-3 katalog 25 provider/5'inde model var (openrouter 9, nous-research 8, deepseek 3, groq 2, cerebras 1) |
| F2 | MEDIUM | UI "ACTIVE MODEL/VIA" çubuğu `runs[currentAgent]?.model/.via` okur; backend `AgentRun` serileştirmesi bu alanları **hiç üretmiyor** (yalnız `output_summary/provenance/call_ids`) → çubuk **her zaman statik** `agentList` fallback'ine düşer. Üretici yorumu "canlı run.via önceliklidir" çalışmıyor. | `AgentRun` modeli (memory_models.py:6-21) `model`/`via` içermez; api.py runs serileştirme 1491-1506; svelte:475-476, 567 |
| F3 | LOW/MEDIUM | README'de provider/model iddiaları kodla uyuşmuyor: (a) `llama-3.3-70b` Groq'da hiçbir yerde yok; (b) `E2B Sandbox` yalnız README'de, kod/config yok; (c) "1014 test" fiili 1135; (d) Google Gemini "resmi OpenAI-uyumlu" ama katalogda 0 model (operator beyanı `PINEAL_PROVIDER_MODELS_GOOGLE_GEMINI` şart). | grep kanıtları PASS-7 tablosu |
| F4 | LOW | Docker compose `pineal_vault:/app/vault-data` volume'u tanımlı ama kod `VAULT_FILE=".pineal_vault.json"` (cwd) kullanıyor; `/app/vault-data` yazılıp okunmuyor (ölü mount). | api.py:495 vs docker-compose volumes |
| F5 | INFO/HIGH(koşullu) | `osint_investigator`, `shadow_executor`, `depth_analyst` ana görev akışında HER görevde çalışıyor (derinlik turu); `osint` LLM çağırmıyor (dormant chain) ama `shadow`/`depth` LLM'li → anahtarsız üretimde hata değil ama maliyet/gecikme; hangi koşulda tam atlandığı dokümante değil. | task_executor.py:905-1030; osint_investigator.py yalnız init'te gateway |
| F6 | INFO | `dialogue_manager`, `interpreter` (registry kapalı), `lilith_growth` (CLI) üretim HTTP yolunda doğrudan çağrılmıyor; tier dosyası bunu "dormant" diye beyan ediyor (beyan kodla uyumlu). | PASS-2/9 |

## D. FALSE CONFIDENCE (özellikle arananlar)

| Tür | Bulgu |
|---|---|
| green tests but broken runtime | Bulunamadı (runtime probe ile testlerin ölçtüğü davranışlar doğrulandı) |
| implemented but unreachable | `/v1` unified rota anahtarsız kurulamaz (fail-closed). `main.py` demo, `run_lilith.py` CLI, `live_llm_gate.py` manuel — "üretim özelliği" değil |
| configured but unused | `PINEAL_ALLOW_UNPRICED_MODELS` kullanılıyor (kodda var); `/app/vault-data` mount **kullanılmıyor** (F4). `OPENROUTER_VISION_MODEL` kodda okunuyor (query) |
| documented but absent | `llama-3.3-70b`, `E2B Sandbox`, "14-provider" (fiilî 25 kayıt/5'inde model), "1014 test" |
| free but inaccessible | Free ID'ler (groq/cerebras/nous `:free`) ROUTES+katalogda `verified`; **erişim anahtara bağlı** (env). Anahtarsız → erişilemez (tasarım) |
| fallback but actually primary | `routed_chat` legacy→unified "fallback"i startup'ta `UNIFIED_ROUTER_CONFIG_MISSING` degraded'e düşer; aspire edilen değil ama görünür |
| secure-looking but bypassable | Doğrulanmış bypass yok. Not: dev'de `PINEAL_REQUIRE_AUTH=false` + `PINEAL_ENV=development` açıkça auth kapatır (bilinçli, /health uyarır) |
| covered but weakly asserted | UI "MODEL/VIA canlı" iddiası svelte fallback'iyle **kapsanmıyor** (F2); bu alanın kontrat testi yok |
| UI says X while runtime does Y | UI statik kart model adları SoT'tan üretiliyor (doğru); ama ACTIVE-MODEL çubuğu statik fallback gösterir (F2). `/v1/models` boş iken UI model seçimi sunmuyor (çelişki yok) |

## E. DEAD / DORMANT SYSTEMS

| Sistem | Sınıf | Kanıt |
|---|---|---|
| `rust_core/` | Experimental-optional; üretim çalışma zamanına ENTEGRE DEĞİL | `runtime_status._RUST_CORE_STATUS` sabiti; Dockerfile kopyalamıyor; python köprüsü yok (yalnız status dict) |
| `android/` | Bağımsız Gradle projesi; Python servisiyle bağ yok | CI ayrı job; repo'da python tarafından import/subprocess yok |
| `main.py` / `live_llm_gate.py` / `scraper.py` / `run_lilith.py` | CLI/demo/manual-gate | Dockerfile yalnız `backend.api` çalıştırır |
| `dialogue_manager` | Dormant (yalnız `/api/experimental/chat/respond`) | api.py:2149-2211; ana rota planlamıyor |
| `interpreter` | Varsayılan kapalı; yalnız `ENABLE_INTERPRETER=true` | cognitive_router/task_executor/api.py aynı env |
| `osint_investigator` LLM zinciri | Dormant (gateway tutar, çağırmaz) | agents/osint_investigator.py init dışında `query_*` yok |
| shadow_executor | Deneysel endpoint + görev derinlik turu | `/api/experimental/shadow/*` + task_executor |
| `decision_config.yaml` alanları | Kısmen ölü riski (aşağıda F: config okunuyor; hangi anahtarların hiç okunmadığı doğrulanmalı) | bkz. F tablosu |

## F. CONFIGURATION TRUTH TABLE (öne çıkanlar)

| Config | Tanımlı | Okunuyor | Üretim etkisi | Not |
|---|:---:|:---:|---:|---|
| `PINEAL_ENV` | .env.example | ✓ (security) | Yüksek — fail-closed belirleyici | Allowlist dışı → prod |
| `PINEAL_TOKEN` / `PINEAL_REQUIRE_AUTH` | ✓ | ✓ | Yüksek | prod'da token zorunlu |
| `OPENROUTER_MAX_SPEND_USD` | ✓ | ✓ (security+gateway) | Yüksek | prod pozitif zorunlu; 0 = dev |
| `PINEAL_ALLOW_PAID_ESCALATION` | ✓ | ✓ (policy/gateway) | Yüksek | paid/frontier kapısı |
| `PINEAL_ALLOW_UNPRICED_MODELS` | ✓ | ✓ (gateway) | Yüksek | fiyatsız modele açık izin |
| `PINEAL_LLM_BACKEND` | ✓ | ✓ (api lifespan) | Yüksek | unified/legacy |
| `PINEAL_ROUTER_CONFIG` | ✓ | ✓ | Orta | yoksa auto-config |
| Provider anahtarları (GROQ/CEREBRAS/NOUS/...) | ✓ | ✓ (route/transport) | Yüksek | anahtar yoksa rota yok |
| `PINEAL_MAX_ROOMS`/TTL/CLIENT_ID | ✓ | ✓ | Orta | resource cap |
| `PINEAL_CACHE_MAX_ROWS` | ✓ | ✓ (cache) | Düşük | emniyet kemeri |
| `PINEAL_MEMORY_ENGINE` | ✓ | ✓ (memory) | Orta | canonical/hindsight |
| `ENABLE_MAIGRET/HOLEHE/CRAWL4AI/INTERPRETER` | ✓ | ✓ | Yüksek | varsayılan KAPALI |
| `OPENROUTER_VISION_MODEL` | ✓ | ✓ (query) | Düşük | görsel model |
| `USE_LOCAL_LLM` / `LOCAL_LLM_*` | ✓ | ✓ | Orta | Kasa override eder |
| `VITE_PINEAL_TOKEN` | ✓ | ✓ (build) | Yüksek | prod UI kimliği |
| `E2B_API_KEY` | README'de | **YOK** | — | dokümante ama kodda yok |
| `PINEAL_ALLOWED_ORIGINS` | ✓ | ✓ (CORS) | Düşük | boşsa localhost |
| `/app/vault-data` volume | compose | **YOK** | — | ölü mount (F4) |

## G. MODEL / PROVIDER ROUTING TRUTH TABLE

Sınıflandırma merdiveni (kod): **DECLARED** (katalog/ROUTES) → **REGISTERED** (registry) → **AVAILABLE** (ROUTES `verified`+tier) → **ROUTABLE** (transport + policy) → **REACHABLE** (anahtar + kısıt) → **CALLED** (runtime'da fiilen).

| Model (zincir kaynağı) | Tier ajanlar | Katalog | ROUTES | Erişim koşulu (kod) | Fiili durum |
|---|---|---|---|---|---|
| `openai/gpt-oss-120b` | simple (4 zincir) + genel | groq/cerebras | ✓ free verified | GROQ ya da CEREBRAS anahtarı (direct) / OR | REACHABLE koşullu; anahtarsız yok |
| `poolside/laguna-s-2.1:free` | simple zincirleri | nous | ✓ free | NOUS anahtarı (direct) / OR free | REACHABLE koşullu |
| `anthropic/claude-sonnet-5` | heavy/verify/aspasia | nous + OR | ✓ paid (nous indirimli $1.6/$8; OR liste) | nous direct: NOUS anahtarı + heavy indirim-relax; OR: OPENROUTER anahtarı (+ escalation politikası) | REACHABLE koşullu |
| `google/gemini-3.7-flash` | heavy/vision | OR (google-gemini: 0) | OR `verified` | OPENROUTER anahtarı; google direct YOK | yalnız OR |
| `x-ai/grok-4.6`, `deepseek-v4-*` | heavy/verify | OR/deepseek | deepseek direct | OR veya DEEPSEEK anahtarı | koşullu |
| `openai/gpt-5.6-sol-pro` (hakem) | live-gate judge | OR | frontier $2/$10 | OPENROUTER + judge env | manuel kapı |
| OR kataloğu artıkları (`upstage/solar-pro4`, `inclusionai/ling-3.0-flash`, `z-ai/glm-5.2`) | — | OR'da mevcut | — | /v1 grup olarak ROUTABLE (auto-config OR havuzuna girer) | ajan zincirlerinde DEĞİL (emekli beyanı doğru) |

Önemli kod gerçeği:
- Ajan yolu modeli = zincir (ilk model → başarısızsa sıradaki); her model için `agent_route_variants` provider merdiveni (direct free → direct ucuz/indirimli → OR). Simple tier'da paid/direct/OR-legacy **ENFORCE reddi** (HEAD davranışı, kilitli: `tier_denied_transport` + `[]`).
- Heavy/vision/verify: nous **indirimli direct** escalation env'siz kullanılabilir (relax); liste-fiyat direct bugünkü paid firewall; OR-legacy liste engeli **henüz yok** (yalnız denetim izi) — yani OR-legacy üzerinden liste fiyatı ödeme yolu hâlâ açık (bilinçli erteleme, koddaki yorumda belirtiliyor).
- "Free model tanımlı ama rotaya hiç girmiyor" örneği: google-gemini 0 model (declared provider, no models). "Tanımlı ve routable ama ajan zincirinde yok": OR'daki emekli üçlü.

## H. TEST TRUST REPORT

| Katman | Dosyalar | Güven |
|---|---|---|
| Unit (routing/gateway/policy) | test_final_routing_policy, test_tier_variant_gate, test_routing_cost_firewall, ... | YÜKSEK — mutasyon kanıtlı (bu oturum M-C1-full/bypass KIRMIZI) |
| Unit (agents/engines/depth) | test_passion_mapper, test_pillar_*, test_glue_*, ... | YÜKSEK-ORTA |
| Audit-regresyon | tests/audit/* (P0-1..P2-10) | YÜKSEK (geçmiş kusur geri-gelme kilidi) |
| Security | test_security_hardening/isolation, test_no_secret_leak, test_no_mock_in_production | YÜKSEK |
| Integration (API) | test_aspasia_chat_api, test_critical_paths, test_ws_ordering, test_openai_compatibility | ORTA-YÜKSEK — TestClient üzerinde gerçek app |
| E2E/canlı | tests/e2e + release-gates.yml | ORTA — canlı LLM/cookie kapsamı manuel (LIVE kapısı) |
| Şüpheli/zayıf alanlar | UI "MODEL/VIA canlı" iddiası (F2): kontrat testi YOK; `/v1/models` içeriği anahtarsız boş iken bunu assert eden e2e yok; kararlı snapshot doğrulaması `--check` ile sınırlı (değer doğruluğu değil, bayatlık) | ORTA |

Not: `--cov-fail-under=80` agent_core+backend genelinde gerçek bir eşik; CI'da yeşil (HEAD `2006f696` → run `34199584703`, 5/5 job: android, rust-core, frontend, backend, smoke).

## I. AS-IS vs DOCUMENTED

| README/İddia | Kod/Runtime | Durum |
|---|---|---|
| v3.1 · 360° insan tanıma istasyonu | Doğrulanabilir: misyon akışı profil analizi üretir | ✅ (kapsam iddiası abartılı ama kodda karşılığı var) |
| 7 nöro-bilişsel dalga motoru | engines/ deterministik, LLM'siz, görev akışında çalışıyor | ✅ |
| 14-provider yönlendirme | Katalog 25 provider; yalnız 5'inde model (openrouter/nous-research/deepseek/groq/cerebras); transport OPENAI_CHAT dışı havuza giremez; aktif havuz anahtar-koşullu | ⚠️ sayı/erişim abartısı |
| Google Gemini resmi OpenAI-uyumlu | google-gemini katalogda 0 model; yalnız operator beyanı | ⚠️ |
| Groq `gpt-oss-120b`, `llama-3.3-70b` | sadece gpt-oss-120b(+20b) var; `llama-3.3-70b` YOK | ❌ |
| Ağ geçitleri … `E2B Sandbox` | kod/config'te E2B yok | ❌ |
| Fail-closed harcama bayrakları | her iki bayrak kodda okunuyor + prod cap zorunlu | ✅ |
| Kasa `.pineal_vault.json` iç içe schema | `_load_vault` okur; ham dict düşürülür | ✅ (not: disk yazımı yok, oda belleğinde) |
| Dual memory + Aspasia | canonical/hindsight + AspasiaChief | ✅ |
| Test disiplini: "1014 test" | fiilen 1135 collect / 1132 pass; audit+mutasyon kültürü | ⚠️ sayı bayat |
| rust_core: bağımsız deneysel, ürüne entegre değil | `_RUST_CORE_STATUS` birebir | ✅ |
| "Kişisel veriler yalnız yerel memory/; dış sunuculara telemetri yok" | outbound: sağlayıcılar + arama + görsel fetch (hepsi anahtar/SSRF korumalı); telemetri yok | ✅ (canlı anahtar yokken doğrulandı) |
| "hiçbir platforma gizli/otomatik mesaj atmaz" | kodda otomatik gönderim yok (yalnız mesaj ÜRETİMİ; X kazıması kapalı) | ✅ |

## J. TOP 10 RISKS (önem sırası)

1. **Canlı sağlayıcı davranışı CI kapsamı dışı** — release-gates + live_llm_gate manuel; gerçek anahtarla routing/fallback/maliyet hiçbir otomatik job'da doğrulanmıyor (yüksek etki × koşullu oluşma).
2. **Tek-process mimarisi** (oda/kasa/rate/kuyruk process-local) — ölçek/restart veri davranışı; multi-replica yasak compose'da beyanlı (bilinçli) ama operasyon riski.
3. **UI gerçek-zaman model/provider göstergesi çalışmıyor** (F2) — operatör "hangi model/provider çalıştı"yı canlı göremez; iz ancak provenanceda/call log'da.
4. **OR-legacy liste-fiyat kaçağı hâlâ açık** — heavy ailesi için indirimli direct yoksa OR liste fiyatından ödeme yolu denetim izinde ama engelli değil (bilinçli erteleme; ama harcama riski).
5. **Canlı-katalog bağımlılığı** — OR kataloğu doğrulama scripti canlı anahtar olmadan SKIP; model/ID bozulması yalnız yerel kontratla yakalanır.
6. **Instagram kazıma** — kullanıcı cookie'si + Playwright; hesap kısıt/ban/yasal risk; testler gerçek IG'ye değil fixture'lara dayanıyor.
7. **Google direct yokluğu** — gemini yalnız OR üzerinden (vision dahil); google-gemini katalog boş; tek sağlayıcıya bağımlılık.
8. **Kasa kalıcılığı yok** (disk yazımı yok) — restart'ta oda/kasa kaybı; uzun görev belleği memory/ ama anahtarlar uçar.
9. **`/v1/models` ve UI model seçimi anahtarsız boş** — istemci deneyimi "model yok" (fail-closed doğru ama dokümante edilmemiş).
10. **Dokümantasyon sayı/özellik bayatlığı** (F3; README test sayısı, llama/E2B/14-provider) — yanlış beklenti ve denetim güveni kaybı.

## K. RECOMMENDED REPAIR ORDER (henüz değişiklik yapılmadı)

```text
P0  — Yok (fail-closed ihlali/uzaktan sömürülebilir açık doğrulanmadı).
P1  — (a) UI MODEL/VIA çubuğunu gerçek provenansa bağla (F2) veya etiketi "statik"
      yap. (b) OR-legacy liste-fiyat kaçağı için karar turu (engelle veya belgele).
      (c) Canlı-katalog doğrulamayı anahtarlı bir CI job'ına (workflow_dispatch)
      taşı. Doğrulama: kontrat testi + mutation.
P2  — (a) /v1/models içeriği için e2e assert (anahtarsız boş = beklenen) ekle.
      (b) README provider/model/test-sayısı bayatlıklarını düzelt (F3) veya
      "generated: TARİH" işareti koy. (c) compose vault volume'unu koda bağla ya da kaldır (F4).
P3  — (a) derinlik turu (depth/shadow/osint) koşullarını dokümante + skip sayacı.
      (b) dialogue_manager/lilith/interpreter "dormant" beyanını merkezi tek yerde
      sürdür (tier dosyası _meta zaten not düşüyor). (c) process-local kasa için
      restart politikası yaz.
```

## 11. UNKNOWN / YETERSİZ KANIT (uydurma yok)

- **Canlı LLM çağrı davranışı** (gerçek OpenRouter/provider anahtarı): doğrulanamadı — anahtar yok; yalnız fail-closed yolu runtime'da ölçüldü.
- **Gerçek Instagram kazıma** (cookie + canlı hedef): ölçülmedi (dış ağ + hesap riski).
- **Maigret/holehe/crawl4ai canlı tarama davranışı**: env kapalı; sadece kapı + birim testler incelendi.
- **Gerçek maliyet/kota davranışı**: dolar tahmini ÜRETİLMEDİ; fiyatlar katalog/ROUTES'ten alındı (doğrulama scripti yerel PASS).
- **Android uygulamasının işlevi**: repo'da servisle bağı yok; derinlemesine Kotlin denetimi yapılmadı (yalnız varlık/CI doğrulandı).
- **Bazı config anahtarlarının tam okunurluk matrisi** (decision_config.yaml içindeki tüm field_weights'lerin runtime tüketimi): kısmen doğrulandı; tam liste için ek PASS gerekir.
- **Kod-ötesi davranış** (sağlayıcı kotaları, OR yanıt kalitesi): denetlenemez.
- **Restart-runtime davranışı** (kasa/oda kaybında fiilen ne oluyor — ölçülmedi; §2J risk #8'in runtime karşılığı yok).
- **Paralel görev / çok-oda yük davranışı** (process-local modelde eşzamanlılık ölçülmedi).

## 12. YÖNTEM NOTU (bağımsızlık sınırı)

Bu oturum aynı zamanda repo'da son commit'lerin yazarıdır (`2006f696` routing değişiklikleri dahil). Bu nedenle son değişikliklerin **tasarım niyeti** tarafsız değerlendirilememiştir; rapordaki tüm ifadeler HEAD'deki **kod durumu** ve bu oturumda **ölçülen davranış** ile sınırlıdır. Bağımsız doğrulama için: `git show 2006f696` + bu rapordaki PASS-4 komutlarının tekrarı yeterlidir.

## EK — Kanıt komutları (tekrarlanabilir)

```bash
# runtime
PINEAL_ENV=development PINEAL_REQUIRE_AUTH=false PINEAL_CACHE_PATH=/tmp/a.db \
  .venv/bin/python -m uvicorn backend.api:app --port 8098 &
curl -s localhost:8098/health; curl -s localhost:8098/v1/models
curl -s -X POST localhost:8098/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"model":"gpt-oss-120b","messages":[{"role":"user","content":"ping"}]}'
curl -s -X POST localhost:8098/api/aspasia/chat -H 'Content-Type: application/json' \
  -d '{"client_id":"p","user_message":"hi"}'
# testler (tam suite)
.venv/bin/python -m pytest tests -q -p no:cacheprovider          # 1132 passed, 3 skipped
# katalog
.venv/bin/python -c "import json;d=json.load(open('config/provider_catalog.json'));[print(p['id'],len(p.get('models',[]))) for p in d['providers']]"
# zincir çözümü (18 ajan) — PASS-3 tablosu
.venv/bin/python scripts/generate_routing_shadows.py --check
# mutasyon kanıtı (F-sekmesi): simple zincire paid ekle / ENFORCE guard'ı kaldır -> kilit KIRMIZI
```
