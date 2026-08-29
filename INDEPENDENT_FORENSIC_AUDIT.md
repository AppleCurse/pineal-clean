# INDEPENDENT FORENSIC AUDIT — pineal-clean

**İnceleme tarihi:** 2026-08-29
**İnceleyen:** Bağımsız doğrulayıcı (önceki hiçbir rapor/README iddiası referans alınmadı)
**Yöntem:** Sıfırdan kurulum → lint → test → build → start → HTTP/WS çalışma zamanı → negatif testler → güvenlik → bağımlılık/config/deployment denetimi → canlı OpenRouter katalog doğrulaması
**Revizyon:** `fda9940` ("ci(github): add Android build pipeline to canonical workflow"), branch `arena/01a04b6f-pineal-clean` (tek commit'li checkout)

> **Kanıt disiplini:** Aşağıdaki her sonuç ya çalışma zamanı çıktısıyla, ya kod/call-graph incelemesiyle ya da dış katalog sorgusuyla desteklenir. Kanıt yoksa **UNKNOWN**, çalıştırılamadıysa **NOT EXECUTED** yazılmıştır. Kesinlik dereceleri açık belirtilmiştir.

---

## 1. Executive Summary

Sistem, README'nin çoğu iddiasının **gerçekten çalıştığı ender bir proje**: sahte/placeholder yanıt üretmeyen, kanıt yoksa **dürüstçe duran** (halted_evidence) bir ajan pipeline'ı kodda değil, **çalışma zamanında doğrulandı**. Sunucu ayağa kalktı, Svelte arayüzü servis edildi, WebSocket üzerinden FIFO telemetri + sonuç üretildi, kimlik doğrulama ve hız limiti çalıştı, bellek kalıcılığı ve kalıcı silme çalıştı.

Ancak denetim şunları da tespit etti:

- **2 test kod–kontrat uyuşmazlığı nedeniyle FAIL** (345/347 geçti); bu haliyle CI'ın backend job'ı da kırmızı olur.
- **README/RUNBOOK'taki model zinciri belgeleri kodla çelişiyor** (kodda hiç olmayan `laguna-s-2.1`, `minimax-m2.7`, `qwen3-235b-a22b-2507` zincirleri belgelenmiş).
- **README + ARCHITECTURE: "rust_core CI'da derlenmiyor" — ÇELİŞKİ:** `ci.yml` içinde Rust derleyip test eden `rust-core` job'u var.
- **`USE_LOCAL_LLM` env değişkeni API sunucusu yoksayılıyor** (vault değeriyle eziliyor) — çalışma zamanında kanıtlandı.
- **`OPENROUTER_TIER_2_MODEL` env'i belgelenmiş ama kodda hiç okunmuyor** (ölü config).
- **Android uygulaması Python backend'ine hiç bağlanmıyor**; doğrudan Google Gemini API'sine konuşan bağımsız bir istemci.
- Canlı OpenRouter ücretli çağrısı ve Instagram kazıması bu ortamda çalıştırılamadı (**NOT EXECUTED** — anahtar yok; Chromium CDN'i erişilemez).

**Genel gerçeklik derecelendirmesi (kanıt ağırlıklı):** Çekirdek (API + pipeline + bellek + telemetri + güvenlik kapıları) **WORKING**; LLM canlı bulut yolu **PARTIAL** (kod + kapı doğrulandı, ücretli çağrı yürütülemedi); kazıma **PARTIAL**; Rust/Tauri/Android **UNKNOWN/NOT EXECUTED**.

---

## 2. What Actually Works (çalışma zamanında kanıtlandı)

| # | Kanıt | Yöntem | Sonuç |
|---|---|---|---|
| 1 | Kurulum | `pip install -r requirements.txt` → exit 0, venv 787 MB | **PASS** |
| 2 | Lint | `ruff check .` → "All checks passed" | **PASS** |
| 3 | Frontend build | `npm ci` + `npm run check` (0 hata) + `npm run build` (110.92 kB JS); `grep "PINEAL-HERETIC" dist/assets/*.js` eşleşti | **PASS** |
| 4 | Start | `uvicorn backend.api:app` → "Application startup complete"; `GET /` → 200 + `id="app"` | **PASS** |
| 5 | Telemetry | `GET /api/telemetry` → dürüst yetenek raporu (browser_installed:false — Chromium gerçekten yok) | **PASS** |
| 6 | Aspasia fallback | Anahtarsız `POST /api/aspasia/chat` → 200, `confidence_assessment:"fallback"`, uydurma yok ("Sistem verisini uydurmuyorum") | **PASS** |
| 7 | WS+initiate zinciri | initiate → WS'te 13 mesaj (log/snapshot/TaskStarted FIFO) → `result: halted_evidence` (LLM'siz koşuda dürüst duraklama) | **PASS** |
| 8 | **Tam pipeline, canlı sağlayıcı çağrısıyla** | Yerel OpenAI-uyumlu sağlayıcı + Kasa kilidi: `mirror_truth`/`passion_mapper`/`friction_detector` **completed, provenance="llm"**; DecisionEngine → `partially_completed` | **PASS** |
| 9 | Model zinciri failover | Çalışma zamanı logu: depth zincirinde `solar-pro4 → glm-5.2 → deepseek-v4-pro` sırayla denendi (şema hatasında sıradaki modele düşme) | **PASS** |
| 10 | Halüsinasyon kapısı | UncertaintyEngine, jenerik/içeriksiz LLM yanıtını "Düşük güven (0.00 < 0.7)" ile durdurdu; interpreter, autonomous_verifier, cognitive_profiler vb. dürüstçe halted | **PASS** |
| 11 | Provenance damgası | `mirror_truth: prov=llm`, `shadow_executor: prov=fallback (dark_triad_markers_unobserved)`, `osint: prov=fallback (provider_credentials_unavailable)` | **PASS** |
| 12 | Hız limiti | 6. ardışık initiate → **429** | **PASS** |
| 13 | Kimlik doğrulama | Token'lı örnek: token'sız **401**, yanlış **401**, doğru **200**; WS yanlış token → bağlantı reddi (1008/403) | **PASS** |
| 14 | X URL politikası | `x.com` hedefi → `result: awaiting_authorization`, analiz başlamadı | **PASS** |
| 15 | Desteklenmeyen platform | `facebook.com` → `result: unsupported_platform`, tahmine dayalı kazıma yok | **PASS** |
| 16 | Bellek kalıcılığı | Her görev için `memory/<task_id>.json` yazıldı; evidence sayısı/confidence dosyada | **PASS** |
| 17 | Retention (silme) | `DELETE /api/tasks/{id}` → dosya gerçekten silindi; olmayan id → **404** | **PASS** |
| 18 | Interpreter kilidi | `POST /api/experimental/interpreter/execute` → **403** (ENABLE_INTERPRETER tanımsızken) | **PASS** |
| 19 | Override/hafıza | `POST /api/override` → `memory/learnings.json` + SHA-256 hash'li kayıt | **PASS** |
| 20 | Yanıt önbelleği | SQLite: `cache` put/get + `response_cache` tablosu doğrulandı | **PASS** |
| 21 | Negatif girdiler | Eksik alan → 422 (FastAPI `{detail:[...]}`), olmayan API → 404 `{error:{code,message}}` — README §8 hata modeliyle birebir | **PASS** |
| 22 | Model slug'ları | **6/6 slug canlı OpenRouter kataloğunda VAR**: `upstage/solar-pro4`, `inclusionai/ling-3.0-flash`, `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro`, `z-ai/glm-5.2`, `google/gemini-3.7-flash` (2026-08-29 sorgusu) | **VERIFIED** |

---

## 3. What Partially Works

| Bileşen | Durum | Kanıt ve sınır |
|---|---|---|
| **Canlı OpenRouter (ücretli) çağrısı** | PARTIAL | Gateway kodu, kilidi (`LIVE_LLM_E2E`/vault), spend-cap, fiyat guard'ı, retry/circuit breaker testleri geçti; **ancak API anahtarı olmadığı için gerçek ücretli çağrı yürütülemedi → NOT EXECUTED**. Local-provider yolu ise uçtan uca doğrulandı (sağlayıcı HTTP trafiği gözlemlendi). |
| **Instagram kazıma** | PARTIAL | `agent_core/scraper/instagram_ghost.py` tam modüllü (Pydantic V2 şema, `InsufficientEvidenceError`), `platform_registry.scrape_instagram` Playwright+stealth kuruyor; hata yolları testli. Ama **chromium indirilemedi (CDN erişilemez) + gerçek Instagram erişimi yok → NOT EXECUTED**. |
| **VisionAnalyzer** | PARTIAL | Çok katmanlı indirme doğrulaması (SSRF guard, magic-byte sniff, boyut limiti) + yerel confidence türetme kodu sağlam; testleri geçti. Gerçek multimodal model çağrısı **NOT EXECUTED**. |
| **Test süiti** | PARTIAL | **345/347 PASS**. `tests/unit/test_human_behavior.py::test_linguistic_forensics` ve `::test_analyze_visual_micro` FAIL — kod `signal_type="passive_voice_observation"` ve `"visual_edge_density"` + yüz-gerekli omuz bölgesine evrilmiş, testler eski kontratta. **Test drift, ürün hatası değil ama CI'ı kırmızı yapar.** |
| **Hindsight (anlamsal bellek)** | PARTIAL | `PINEAL_MEMORY_ENGINE=hindsight` opsiyonu + `requirements-ml.txt` dürüstçe "opsiyonel" belgelenmiş; kurulumu yapılmadı → **NOT EXECUTED**. |
| **7-Pillar deterministik motorlar** | PARTIAL | Boş hedef verisiyle çalıştı (`pineal_7pillar: completed, conf=0.0`); anlamlı girdiyle çıktı kalitesi bu denetimde ayrıca ölçülmedi. |
| **Model fiyatlandırma tablosu** | PARTIAL | `solar-pro4` (0.03/0.12) ve `ling-3.0-flash` (0.021/0.063) katalogla **birebir**; `gemini-3.7-flash` (0.375/1.875) flex kademesiyle eşleşiyor. Ancak `glm-5.2` için 0.10/0.10 yazılmış — katalogda görülen en ucuz uç nokta ~0.39/1.22 → **harcama sayacı maliyeti olduğundan düşük gösterebilir**. `deepseek-v4-pro` (0.50/1.00) da katalog mininin (~0.71/1.42) altında. |

---

## 4. What Is Broken

| Bulgu | Kanıt |
|---|---|
| **2 birim test FAIL** (repo'nun kendi kalite kapısında kırmızı) | `tests/unit/test_human_behavior.py:114` — `assert any(s.signal_type == "tension")` → False; aynı dosyada `contradiction`+`passive_voice` bekleyen test → False. Kod `agent_core/agents/human_behavior.py:382` ("passive_voice_observation") ve :325 ("visual_edge_density") ile evrilmiş. **Bu haliyle `pytest -q` ve dolayısıyla CI backend job FAIL eder.** |
| **README test sayısı eski** | README/RUNBOOK: "223 test"; gerçek toplanan: **347** (her iki belge de güncel sayı için komut veriyor — kısmi savunma). |

---

## 5. What Is Dead

| Öğe | Kanıt (call-graph) |
|---|---|
| `AspasiaChief.preferred_model = "muse-spark-1.2-xhigh"` ve `set_preferred_model()` | `agent_core/aspasia/aspasia_chief.py:29-32`. Tüm repo (Python+Svelte+TS) tarandı: **hiçbir çağıran yok**; model adı `MODEL_REGISTRY`'de de yok. Ölü özellik. |
| `OPENROUTER_TIER_2_MODEL` env | README §5 tablosunda ve `.env.example`'da tanımlı; kodda yalnız `OPENROUTER_TIER_1_MODEL` okunuyor (`llm_gateway.py:36`), Tier-2 hardcoded (`MODEL_REGISTRY["ling_3_flash"]`). **Ölü config.** |
| README/RUNBOOK model zincirleri (`laguna-s-2.1`, `minimax-m2.7`, `qwen3-235b-a22b-2507`) | Kod içinde **0 geçiş** (grep). Gerçek zincirler: `depth=[solar-pro4, glm-5.2, deepseek-v4-pro]`, `dialogue=[solar-pro4, deepseek-v4-flash]`, `fast=[ling-3.0-flash, deepseek-v4-flash]` (`llm_gateway.py:44-49`). Belgelenen zincirler **koddan kopuk**. |
| X (Twitter) kazıyıcı | Tasarım gereği bilinçli DEAD: `scraper.py` her çağrıda `XScraperUnsupportedError` fırlatıyor; API de X URL'de analizi başlatmıyor. Bu, iddia edilen davranışın kendisi (dürüst kapatma) — gizli bir ölüm değil. |
| `/api/experimental/*` UI çağrıcısı | Frontend'de "experimental" **0 geçiş** — README/ARCHITECTURE "UI çağrıcısı yok (D5)" iddiasıyla **uyumlu** (bilinçli izolasyon; hata değil). |

---

## 6. What Is Mock / Fake / Placeholder

**Üretim kodunda sahte yanıt üreten bir bileşen BULUNAMADI.** Mock-avcısı taraması:

- `grep -rniE "mock|fake|stub|dummy"` (agent_core+backend): yalnız **4 sonuç** ve hepsi *anti-mock savunması*: `osint_investigator.py:73` ("Gerçek API anahtarı yoksa MOCK veri dönülmez: dürüst boş…"), `quote_guard.py` ("dropped_fake_quote" sayaç adı), `task_executor.py:747` (aynı sayaç).
- `placeholder/simulat/hardcod` eşleşmeleri de *placeholder tespit eden* guard kodları (`uncertainty_engine.NON_EVIDENCE_PHRASES` vb.).
- `main.py` içindeki görev verisi sahne verisi — ama bu bir demo script'i, production path'e girmiyor.
- Testlerdeki mock'lar (`tests/`) test izolasyonu amaçlı, production path'e girmiyor.

**Çalışma zamanı çapraz kanıt:** Anahtarsız koşuda sistem uydurma profil üretmedi; `halted_evidence` döndü. Stub sağlayıcıya karşı koşuda bile provenance "fallback" olan damgalar dürüstçe "dark_triad_markers_unobserved", "provider_credentials_unavailable" diye işaretlendi.

---

## 7. What Is Unknown

| Bileşen | Neden UNKNOWN |
|---|---|
| **Rust core (`rust_core/`)** | Bu ortamda cargo yok → **derleme/test NOT EXECUTED**. Not: `ci.yml` Rust job'u içeriyor (aşağıda çelişki). Python çalışma zamanına bağlantısı **yok** (teyit: `scripts/run_task.py` "tek gerçek halef" yorumu + grep'te Python'dan rust çağrısı bulunmadı). |
| **Tauri masaüstü kabuğu** | `tauri = { optional = true }` feature-gated; ARCHITECTURE "ayrı faz" diyor. Çalıştırılamadı → UNKNOWN. |
| **Android uygulaması** | Gradle/SDK yok → **NOT EXECUTED** (CI'da `assembleDebug` tanımlı). Statik inceleme: tam bağımsız bir Gemini istemcisi (aşağıda). |
| **Üretim LLM çıktı kalitesi** | Gerçek model anahtarı olmadan hangi ajanların gerçek modelle eşiği geçtiği ölçülemedi (stub koşusunda çoğu ajan dürüstçe durdu). |
| **OpenRouter "promo 2026-09-10'a kadar" iddiası** | solar-pro4 endpoint'inde `discount: 0.9` görüldü ama promo bitiş tarihi alanı döndürülmedi → doğrulanamadı. |

---

## 8. AI / Agent Reality

Zincir şablonu: **AGENT → PROMPT → MODEL → PROVIDER → TOOL → OUTPUT → CONSUMER**

| Ajan | Model/Provider (kod) | Çağrı zinciri | Çalışma zamanı kanıtı |
|---|---|---|---|
| mirror_truth | `AGENT_CHAINS["cognitive_profiler"]` örtük → TIER1 → OpenRouter/local | `execute → llm_gateway.query_json` → `executor` bunu `input_data["user_mirror"]`'a yazıp authentic-vektör hesabına veriyor | **completed, prov=llm** (yerel sağlayıcı trafiği gözlemlendi) |
| passion_mapper / friction_detector / cognitive_profiler | AGENT_CHAINS + query_json_chain | `execute → query_json_chain` → evidence_chain → HolisticProfile | passion+friction **completed prov=llm**; cognitive jenerik içerikte **dürüstçe halted** |
| interpreter | `open-interpreter` kütüphanesi (kendi OpenRouter config'i, `auto_run=False` zorlanmış) | Router has_user iken rota'ya ekliyor → `execute()` | Jenerik koşuda halted (0.60<0.65). Endpoint'i varsayılan 403. Ağır bağımlılık (~800 MB) ve **gateway dışı** kendi LLM yolu var (mimari kusur, aşağıda). |
| autonomous_verifier | SearchEngine (Tavily/SerpAPI/Exa/DuckDuckGo) + LLM | Router hedef varsa ekliyor; anahtar yoksa DuckDuckGo yedeği | Anahtarsız ortamda dürüst halted. SearchEngine.provider çağrıları kodda gerçek HTTP; **canlı sağlayıcı NOT EXECUTED** |
| resonance_calc | saf numpy (LLM'siz) | mirror+target vektörlerinden compatibility_score; <0.70 → halted_frequency | Boş vektörde dürüst **failed** (vektör üretilmedi bilgisiyle); <0.70 kapısı unit-testli |
| depth_analyst / shadow_executor / osint_investigator | LLM zinciri / deterministik dark-triad / platform skorlama | Executor sondamga olarak çalıştırıyor; DecisionEngine durumlarını görüyor | depth zincir failover'ı **loglarla kanıtlandı**; shadow/osint **prov=fallback** ile dürüst |
| Aspasia | TIER1 + (görselde) vision modeli | `build_telemetry_summary(canlı snapshot) → query(system=ASPASIA_PERSONA)` → UI | Fallback yolu **çalışma zamanında** doğrulandı; canlı yolu NOT EXECUTED |

Model adı gerçekten kullanılıyor mu? **EVET** — `selected_model` her çağrıda `chat.completions.create(model=...)`'a giriyor; `last_call_meta` ve `call_log` ajan evidence'ına `llm_calls` olarak yazılıyor (runtime: `runs` çıktısında gözlemlendi). Router gerçekten routing yapıyor mu? **EVET** — boş hedefte 2 ajan, hedef+ kullanıcı ile 10 ajanlık plan üretti (çalışma zamanında iki koşu). Memory persist? **EVET** (`memory/<task_id>.json` + merge_evidence). Context agent'a veriliyor mu? **EVET** (`input_data` enjeksiyonları: user_mirror/passions/frictions/cognitive/verifications/pillar_bundle).

---

## 9. API Reality

- **Var olan ve çalıştığı doğrulanan uçlar:** `POST /api/initiate`, `WS /ws/{id}`, `POST /api/vault`, `POST /api/override`, `GET /api/telemetry`, `POST /api/aspasia/chat`, `POST /api/scraper/authorize-alternative` (kodsuz test: pending olmadan `no_pending_authorization`), `POST /api/executor/intervene` (yalnız kayıt — müdahaleyi uygulamıyor, dürüst "review_required"), `GET /api/tasks`, `DELETE /api/tasks/{id}`, `POST /api/experimental/shadow/analyze|generate`, `POST /api/experimental/chat/respond`, `POST /api/experimental/interpreter/execute` (403 default).
- Hata modeli iddia edildiği gibi: uygulama hataları `{error:{code,message}}`, 422 FastAPI `{detail}` (çalışma zamanında ikisi de doğrulandı).
- Uçlar frontend ile hizalı: `store.ts` `apiFetch` + `wsUrl` aynı yolları kullanıyor; `npm run check` + wiring testleri temiz.
- Statik mount sona ekli → API rotaları ezilmiyor (`/` Svelte shell 200).

---

## 10. Database Reality

- **SQLite gerçekten kullanılıyor:** LLM yanıt önbelleği (`cache/responses.db`, tablo `response_cache`) — put/get çalışma zamanında doğrulandı. ARCHITECTURE'daki "SQLite yok" ifadesi görev verisi için; belge zaten "SQLite yalnızca önbellek+hindsight" diye netleştiriyor. **Tutarlı.**
- **Kanıt belleği dosya tabanlı:** `memory/<task_id>.json` + `memory/learnings.json` — çalıştı, silme çalıştı.
- Başka DB yok; ORM yok. İddia ile gerçeklik uyumlu.

---

## 11. Dependency Reality

| Paket | Bildirimi | Gerçek |
|---|---|---|
| `litellm>=1.80.0` | requirements.txt | **Kaynak kodda 0 import** (dolaylı olarak open-interpreter zaten çekiyor) → **gereksiz doğrudan bağımlılık** |
| `open-interpreter>=0.4.0` | requirements.txt | Kullanılıyor (`interpreter_agent.py`: `from interpreter import interpreter`) ama yalnızca kilitli uç + kritik-olmayan ajan. **Ağır maliyetli** (venv ~787 MB) ve default-kapalı uç için her kuruluma binmesi tartışmalı |
| `openai`, `httpx`, `cv2`, `numpy`, `playwright`, `playwright-stealth`, `aiofiles`, `python-dotenv`, `fastapi`, `uvicorn`, `pydantic` | — | Hepsi kaynakta import ediliyor (import-grami doğrulandı) |
| `sentence-transformers` | requirements-ml.txt (opsiyonel) | Belgelendiği gibi opsiyonel; hindsight kapısı env ile |
| Eksik bağımlılık | — | Bulunamadı (import edilen her şey requirements'ta) |
| Sürüm uyumsuzluğu | — | Belirgin yok (Python 3.11'de kurulum + tüm süit koştu) |

---

## 12. Security Findings

| # | Severity | Konum | Bulgu / Kanıt | Etki | Öneri |
|---|---|---|---|---|---|
| 1 | **MEDIUM** | `backend/api.py` auth middleware | `PINEAL_TOKEN` tanımsızsa API **tamamen açık** (bilinçli tasarım: "yerel tek kullanıcılı"). `0.0.0.0`'a bind edilmesi + Docker kullanımıyla birleşirse LAN/internete açıkuntsuz panel olur. Statik dosyalar her koşulda auth'suz. | Yetkisiz görev başlatma, veri okuma/silme | `PINEAL_REQUIRE_AUTH=true` üretimde zorunlu kıl; bind'i varsayılan 127.0.0.1 yap |
| 2 | **LOW** | `agent_core/utils/security.py` | SSRF guard sağlam (loopback/private/metadata engelli, DNS çözümlemeli). Ancak **TOCTOU/DNS-rebinding** penceresi: çözümleme burada, istemci ayrıca çözümlüyor. | İç ağ keşfi (teorik) | İndirme istemcisinde IP'yi tekrar doğrula/pin'le |
| 3 | **LOW** | `backend/api.py` `api_delete_task` | `task_id` doğrudan `os.path.join`'e giriyor; ancak HTTP katmanında `{task_id}` `/` içermediğinden traversal **erişilemez** (canlı deneme: `..%2F..%2F` → **405**; canary dosya silinmedi). Explicit sanitizasyon yok → savunma derinliği eksik. | (şu an) Yok | `task_id` regex whitelist (`op_[A-Za-z0-9_]+`) ekle |
| 4 | **LOW** | `backend/api.py` CORS | `allow_credentials=True` + `allow_methods/headers=["*"]`; origin default localhost kümesi. `PINEAL_ALLOWED_ORIGINS` açılırsa geniş yetki. | Origin yanlış config'te credential sızıntısı | Methods/headers'ı daralt |
| 5 | **INFO** | `backend/api.py` `get_room` | `.pineal_vault.json` plaintext anahtar dosyası diskten otomatik yükleniyor; `sk-or-v1-YOUR` placeholder'ı reddediliyor (iyi). | Anahtar diskte plaintext | En azından dosya izni/uyarısı |
| 6 | **INFO** | `backend/api.py` rate limit | Limitler süreç-içi bellek (`defaultdict(deque)`) — restart'ta sıfırlanır, çok worker'da paylaşılmaz. | Zayıf iş importu | Not belgesi / Redis opsiyonu |
| 7 | **POSITIVE** | Tüm Python kaynak | `subprocess/os.system/eval/exec` **0 eşleşme**; interpreter `auto_run=False` zorlanmış + uç default 403. Log sızıntı testi (`test_no_secret_leak`) geçti. | — | — |

---

## 13. Deployment Reality

| Yol | Durum |
|---|---|
| `baslat.bat` (Windows) | İncelendi: venv→pip→build→uvicorn sırası doğru. **NOT EXECUTED** (Windows ortamı yok). |
| `Dockerfile` + `docker-compose.yml` | Çok aşamalı build, healthcheck token-duyarlı (B3), memory volume. **Docker bu ortamda yok → NOT EXECUTED.** `tests/unit/test_dockerfile_contract.py` PASS (statik sözleşme). |
| `.github/workflows/ci.yml` | Mevcut ve yerel sonuçlarla tutarlı kurgu (ruff+pytest+frontend+smoke). **Ancak: 2 test FAIL olduğu için backend job'ı bu revizyonda kırmızı olur.** Ayrıca README'nin aksine **rust-core** ve **android** job'ları içeriyor (bkz. §14). |
| Gerçek deploy kanıtı | Yok (deploy artifact/kayıt yok) → "Deployment configuration exists" ≠ "successfully deployed". |

---

## 14. Contradictions

| # | CONTRADICTION | Taraflar |
|---|---|---|
| 1 | **"rust_core CI'da derlenmiyor/koşmuyor"** (README §ust, ARCHITECTURE.md tablosu: "CI'da derlenmiyor (cargo yok)") **↔ `ci.yml` içinde `rust-core` job'u: `cargo check --all-targets` + `cargo test`** | Belge ↔ CI config. CI'da Rust gerçekten derleniyor; README'nin "ürün çalışma zamanında yer almaz" kısmı doğru kalıyor. |
| 2 | **README/RUNBOOK zincirleri** (`depth: deepseek-v4-flash → laguna-s-2.1 → glm-5.2`; `dialogue: minimax-m2.7 → …`; `fast: ling-3.0-flash → qwen3-235b-a22b-2507`) **↔ kod**: `llm_gateway.py:44-49` tamamen farklı zincirler; `laguna/minimax/qwen3-235b` kodda yok. | Belge ↔ kod |
| 3 | **RUNBOOK: "X hedefi → analiz boş hedefle sürer"** **↔ kod + çalışma zamanı**: `run_mission` X'te erken dönüyor, analiz **başlamıyor** (`awaiting_authorization` sonucu gözlemlendi). | Belge ↔ davranış |
| 4 | **.env.example / RUNBOOK: `USE_LOCAL_LLM=true` ile yerel LLM** **↔ çalışma zamanı**: API sunucusu `use_local`'ı vault'tan ezerek False yapıyor (`get_room`); env `USE_LOCAL_LLM=true` iken room gateway `use_local=False` ölçüldü. .env yolu **yalnızca saf Python kullanımında** çalışıyor. | Config belgesi ↔ API davranışı |
| 5 | **README/.env.example: `OPENROUTER_TIER_2_MODEL`** **↔ kod**: hiçbir yerde okunmuyor. | Config ↔ kod |
| 6 | **.env.example: `OPENROUTER_MAX_SPEND_USD=0` (kapalı)** **↔ kod default 1.0 $** (`.env` yokken telemetry `llm_spend_cap_usd: 1.0` gösterdi). | Config ↔ kod |
| 7 | **README/RUNBOOK: "223 test"** **↔ gerçek: 347**. | Belge ↔ gerçeklik |

---

## 15. Runtime Test Results

```
INSTALL        = PASS   (pip, exit 0)
BUILD          = PASS   (frontend: svelte-check 0 hata, vite build OK, bundle doğrulandı)
LINT           = PASS   (ruff)
TEST           = PARTIAL (347 toplandı: 345 PASS, 2 FAIL, 0 SKIP — FAIL'ler test-kontrat sürüklenmesi)
START          = PASS   (uvicorn :8000, startup complete)
HEALTHCHECK    = PASS   (/api/telemetry 200, dürüst capability raporu)
BASIC REQUEST  = PASS   (WS+initiate→result; aspasia; vault; override; tasks; delete)
NEGATIVE       = PASS   (429 / 401 / 403 / 404 / 422 / awaiting_authorization / unsupported_platform)
AUTH MODE      = PASS   (token'lı ikinci örnek: 401/401/200 + WS reddi)
FULL PIPELINE  = PASS*  (*yerel sağlayıcı + stub model içeriğiyle; gerçek model içeriğiyle koşu NOT EXECUTED)
DOCKER         = NOT EXECUTED (docker yok)
RUST           = NOT EXECUTED (cargo yok)
ANDROID        = NOT EXECUTED (SDK yok; CI'da assembleDebug tanımlı)
INSTAGRAM SCRAPE = NOT EXECUTED (Chromium CDN erişilemez; gerçek platform erişimi yok)
LIVE OPENROUTER PAID CALL = NOT EXECUTED (API anahtarı yok)
```

---

## 16. Critical Blockers

1. **CI kırmızı:** `tests/unit/test_human_behavior.py`'daki 2 bayat test bu revizyonda `pytest`'i ve CI backend job'ını düşürür. (Düzeltme: iki assertion'ı yeni kontrata güncelle — 10 dk'lık iş.)
2. **Üretim güvenlik konumu belirsiz:** token'sız modda 0.0.0.0 bind + Docker port yayını = korumasız panel. Dağıtım yapılacaksa `PINEAL_TOKEN` zorunlu olmalı.
3. **Belge–kod uçurumu:** model zincirleri, USE_LOCAL_LLM yolu, X davranışı ve Tier-2 env'i hakkındaki belgeler yanlış yönlendiriyor; "slug'lar katalogdan doğrulandı" iddiası doğru ama zincir belgeleri eski.
4. **Maliyet muhasebesi sapması:** glm-5.2/deepseek-v4-pro fiyatları katalog minilerinin belirgin altında → spend cap erken kesmez, düşük sayar.

Bloklayıcı ürün hatası (özellik tamamen çalışmıyor) **bulunamadı**.

---

## 17. Evidence Table

| CLAIM | EVIDENCE | FILE:LINE / KOMUT | EXECUTION | RESULT | STATUS |
|---|---|---|---|---|---|
| "LLM destekli, OpenRouter/Ollama" | Gateway + AsyncOpenAI client | `llm_gateway.py:16,190-196` | local-provider e2e | sağlayıcıya HTTP gitti, ajanlar completed | WORKING (local) / NOT EXECUTED (cloud) |
| "Anahtar yoksa pipeline durur" | REAL_LLM_CALL_NOT_EXECUTED → halt | `llm_gateway.py:216-226` | WS koşusu anahtarsız | `result: halted_evidence` | VERIFIED |
| "Sıfır halüsinasyon / kanıt yoksa dur" | UncertaintyEngine + fallback reddi | `uncertainty_engine.py`, `task_executor.py` (mirror halt: "fallback sonuç kabul edilmedi") | stub jenerik içerik koşusu | 7 ajan dürüstçe halted | VERIFIED |
| "Rezonans <0.70 → halted_frequency" | score kontrolü | `task_executor.py` (resonance_calc bloğu) | unit+integration testleri | testler geçti | VERIFIED (test) / runtime NOT TRIGGERED |
| "6 Forensik Damga" | follower/timing/depth/visual/shadow/osint alanları | `task_executor.py`, `api.py:_send_snapshot` | WS snapshot + result | 6 damga alanı taşındı; visual NOT EXECUTED | PARTIAL (5/6 runtime'da doldu) |
| "Telemetri FIFO→WS sıralı kayıpsız" | _room_sender kuyruğu | `api.py` (TELEMETRI BUS) | canlı WS: 13 mesaj sıralı | result dahil ulaştı; `test_ws_ordering` geçti | VERIFIED |
| "PINEAL_TOKEN ile tüm API korunur" | middleware | `api.py:66-89` | token'lı örnek | 401/401/200 + WS reddi | VERIFIED |
| "initiate 5/dk, aspasia 20/dk" | rate_limit | `api.py:100-112` | 6× initiate | 6. istek 429 | VERIFIED (initiate) |
| "Retention: DELETE kalıcı siler" | endpoint | `api.py:api_delete_task` | canlı DELETE | dosya silindi; 404 doğru | VERIFIED |
| "Model slug'ları katalogdan doğrulandı" | OpenRouter API | 6 adet `/api/v1/models/*/endpoints` sorgusu (2026-08-29) | canlı katalog | 6/6 mevcut; 4/6 fiyat birebir, 2/6 düşük | VERIFIED (slug) / PARTIAL (fiyat) |
| "Rust: Python'a bağlı değil" | call-graph | grep: Python→rust çağrısı yok; run_task.py "tek halef" yorumu | statik | bağımsızlık teyit edildi | VERIFIED |
| "Rust: CI'da derlenmiyor" | ci.yml | `.github/workflows/ci.yml` rust-core job | statik | job mevcut → iddia ÇÜRÜTÜLDÜ | CONTRADICTED |
| "223 test" | pytest | `pytest --collect-only -q` | yürütüldü | 347 | CONTRADICTED (eskimiş) |
| "USE_LOCAL_LLM (.env) ile yerel model" | env-clobber | `api.py get_room` | canlı ölçüm | env yok sayıldı (False) | CONTRADICTED (API yolu) |
| "Instagram kazıma aktif" | scraper modülleri | `platform_registry.py`, `instagram_ghost.py` | chromium yok → launch hatası | kod VAR, koşu YOK | PARTIAL / NOT EXECUTED |

---

## 18. Recommended Fix Order

1. **(Kritik, dakikalar)** `tests/unit/test_human_behavior.py`'daki 2 bayat assertion'ı yeni sinyal tiplerine (`passive_voice_observation`, `visual_edge_density` + `_force_legacy_crop_for_tests`) güncelle → CI yeşile döner.
2. **(Kritik, güvenlik)** Varsayılanı güvenli çevir: `PINEAL_REQUIRE_AUTH=true` + bind `127.0.0.1` (Docker dışında), veya Dockerfile'da token zorunluluğu.
3. **(Yüksek)** README/RUNBOOK'taki model zincir bölümünü `llm_gateway.CHAINS` ile senkronize et; `laguna/minimax/qwen3` satırlarını sil; "rust_core CI'da derlenmiyor" cümlesini ci.yml ile uyumla; X-hedefi satırını "analiz başlamaz, yetki bekler" olarak düzelt; "223" sayısını kaldır (komut zaten var).
4. **(Yüksek)** `api.py get_room`'da `USE_LOCAL_LLM` env'ine saygı: `use_local = vault.get("use_local", os.getenv("USE_LOCAL_LLM")=="true")`; `OPENROUTER_TIER_2_MODEL`'ı ya oku ya belgelerden çıkar.
5. **(Orta)** `MODEL_PRICING`'i canlı katalog değerleriyle güncelle (özellikle `z-ai/glm-5.2`, `deepseek-v4-pro`); spend-cap ile gerçek maliyet arasındaki sapmayı kapat.
6. **(Orta)** `AspasiaChief.preferred_model` + `set_preferred_model`'ı ya bağla ya sil; `litellm`'i requirements'tan çıkar (open-interpreter zaten çekiyor); `open-interpreter`'ı opsiyonel gruba taşı (`requirements-ml.txt` gibi) veya extras ile izole et.
7. **(Düşük)** `api_delete_task`'a `task_id` whitelist regex'i ekle (savunma derinliği); CORS methods/headers'ı daralt; canlı OpenRouter + gerçek Instagram koşusu için bir "live verification" runbook adımı ekle (bir sonraki denetimin HEALTHCHECK'i olarak).

---

### Kesinlik Beyanı

- **Yüksek kesinlik (çalışma zamanı, tekrarlanabilir):** §2'deki 22 madde, §4 test hataları, §5 ölü kod/config, §14 çelişkiler 3-7.
- **Orta kesinlik (kod incelemesi + kısmi yürütme):** AI zincir tablosundaki tekil ajan satırları, güvenlik bulguları 2/3/5/6.
- **Düşük kesinlik / UNKNOWN:** Rust runtime, Android runtime, Tauri, üretim LLM çıktı kalitesi, gerçek Instagram davranışı, Docker imaj davranışı — hiçbiri "çalışıyor" diye **ilan edilmemiştir**.
