# PINEAL-CLEAN — ADLİ YAZILIM İNCELEME RAPORU

**Tarih:** 2026-08-29 (UTC)  
**Hedef:** https://github.com/AppleCurse/pineal-clean  
**Branch (inceleme anı):** `arena/01a04b6e-pineal-clean` @ `fda9940`  
**İnceleme yöntemi:** Kaynak kod okuma + bağımlılık kurulumu + test koşumu + canlı HTTP/WS duman testi + frontend build. README iddiaları kanıt sayılmamıştır.

**Ortam kısıtları (bu sandbox):**
- `OPENROUTER_API_KEY` yok → canlı LLM / OpenRouter [NOT_EXECUTED]
- Docker yok → imaj build [NOT_EXECUTED]
- `cargo`/`rustc` yok → rust_core derleme [NOT_EXECUTED]
- Android `gradlew` yok → Android assemble [NOT_EXECUTED]
- Playwright Chromium binary yok → Instagram scrape runtime [NOT_EXECUTED]

---

## 1. EXECUTIVE SUMMARY

Bu depo, **tek kullanıcılı yerel bir analiz istasyonu** olarak tasarlanmış hibrit bir sistemdir:

| Katman | Gerçek durum (kanıtlı) |
|---|---|
| FastAPI API (`backend/api.py`) | **Ayağa kalkıyor**, endpoint’ler yanıt veriyor [PROVEN] |
| Svelte UI (`frontend/`) | **Build + typecheck geçiyor**, API tarafından statik servis ediliyor [PROVEN] |
| Orchestrator (`PinealExecutor`) | Kod yolu bağlı; LLM kapalıyken **dürüstçe `halted_evidence`** [PROVEN] |
| LLM Gateway | OpenRouter/Ollama yolu kodda var; canlı çağrı bu ortamda **yapılmadı** [OBSERVED / NOT_EXECUTED] |
| Instagram scraper | Kod var; Chromium yüklü değil → capability `false` [PROVEN] |
| X scraper | Bilinçli devre dışı; yetki kapısı çalışıyor [PROVEN] |
| 7-Pillar deterministik motorlar | Executor’da çağrılıyor; girdi zayıfsa `INSUFFICIENT_DATA` [PROVEN] |
| `rust_core/` | Python ürün yoluna bağlı değil; bu ortamda derlenemedi [OBSERVED / NOT_EXECUTED] |
| `android/` | Ayrı Gemini edge uygulaması; Python backend’e HTTP ile bağlı değil [OBSERVED] |
| Testler | **347 collected; 345 passed, 2 failed** [PROVEN] |

**Tek cümlelik gerçeklik:**  
Altyapı (API + UI + orchestrator + bellek + güvenlik kapıları) **çalışır durumda**. Ürünün vaat ettiği **360° LLM destekli insan tanıma çıktısı**, anahtar + `LIVE_LLM_E2E`/vault unlock + (IG için) tarayıcı olmadan **tamamlanmaz**; sistem bunu gizlemez, durur. İki birim testi, `HumanBehaviorAnalyzer` sözleşme kayması nedeniyle kırmızıdır.

---

## 2. REPOSITORY HEALTH SCORE

### Skor: **62 / 100**

### Metodoloji (ağırlıklar, spekülasyon yok)

| Boyut | Ağırlık | Puan (0–10) | Gerekçe |
|---|---:|---:|---|
| Boot / entrypoint | 15% | 9 | uvicorn + frontend build + `/` 200 [PROVEN] |
| Core orchestration | 15% | 8 | Executor zinciri bağlı; LLM yokken halt doğru [PROVEN] |
| Test reality | 15% | 7 | 345/347 yeşil; 2 fail [PROVEN] |
| AI/LLM path completeness | 15% | 3 | Canlı LLM bu ortamda yok; kapı tasarımı sağlam ama uçtan uca [NOT_EXECUTED] |
| Scraper / external I/O | 10% | 3 | Chromium yok; IG capability false; X unsupported [PROVEN] |
| Security posture | 10% | 7 | Token auth, rate limit, interpreter default off, LIVE_LLM gate [PROVEN]; interpreter route riski var |
| Dependency honesty | 10% | 5 | Eksik beyan (PyYAML), env isim uyumsuzlukları, kullanılmayan litellm yolu [PROVEN] |
| Dead/experimental surface | 5% | 5 | p2p boş, reflection.sql ölü, rust/android ayrı [PROVEN] |
| Docs vs reality | 5% | 4 | Test sayısı, rust CI, TIER_2 env iddiaları çelişiyor [PROVEN] |

Hesap: \(0.15\cdot9 + 0.15\cdot8 + 0.15\cdot7 + 0.15\cdot3 + 0.10\cdot3 + 0.10\cdot7 + 0.10\cdot5 + 0.05\cdot5 + 0.05\cdot4 = 6.20\) → **62/100**.

**Yorum (kanıttan ayrılmış):** Skor “iskelet sağlam, vaat edilen tam analitik çıktı bu ortamda doğrulanamadı” anlamına gelir. 80+ için canlı LLM gate + Chromium + kırık testlerin düzeltilmesi gerekir.

---

## 3. REPOSITORY ENVANTERİ

### 3.1 Üst düzey ağaç

```
pineal-clean/
├── main.py                 # CLI demo entry (PinealExecutor)
├── live_llm_gate.py        # Manuel canlı LLM release gate
├── scraper.py              # X scraper — bilerek unsupported
├── backend/api.py          # FastAPI uygulama (asıl sunucu entry)
├── agent_core/             # Orchestrator, ajanlar, servisler, motorlar
├── frontend/               # Svelte 5 + Vite UI
├── config/decision_config.yaml
├── rust_core/              # Deneysel Rust + Tauri iskeleti
├── android/                # Ayrı Kotlin/Compose + Gemini uygulama
├── scripts/                # run_task, e2e, analyze helpers
├── tests/                  # unit + integration + e2e
├── docs/reports/           # Önceki adli notlar
├── Dockerfile, docker-compose.yml
├── requirements.txt, requirements-ml.txt
├── .env.example, .github/workflows/ci.yml
└── baslat.bat              # Windows tek komut başlatıcı
```

### 3.2 agent_core alt envanter

| Alt sistem | Konum | Runtime’a bağlı mı? |
|---|---|---|
| Orchestrator | `task_executor.py` | Evet — API `get_room` → `PinealExecutor` |
| Router | `services/cognitive_router.py` | Evet |
| LLM | `services/llm_gateway.py` | Evet (çağrı kapıya bağlı) |
| Memory | `canonical_memory.py` / `hindsight_memory.py` | Canonical varsayılan; hindsight opsiyonel ML |
| Search | `search_engine.py` | Verifier + X alternatif research |
| Vision | `vision_analyzer.py` | Executor, HTTP image varsa |
| Agents | `agents/*` (14 dosya) | Router + post-loop |
| Engines | `engines/*` (7 pillar) | Executor başında |
| Aspasia | `aspasia/aspasia_chief.py` | `/api/aspasia/chat` |
| Shadow | `shadow/shadow_executor.py` | Executor post-loop + experimental API |
| Chat/Dialogue | `chat/dialogue_manager.py` | Yalnız experimental |
| NLP/Psych | `nlp/dark_nlp.py`, `psychology/dark_triad.py` | Shadow yolu |
| Scraper | `scraper/instagram_ghost.py` | `platform_registry.scrape_instagram` |
| p2p | `p2p/__init__.py` (0 byte) | **Hayır — boş paket** |
| db | `db/reflection.sql` | **Hayır — hiçbir Python referansı yok** |

---

## 4. ENTRY POINT HARİTASI

### 4.1 Üretim entry (asıl)

```
CMD/uvicorn
  └─ backend.api:app          [PROVEN — process dinliyor :8000]
       ├─ StaticFiles(frontend/dist)   [PROVEN — HTTP 200, PINEAL-HERETIC JS]
       ├─ WS /ws/{client_id}
       └─ REST /api/*
            └─ run_mission → PinealExecutor.execute_task
```

**CLAIM:** Sistem gerçekten `uvicorn backend.api:app` ile başlar.  
**EVIDENCE:** Dockerfile `CMD`, `baslat.bat`, CI smoke, bu incelemede process log: `Uvicorn running on http://0.0.0.0:8000`.  
**FILE:** `Dockerfile` L41; `baslat.bat`; CI `.github/workflows/ci.yml`  
**STATUS:** [PROVEN] **CONFIDENCE:** HIGH

### 4.2 Diğer entry’ler

| Entry | Ne yapar | Ürün yolunda mı? |
|---|---|---|
| `main.py` | Sabit fixture ile `PinealExecutor` | Demo/CLI [OBSERVED] |
| `scripts/run_task.py` | stdin JSON → registry → executor (Rust TaskManager köprüsü) | Rust yolu için [OBSERVED] |
| `live_llm_gate.py` | Canlı OpenRouter gate | Manuel [OBSERVED], burada [NOT_EXECUTED] |
| `scraper.py` | X — `XScraperUnsupportedError` | Kazıma yok [OBSERVED] |
| Android `MainActivity` | Gemini edge pipeline | Python’dan bağımsız [OBSERVED] |
| Tauri `rust_core/src-tauri` | Masaüstü kabuk iskeleti | Ürün yolunda değil [OBSERVED] |

### 4.3 Execution chain (doğrulanmış halkalar)

```
USER (Svelte)
  ↓ apiFetch / WebSocket                    [PROVEN]
FastAPI backend/api.py
  ├─ auth_middleware (PINEAL_TOKEN?)        [PROVEN]
  ├─ rate_limit initiate/aspasia            [PROVEN — 6. istek 429]
  ├─ get_room → PinealExecutor + vault      [PROVEN]
  ├─ platform_registry.effective_scraper_type
  │    ├─ x → awaiting_authorization        [PROVEN kod + initiate]
  │    ├─ unsupported_web → halt            [OBSERVED kod]
  │    └─ instagram → scrape_instagram      [OBSERVED kod; runtime browser YOK]
  └─ PinealExecutor.execute_task            [PROVEN]
       ├─ follower_audit + timing_forensics [PROVEN — memory/log]
       ├─ VisionAnalyzer (http images)      [OBSERVED; bu koşuda image yok]
       ├─ PillarOrchestrator (7 engine)     [PROVEN — evidence_chain]
       ├─ CognitiveRouter.analyze → agents  [PROVEN — planned_agents]
       ├─ per-agent execute + UncertaintyEngine
       │    └─ LLMGateway.query*            [OBSERVED; LIVE kapalı → fail/fallback]
       ├─ deferred: pattern_interrupt, resonance_synthesizer
       ├─ HolisticProfile assemble
       ├─ depth_analyst (post)
       ├─ shadow_executor + osint_investigator (post)
       ├─ DecisionEngine.make_decision
       └─ CanonicalMemory.merge_evidence    [PROVEN — memory/*.json]
  ↓ FIFO queue → WebSocket
UI snapshot/log/result                      [PROVEN — TestClient WS mesajları]
```

**Doğrulanamayan halka:** OpenRouter’a gerçek HTTPS completion + Instagram DOM scrape + Tavily/SerpAPI/Exa canlı arama → **[UNVERIFIED / NOT_EXECUTED]**

---

## 5. VERIFIED WORKING COMPONENTS

### 5.1 FastAPI sunucu + statik UI

**CLAIM:** API ayağa kalkar; UI build edilince `/` gerçek uygulamayı sunar.  
**EVIDENCE:**
- `curl /` → HTTP 200, `index.html` + `assets/index-*.js`
- JS içinde `PINEAL-HERETIC v3.0` string’i
- `npm run build` başarılı; `svelte-check` 0 error / 0 warning  
**STATUS:** [PROVEN] **CONFIDENCE:** HIGH

### 5.2 Telemetri endpoint

```json
{
  "core": true,
  "gateway": false,
  "scraper": false,
  "instagram_scraper": false,
  "browser_installed": false,
  "x_scraper": false,
  "llm_spend_cap_usd": 1.0
}
```
**STATUS:** [PROVEN]

### 5.3 Aspasia graceful fallback (LLM kapalı)

**CLAIM:** Anahtarsız Aspasia uydurma telemetri yerine fallback mesaj döner.  
**EVIDENCE:** POST `/api/aspasia/chat` → `confidence_assessment: "fallback"`, mesajda `REAL_LLM_CALL_NOT_EXECUTED`.  
**STATUS:** [PROVEN]

### 5.4 Initiate + pipeline halt (LLM kapalı)

**CLAIM:** Görev başlar; mirror_truth LLM’siz fallback’i uncertainty reddeder → `halted_evidence`.  
**EVIDENCE:**  
```
STATUS halted_evidence
PLANNED [mirror_truth, interpreter, autonomous_verifier, ...]
COMPLETED []
AGENTS {'pineal_7pillar': 'completed', 'mirror_truth': 'halted'}
```
WS: `snapshot_update` status `halted_evidence`.  
Memory: `memory/forensic_op_1.json` evidence_count 1 (7pillar).  
**STATUS:** [PROVEN]

### 5.5 Rate limit

6. `POST /api/initiate` aynı client → **429** [PROVEN]

### 5.6 Auth (PINEAL_TOKEN)

Token set → `/api/*` 401 without key; 200 with `X-API-Key`; WS token’sız disconnect [PROVEN]

### 5.7 Vault

POST `/api/vault` fake key → telemetry `gateway: true`, `vault: true` [PROVEN]  
(Canlı OpenRouter çağrısı yapılmadı; sahte anahtar ile auth hatası beklenir.)

### 5.8 Intervention safety

`HALT` → `review_required`, otomatik uygulanmaz [PROVEN]

### 5.9 Interpreter default disabled

POST experimental interpreter → **403** [PROVEN]

### 5.10 X platform gate

X URL initiate → started; kod yolu `awaiting_authorization` (analiz başlatılmaz) [OBSERVED kod + API accepted]

### 5.11 Ruff

`ruff check .` → All checks passed [PROVEN]

### 5.12 Pytest (çoğunluk)

**347 collected, 345 passed, 2 failed, 42.62s** [PROVEN]

### 5.13 Deterministik 7-pillar

Executor’da çalışır; zayıf girdide status `INSUFFICIENT_DATA`, yine de `completed` agent_run + evidence kaydı [PROVEN]

### 5.14 Canonical memory

`memory/<task_id>.json` yazılıyor [PROVEN]

---

## 6. PARTIALLY WORKING COMPONENTS

| Bileşen | Kod | Çağrılıyor | Test | Runtime | Durum |
|---|---|---|---|---|---|
| LLMGateway | Var | Evet | Çok unit | Canlı çağrı yok | PARTIALLY WORKING |
| Tüm LLM ajanları (mirror, passion, friction, cognitive, synthesizer, pattern_interrupt, authenticity, depth) | Var | Router/executor | Mock/unit | LLM kapalı halt/fallback | PARTIALLY WORKING |
| SearchEngine | Var | Verifier + alt research | Unit | Anahtarsız DDG yolu kodda; canlı [NOT_EXECUTED] | PARTIALLY WORKING |
| InstagramGhostScraper | Var | platform_registry | Unit/mocks | browser_installed=false | PARTIALLY WORKING |
| HumanBehaviorAnalyzer | Var | Router | 8 pass / 2 fail | Deterministik kısımlar çalışır; sinyal sözlüğü testle uyumsuz | PARTIALLY WORKING |
| VisionAnalyzer | Var | Executor (http images) | Unit | Bu koşuda tetiklenmedi | UNTESTED (runtime) |
| HindsightMemory | Var | env `PINEAL_MEMORY_ENGINE` | Unit | sentence-transformers yok | PARTIALLY WORKING / UNUSED default |
| Shadow + DarkTriad | Var | Executor + experimental | Unit | Heuristik TR marker; EN metinde 0 skor | PARTIALLY WORKING |
| Aspasia | Var | API + UI | Integration | Fallback çalışır; gerçek LLM [NOT_EXECUTED] | PARTIALLY WORKING |
| Frontend API yüzeyi | Var | vault/initiate/aspasia/intervene | Build | tasks/telemetry HTTP/experimental çağırmıyor | PARTIALLY WORKING |

---

## 7. BROKEN COMPONENTS

### 7.1 HumanBehaviorAnalyzer ↔ test sözleşmesi [PROVEN]

**CLAIM:** İki unit test kırık; üretim kodu testlerin beklediği `signal_type` değerlerini üretmiyor.

| Test | Beklenen | Kodun ürettiği |
|---|---|---|
| `test_linguistic_forensics` | `signal_type=="contradiction"` + `passive_voice` location | `passive_voice_observation` + `location="linguistic"` |
| `test_analyze_visual_micro` | `signal_type=="tension"` | `visual_edge_density` |

**FILE:** `agent_core/agents/human_behavior.py` (~L333, ~L384); `tests/unit/test_human_behavior.py` L15, L114  
**STATUS:** [PROVEN] — `pytest` 2 failed  
**Etki:** CI `backend` job’u bu haliyle kırmızı olur (CI `pytest -q` çalıştırıyor).

### 7.2 Playwright Chromium yok [PROVEN]

```
exe .../chromium-.../chrome exists False
telemetry.browser_installed = false
telemetry.instagram_scraper = false
```
`pip install playwright` paket kurar; browser binary ayrı `playwright install chromium` ister. Bu ortamda kurulmadı. Dockerfile kurar; manuel/venv yolu kurmazsa IG scrape çalışmaz.

### 7.3 Env / config çelişkileri (davranışsal bug)

#### A) `OPENROUTER_TIER_2_MODEL` env yok sayılıyor

```python
# llm_gateway.py
TIER_1_MODEL = os.getenv("OPENROUTER_TIER_1_MODEL", ...)  # OK
TIER_2_MODEL = MODEL_REGISTRY["ling_3_flash"]  # ENV OKUNMUYOR
```
`.env.example` ve README TIER_2’nin env ile ezileceğini iddia ediyor.  
**STATUS:** [CONTRADICTED] docs vs code

#### B) SerpAPI env adı uyumsuz

| Yer | Değişken |
|---|---|
| `.env.example` / `SearchEngine` | `SERPAPI_API_KEY` |
| `backend/api.py` get_room | `os.getenv("SERPAPI_KEY")` |

Vault UI’dan set edilirse çalışır; yalnız `.env` ile `SERPAPI_API_KEY` doldurulursa room bootstrap kaçırabilir.  
**STATUS:** [PROVEN] kod farkı

#### C) Spend cap default

| Kaynak | Değer |
|---|---|
| `.env.example` | `OPENROUTER_MAX_SPEND_USD=0` (sınırsız) |
| `LLMGateway.__init__` default | `1.0` USD |

Env yokken telemetry `llm_spend_cap_usd: 1.0` [PROVEN].  
**STATUS:** [CONTRADICTED]

---

## 8. DEAD CODE / UNUSED

| Öğe | Kanıt | Durum |
|---|---|---|
| `agent_core/p2p/` | Sadece boş `__init__.py`; import yok | DEAD / PLACEHOLDER |
| `agent_core/db/reflection.sql` | `rg` sıfır Python referansı | DEAD |
| `litellm` (requirements) | Ana gateway `openai.AsyncOpenAI`; litellm import üretim yolunda yok (open-interpreter alt bağımlılığı olarak devreye girer) | UNUSED direct / transitive |
| Frontend → `/api/tasks`, DELETE, `/api/override`, `/api/telemetry` HTTP, `/api/scraper/authorize-alternative`, `/api/experimental/*` | `rg` frontend’de yok | API var, UI UNUSED |
| `rust_core` → Python ürün WS/API | Bağlı değil; ayrı subprocess köprüleri var | EXPERIMENTAL / UNUSED in main path |
| Android → Python backend | Gemini direct; `localhost:8000` yok | PARALLEL PRODUCT |
| `main.py` hardcoded images `./target_photo_*.jpg` | Dosyalar yok | DEMO path kırılgan |

---

## 9. MOCK / FAKE / PLACEHOLDER

| Bulgu | Production path’te mi? | Kritiklik |
|---|---|---|
| LLM `LIVE_LLM_E2E` / `live_unlocked` kapısı — canlı çağrı reddi | Evet | Tasarım; CRITICAL değil (dürüst fail) |
| Ajan `fallback_reason` / `data_confidence=False` | Evet | Tasarım; uncertainty çoğu fallback’i reddeder |
| DarkTriad kelime sayacı (TR marker listesi) | Shadow + experimental | Düşük bilimsel geçerlilik; “ML” değil heuristik [OBSERVED] |
| Dark NLP template cümle üretici | Shadow generate | Template/placeholder metin [OBSERVED] |
| Android `PinealAnalyzerEngine` | Android only | LLM’e “tahmin” prompt’u; ayrı ürün [OBSERVED] |
| `InterpreterAgent` default prompt `"Sistem durumunu kontrol et."` | Router `has_user` iken zincirde | **CRITICAL risk:** ana pipeline’da open-interpreter tetiklenebilir |

### CRITICAL: Interpreter ana rotada

**CLAIM:** `CognitiveRouter`, kullanıcı verisi varken `interpreter` ajanını route’a ekler.  
**EVIDENCE:** `cognitive_router.py` L46–48 `agents.append('interpreter')`.  
`InterpreterAgent.execute` → `open-interpreter` kod çalıştırma yığını.  
Experimental HTTP kapalı (403) olsa da **executor route’u açık**.  
LLM/anahtar yokken hata ile geçer (graceful non-critical); anahtar+unlock varken risk artar.  
**STATUS:** [PROVEN] wiring **CONFIDENCE:** HIGH

---

## 10. UNTESTED / UNKNOWN / NOT_EXECUTED

| Alan | Durum |
|---|---|
| Canlı OpenRouter completion | NOT_EXECUTED (anahtar yok) |
| `live_llm_gate.py` | NOT_EXECUTED |
| Instagram gerçek profil scrape | NOT_EXECUTED (Chromium yok) |
| Tavily/SerpAPI/Exa canlı | NOT_EXECUTED |
| DuckDuckGo fallback canlı kalite | UNKNOWN |
| Docker build/compose | NOT_EXECUTED (docker binary yok) |
| `cargo test` rust_core | NOT_EXECUTED |
| Android `assembleDebug` | NOT_EXECUTED (gradlew yok) |
| Ollama local LLM | NOT_EXECUTED |
| Çoklu tarayıcı E2E UI | NOT_EXECUTED |
| Coverage % | UNKNOWN (coverage raporu üretilmedi) |

---

## 11. SECURITY FINDINGS

### S1 — Open Interpreter üretim rotasında [PROVEN]

- **FILE:** `agent_core/services/cognitive_router.py`, `agent_core/agents/interpreter_agent.py`
- **RISK:** Arbitrary code execution yüzeyi (kütüphane amaçlı)
- **EXPLOITABILITY:** Orta — LLM/auto_run kapıları var; yine de gereksiz attack surface
- **EVIDENCE:** Router append; `from interpreter import interpreter`; HTTP endpoint env ile kapalı ama agent registry’de
- **RECOMMENDATION:** Router’dan çıkar; yalnız `ENABLE_INTERPRETER=true` iken registry’ye ekle

### S2 — Experimental shadow/chat auth opsiyonel [OBSERVED]

`PINEAL_TOKEN` yokken tüm API açık (tasarım: yerel tek kullanıcı). LAN’da bind `0.0.0.0` ise risk.

### S3 — SSRF sertleştirme human_behavior image fetch [OBSERVED]

DNS/IP private check kodu mevcut (`human_behavior.py`). Tam bypass testi bu raporda koşulmadı → residual UNKNOWN.

### S4 — Secret tarama [PROVEN negative]

Repoda commit’li gerçek `sk-or-v1-...` / `.env` / `.pineal_vault.json` yok.  
`.gitignore` `.env` ve vault’u dışlıyor.

### S5 — Hardcoded secret yok [OBSERVED]

Raporlanacak SECRET DETECTED yok.

### S6 — Rate limit [PROVEN]

Initiate 5/dk, Aspasia 20/dk — in-memory; multi-worker’da paylaşımsız (bilinçli basitlik).

### S7 — CORS [OBSERVED]

Default localhost kümesi; `*` strip ediliyor.

---

## 12. DEPENDENCY FINDINGS

### requirements.txt (beyan)

`pydantic, httpx, litellm, open-interpreter, fastapi, uvicorn, playwright, playwright-stealth, openai, opencv-python-headless, numpy, aiofiles, python-dotenv`

### A) Kullanılıyor, requirements’ta yok / dolaylı

| Paket | Kullanım | requirements |
|---|---|---|
| `PyYAML` | `config_loader.py` | **Yok** — bu venv’de 6.0.3 kuruldu (muhtemel transitive). Çıplak install’da risk. |
| `aiohttp` | `osint_investigator.py` | **Yok** — transitive olabilir |
| `starlette` | FastAPI | transitive OK |
| `pytest`, `ruff` | CI | requirements’ta yok; CI ayrıca kuruyor OK |

### B) Beyan var, doğrudan az/hiç kullanılmayan

| Paket | Bulgu |
|---|---|
| `litellm` | Gateway kullanmıyor; open-interpreter içinden sızıyor |
| `open-interpreter` | Yalnız InterpreterAgent; ana vaat için zorunlu değil |

### C) Opsiyonel

`requirements-ml.txt` → `sentence-transformers` (Hindsight). Kurulu değil → hindsight açılamaz [PROVEN ModuleNotFoundError]

### D) Versiyon notu

Kurulu örnekler: fastapi 0.115.2, openai 3.6.0, playwright 1.62.0, cv2 4.14.0, numpy 2.4.6.

---

## 13. AI / AGENT FINDINGS

### 13.1 LLMGateway

| Özellik | Kanıt |
|---|---|
| Provider | OpenRouter `https://openrouter.ai/api/v1` via `AsyncOpenAI` [OBSERVED] |
| Local | Ollama uyumlu `LOCAL_LLM_URL` [OBSERVED] |
| Gate | `LIVE_LLM_E2E!=1` ve `live_unlocked=False` → `REAL_LLM_CALL_NOT_EXECUTED` [PROVEN] |
| Vault unlock | `set_key(..., unlock_live=True)` [PROVEN telemetry gateway true] |
| Retry / circuit breaker / spend cap / pricing guard / cache | Kodda mevcut [OBSERVED]; unit testler çoğunlukla geçiyor |
| query_chain / agent chains | Kodda [OBSERVED] |

**Canlı model çağrısı:** [NOT_EXECUTED]

### 13.2 Agent matrisi

| Agent | LLM? | Route? | Executor sahipliği | Failure |
|---|---|---|---|---|
| mirror_truth | Evet | has_user | main loop | critical; fallback uncertainty halt [PROVEN] |
| interpreter | open-interpreter | has_user | main loop | non-critical error |
| autonomous_verifier | Search (+?) | has_target | main | graceful |
| human_behavior | Hibrit (det + LLM) | has_target | main | |
| passion_mapper | Evet | has_target | main | critical list |
| friction_detector | Evet | has_target | main | |
| cognitive_profiler | Evet | has_target | main | |
| authenticity_auditor | Evet | yalnız `visual_evidence` varsa | main | |
| resonance_calc | Hayır (numpy) | has_user∧target | main | <0.70 → halted_frequency |
| pattern_interrupt | Evet | deferred | main | |
| resonance_synthesizer | Evet | deferred | main | |
| depth_analyst | Evet | route dışı post | post | skip on error |
| shadow_executor | Hibrit | route dışı post | post | |
| osint_investigator | Provider HTTP | route dışı post (çift çağrı engeli bilinçli) | post | credentials yok → unavailable |

### 13.3 Model registry (kod)

`upstage/solar-pro4`, `inclusionai/ling-3.0-flash`, `deepseek/*`, `z-ai/glm-5.2`, `google/gemini-3.7-flash` — **katalogda isim var ≠ erişilebilir**. Canlı doğrulama yok.

---

## 14. API FINDINGS

| Method | Path | Auth | UI kullanır? | Runtime smoke |
|---|---|---|---|---|
| WS | `/ws/{client_id}` | token query | Evet | PROVEN mesaj akışı |
| POST | `/api/initiate` | optional | Evet | PROVEN 200 + pipeline |
| POST | `/api/vault` | optional | Evet | PROVEN |
| POST | `/api/aspasia/chat` | optional + RL | Evet | PROVEN fallback |
| POST | `/api/executor/intervene` | optional | Evet | PROVEN review_required |
| GET | `/api/telemetry` | optional | **Hayır** (HTTP) | PROVEN |
| POST | `/api/override` | optional | Hayır | PROVEN sealed |
| GET | `/api/tasks` | optional | Hayır | PROVEN |
| DELETE | `/api/tasks/{id}` | optional | Hayır | PROVEN 404 |
| POST | `/api/scraper/authorize-alternative` | optional | Hayır | kod OBSERVED |
| POST | `/api/experimental/shadow/*` | optional | Hayır | analyze PROVEN |
| POST | `/api/experimental/chat/respond` | optional | Hayır | NOT_EXECUTED |
| POST | `/api/experimental/interpreter/execute` | optional | Hayır | PROVEN 403 |

**Frontend çağırıp backend’de olmayan endpoint:** Yok [OBSERVED].  
**Backend var frontend yok:** tasks, override, telemetry HTTP, authorize-alternative, experimental — [PROVEN].

---

## 15. DATABASE FINDINGS

| Depolama | Teknoloji | Kullanım |
|---|---|---|
| Görev kanıtı | `memory/<task_id>.json` | CanonicalMemory [PROVEN] |
| LLM cache | SQLite `cache/responses.db` | ResponseCache env ile [OBSERVED] |
| Hindsight | SQLite + embeddings | Opsiyonel, ML yoksa kapalı |
| `reflection.sql` | SQL şema dosyası | **Hiç migrate/execute edilmiyor** [PROVEN dead] |
| Klasik RDBMS | Yok | Bilinçli (ARCHITECTURE) |

**CLAIM:** “Database yok” iddiası görev kanıtı için doğru; cache/hindsight SQLite istisnaları var.  
**STATUS:** [PROVEN]

---

## 16. DEPLOYMENT FINDINGS

| Yöntem | Durum |
|---|---|
| `uvicorn` manuel | **PROVEN çalışır** (frontend dist şart) |
| `baslat.bat` | Windows script; bu Linux ortamda koşulmadı [NOT_EXECUTED] |
| Docker | Dockerfile multi-stage mantıklı; **build bu ortamda yok** [NOT_EXECUTED] |
| docker-compose | volume + port 8000; docker yok [NOT_EXECUTED] |
| Vercel/Railway | Konfig yok [OBSERVED] |
| CI | ruff+pytest+frontend+smoke+rust+android tanımlı; android `gradlew` repoda yok → android job kırılgan [OBSERVED] |
| Healthcheck | Dockerfile python urllib telemetry [OBSERVED] |

**ARCHITECTURE.md** “rust CI’da derlenmiyor” diyor; **CI dosyası** `rust-core` job içeriyor → doküman eski [CONTRADICTED].

---

## 17. EXECUTION GRAPH (yalnız doğrulanan)

```
[BROWSER UI build artifacts]
        │ HTTP/WS
        ▼
[FastAPI :8000] ──auth?── rate limit?
        │
        ├─ /api/vault ──► LLMGateway.set_key / SearchEngine.set_keys
        ├─ /api/aspasia/chat ──► AspasiaChief ──► LLMGateway [gate]
        │                              └─ fallback message [PROVEN]
        └─ /api/initiate ──► run_mission
                │
                ├─ platform x/unsupported ──► halt/authorize [no executor]
                ├─ instagram ──► Playwright [browser missing → fail path]
                └─ PinealExecutor
                        │
                        ├─ forensics (follower, timing) ── deterministic
                        ├─ 7-pillar bundle ── deterministic
                        ├─ CognitiveRouter ── agent list
                        ├─ agents* ──► LLMGateway ──► OpenRouter/Ollama
                        │                 [UNVERIFIED live]
                        ├─ DecisionEngine
                        └─ CanonicalMemory JSON
                                │
                                ▼
                        WS FIFO ──► UI panels
```

---

## 18. CRITICAL BLOCKERS (tam 360° “çalışıyor” iddiası için)

1. **Canlı LLM yok** → pipeline `halted_evidence` (tasarım + bu ortam)  
2. **Chromium yok** → Instagram scrape capability false  
3. **2 failing unit test** → CI backend kırmızı  
4. **Interpreter’ın ana route’ta olması** → güvenlik/istikrar blocker adayı  
5. **TIER_2 / SERPAPI / spend-cap config yalanları** → operasyonel sürpriz  
6. **Android gradlew eksik** → CI android job  
7. **Docker/Rust bu ortamda doğrulanamadı**

---

## 19. EXACT FIX PLAN (öncelik sırası)

### P0 — CI yeşil + güvenlik yüzeyi

1. `tests/unit/test_human_behavior.py` beklentilerini koda hizala **veya** kodda `signal_type` geriye dönük uyumluluk ekle (`tension` alias / `contradiction`+location).  
2. `CognitiveRouter` içinden `interpreter`’ı kaldır; yalnızca `ENABLE_INTERPRETER=true` iken `PinealExecutor.agents`’a register et.  
3. `OPENROUTER_TIER_2_MODEL = os.getenv(..., MODEL_REGISTRY["ling_3_flash"])`.  
4. `backend/api.py`: `SERPAPI_KEY` → `SERPAPI_API_KEY` (veya her ikisini oku).  
5. Spend cap default’u `.env.example` ile hizala (`0` = unlimited).

### P1 — Çalıştırılabilirlik

6. README/RUNBOOK: `python -m playwright install chromium` zorunlu adım (Docker dışı).  
7. `requirements.txt` içine `PyYAML`, gerekirse `aiohttp` ekle.  
8. `litellm`’i doğrudan ihtiyaç yoksa çıkar veya gerçekten gateway’de kullan.  
9. Android: `gradlew` wrapper commit veya CI job’u düzelt.  
10. ARCHITECTURE.md rust CI ifadesini güncelle.

### P2 — Ürün tamamlığı

11. Frontend: tasks retention UI, X authorize-alternative sonucu, telemetry HTTP badge.  
12. `live_llm_gate.py`’yi gerçek anahtarla koş; modeli/slug’ları doğrula.  
13. DarkTriad EN/TR marker genişletmesi veya dil-agnostik olduğunu dokümante et.  
14. `p2p/`, `reflection.sql` kaldır veya bağla.  
15. README test sayısı 223 → dinamik (`pytest --collect-only`).

### P3 — Doğrulama komutları (kanıt üret)

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt ruff pytest pytest-asyncio
python -m playwright install chromium
ruff check .
pytest -q
cd frontend && npm ci && npm run check && npm run build && cd ..
uvicorn backend.api:app --host 0.0.0.0 --port 8000
# canlı:
# OPENROUTER_API_KEY=... LIVE_LLM_E2E=1 python live_llm_gate.py
```

---

## 20. MODÜL DURUM TABLOSU (özet)

| Modül | Kod | Import | Çağrılıyor | Test | Test geçiyor | Runtime | Durum |
|---|---|---|---|---|---|---|---|
| backend.api | ✓ | ✓ | ✓ | ✓ | çoğunluk | ✓ | WORKING |
| frontend | ✓ | ✓ | ✓ | check/build | ✓ | ✓ served | WORKING |
| PinealExecutor | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ halt path | PARTIALLY WORKING |
| LLMGateway | ✓ | ✓ | ✓ | ✓ | ✓ | gate only | PARTIALLY WORKING |
| CognitiveRouter | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | WORKING |
| CanonicalMemory | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | WORKING |
| 7-Pillar engines | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | WORKING (det.) |
| Instagram scraper | ✓ | ✓ | conditional | ✓ | ✓ | browser missing | PARTIALLY WORKING |
| X scraper | ✓ | ✓ | gate | ✓ | ✓ | unsupported | WORKING (as designed) |
| Aspasia | ✓ | ✓ | ✓ | ✓ | ✓ | fallback | PARTIALLY WORKING |
| HumanBehavior | ✓ | ✓ | ✓ | ✓ | **2 fail** | partial | PARTIALLY WORKING / BROKEN tests |
| Interpreter | ✓ | ✓ | route | ✓ | ✓ | HTTP 403 | PARTIALLY WORKING / RISK |
| OSINT | ✓ | ✓ | post-loop | ✓ | ✓ | no creds | PARTIALLY WORKING |
| Shadow/DarkTriad | ✓ | ✓ | post+exp | ✓ | ✓ | heuristic | PARTIALLY WORKING |
| SearchEngine | ✓ | ✓ | ✓ | ✓ | ✓ | live unknown | PARTIALLY WORKING |
| Hindsight | ✓ | env | optional | ✓ | ? | ML missing | UNUSED default |
| rust_core | ✓ | — | — | CI defined | NOT_EXECUTED | NOT linked | EXPERIMENTAL |
| android | ✓ | — | — | CI defined | NOT_EXECUTED | separate | EXPERIMENTAL/PARALLEL |
| p2p | empty | — | — | — | — | — | DEAD CODE |
| reflection.sql | ✓ | — | — | — | — | — | DEAD CODE |

---

## 21. BU İNCELEMEDE ÇALIŞTIRILAN KOMUT ÇIKTILARI (kanıt kaydı)

```
ruff check .                     → All checks passed!
pytest --collect-only -q         → 347 tests collected
pytest -q                        → 2 failed, 345 passed in 42.62s
npm run build                    → ✓ built
npm run check                    → 0 errors 0 warnings
uvicorn backend.api:app :8000    → Application startup complete
GET /api/telemetry               → core true, browser false, cap 1.0
GET /                            → 200 + PINEAL-HERETIC assets
POST /api/aspasia/chat           → fallback REAL_LLM_CALL_NOT_EXECUTED
POST /api/initiate ×6            → 200×5 + 429
POST interpreter                 → 403
Executor no-LLM                  → status=halted_evidence
```

---

## 22. SONUÇ — “REPO GERÇEKTE NE DURUMDA?”

**Çalışan:** Yerel komuta merkezi iskeleti — API, UI build, WebSocket telemetri bus, vault, rate limit, auth kapısı, görev bellek dosyaları, deterministik forensics/7-pillar, dürüst LLM kapısı ve halt semantiği.

**Çalışmayan / doğrulanamayan:** Vaat edilen uçtan uca “360° kanıta dayalı insan tanıma + vision + OSINT + canlı model zinciri” bu ortamda **tamamlanmadı** (anahtar + tarayıcı yok). İki test kırık. Config/docs drift var. Interpreter ana pipeline’da gereksiz risk. Rust/Android ana Python ürününün parçası değil.

**README = gerçeklik değil:** Test sayısı, TIER_2 env, spend cap default, rust CI ifadesi çelişiyor.

**Tek doğru özet cümlesi:**  
> Bu repo, dikkatle sertleştirilmiş bir **orkestrasyon iskeleti** sunar; iskelet ayakta. Üzerine bindirilen **canlı zekâ ve kazıma vaatleri**, harici anahtar/binary olmadan ve iki test düzeltilmeden “WORKING ürün” diye sertifikalanamaz.

---

## 23. BAĞIMSIZ DENETİM İLE ÇAPRAZ DOĞRULAMA (2026-08-29)

Aşağıdaki tablo, kullanıcı tarafından sağlanan bağımsız adli denetim metni ile bu incelemenin bulgularını karşılaştırır. Her satır yeniden kanıtlandı.

### 23.1 UYUM (her iki denetimde de kanıtlandı)

| Bulgu | Bu inceleme | Bağımsız | Yeniden doğrulama |
|---|---|---|---|
| 345/347 test; 2 human_behavior FAIL | PROVEN | PROVEN | pytest yeniden FAIL |
| API+UI+WS+halted_evidence iskeleti çalışır | PROVEN | PROVEN | uvicorn smoke |
| LIVE_LLM kapısı / anahtarsız dürüst halt | PROVEN | PROVEN | executor run |
| Rate limit 429, token 401, interpreter 403 | PROVEN | PROVEN | curl |
| TIER_2 env okunmuyor (ölü config) | PROVEN | PROVEN | llm_gateway.py:37 |
| Spend cap default 1.0 vs .env.example 0 | PROVEN | PROVEN | telemetry |
| SERPAPI_KEY vs SERPAPI_API_KEY drift | PROVEN | (bağımsızda yok/eksik) | api.py:199 |
| README 223 vs 347 test | PROVEN | PROVEN | collect-only |
| rust CI var; ARCH “CI’da yok” çelişkisi | PROVEN | PROVEN | ci.yml |
| X URL → analiz başlamaz (awaiting_authorization) | PROVEN | PROVEN | kod+API |
| RUNBOOK “analiz boş hedefle sürer” yanlış | — | PROVEN | RUNBOOK.md:34 vs api.py run_mission |
| Android ≠ Python backend | PROVEN | PROVEN | statik |
| rust_core ürün path’inde değil | PROVEN | PROVEN | call-graph |
| litellm doğrudan import yok | PROVEN | PROVEN | rg 0 hit |
| Production mock/fake response yok (anti-mock tasarım) | PROVEN | PROVEN | grep+runtime |
| Docker/Chromium/cargo bu ortamda NOT_EXECUTED | PROVEN | PROVEN | tool yok |

### 23.2 BAĞIMSIZ DENETİMİN EKLEDİĞİ — BU İNCELEMEDE DOĞRULANDI

| Yeni bulgu | Kanıt | STATUS |
|---|---|---|
| **`AspasiaChief.preferred_model = "muse-spark-1.2-xhigh"` ölü** | Yalnız assign/setter; `chat()` `selected_model = model_override` kullanır, `self.preferred_model` **hiç okunmaz**. MODEL_REGISTRY’de yok. | [PROVEN] DEAD |
| **`USE_LOCAL_LLM` API room bootstrap’ta eziliyor** | `LLMGateway.__init__` env okur → True; `get_room` sonra `use_local = vault.get("use_local", False)` ile **False yazar**. Runtime: standalone True → clobber False. | [PROVEN] CONTRADICTED (docs vs API path) |
| **README/RUNBOOK zincirleri kodda yok** | Docs: `laguna-s-2.1`, `minimax-m2.7`, `qwen3-235b-a22b-2507`. Kod CHAINS: solar-pro4/glm-5.2/deepseek-v4-*. `rg laguna` yalnız README/RUNBOOK. | [PROVEN] CONTRADICTED |
| **Interpreter gateway-dışı kendi LLM yolu** | `interpreter_agent.py` open-interpreter + kendi api_base; router has_user’da ekliyor. | [PROVEN] (bu incelemede de CRITICAL risk) |

### 23.3 BAĞIMSIZ DENETİMİN İDDİA EDİP BU ORTAMDA DOĞRULANAMAYANLARI

| İddia | Bu ortam | Hüküm |
|---|---|---|
| “6/6 OpenRouter slug katalogda VERIFIED” | `curl openrouter.ai` → TLS SSL_ERROR_SYSCALL; endpoints HTTP 000 | **[NOT_EXECUTED]** — ağ/TLS engeli. Bağımsız denetimin katalog sorgusu burada tekrarlanamadı. |
| “Local OpenAI-uyumlu provider ile full pipeline PASS (prov=llm)” | Yerel Ollama/stub provider kurulmadı | **[NOT_EXECUTED]** bu sandbox’ta. Mimari olarak mümkün [INFERRED from code]; runtime kanıtı bağımsızdan alıntı, burada yeniden üretilmedi. |
| “Model zinciri failover log: solar→glm→deepseek” | Aynı — local provider koşusu yok | **[NOT_EXECUTED]** burada; kod yolu `query_json_chain` [OBSERVED] |
| “glm-5.2 / deepseek-v4-pro fiyat sapması katalog minine göre düşük” | Katalog çekilemedi | **[UNKNOWN]** bu ortamda; kod fiyatları [OBSERVED] |
| “solar-pro4 discount 0.9 promo” | Katalog yok | **[UNKNOWN]** |

### 23.4 BU İNCELEMENİN BAĞIMSIZDA EKSİK / ZAYIF KALAN NOKTALARI

| Bulgu (bu inceleme) | Bağımsızda | Not |
|---|---|---|
| Interpreter’ın **CognitiveRouter ana rotasında** olması | Kısmen (interpreter satırı var; CRITICAL blocker olarak zayıf) | Güvenlik yüzeyi olarak P0 kalmalı |
| `SERPAPI_KEY` vs `SERPAPI_API_KEY` | Belirtilmemiş | Operasyonel bug |
| `agent_core/p2p/` boş + `reflection.sql` dead | Belirtilmemiş / zayıf | DEAD CODE |
| Frontend’in tasks/override/authorize-alternative çağırmaması | Kısmen experimental notu | API/UI gap |
| Health score metodolojisi | Bağımsız skor vermedi; “WORKING/PARTIAL” dil kullandı | Uyumlu ruh |

### 23.5 ÇELİŞKİ ÇÖZÜMÜ (iki denetim arasında)

| Konu | Çözüm |
|---|---|
| Branch adı `01a04b6e` vs `01a04b6f` | Bu checkout: `arena/01a04b6e-pineal-clean` @ `fda9940` [PROVEN git]. Bağımsızdaki `f` muhtemel yazım hatası. |
| “Üretimde sahte yanıt yok” vs “DarkTriad/heuristik zayıf” | İkisi de doğru: sistem **uydurma tamamlanmış profil** üretmiyor (halt/fallback damgalı); DarkTriad ise **zayıf heuristik** ve data_confidence=False ile işaretleniyor — mock değil, düşük kaliteli sinyal. |
| Full pipeline “PASS” | Yalnız **local/stub provider** ile bağımsızda PASS; cloud ücretli ve bu sandbox local provider’sız → her iki denetim de cloud’u NOT_EXECUTED saymalı. “PASS*” etiketi doğru çerçeve. |

### 23.6 BİRLEŞİK SON HÜKÜM (çapraz)

İki bağımsız inceleme **çekirdek gerçeklikte hemfikir**:

1. İskelet (API, UI, WS, memory, auth, rate limit, dürüst halt) **WORKING**.  
2. CI **2 test yüzünden kırmızı**.  
3. Docs↔kod uçurumu (zincirler, TIER_2, USE_LOCAL_LLM API path, X RUNBOOK, test sayısı, rust CI) **CONTRADICTED / sistematik**.  
4. Canlı bulut LLM + Instagram + Docker + Rust/Android runtime bu kısıtlı ortamlarda **NOT_EXECUTED**.  
5. Üretim path’te bilinçli fake-completion motoru **yok**.  

**Ek netleştirme (bu çapraz tur):**
- `preferred_model` / `muse-spark-1.2-xhigh` = **DEAD** [PROVEN].  
- `USE_LOCAL_LLM` .env → API room = **eziliyor** [PROVEN].  
- OpenRouter katalog/slug doğrulaması bu sandbox’ta **tekrarlanamadı** [NOT_EXECUTED].

**Güncellenmiş P0 fix listesine ek:**
8. `AspasiaChief.preferred_model` bağla veya sil.  
9. `get_room`: `use_local = vault.get("use_local", os.getenv("USE_LOCAL_LLM","false").lower()=="true")`.  
10. README/RUNBOOK model zincirlerini `llm_gateway.CHAINS` ile senkronize et; hayali slug’ları sil.  
11. RUNBOOK X satırını “analiz başlamaz / yetki bekler” yap.

**Skor revizyonu:** Çapraz tur iskelet güvenini artırır (+2 docs-awareness), cloud LLM hâlâ NOT_EXECUTED.  
Revize health score: **64 / 100** (önceki 62; metodoloji aynı, docs/contradiction maddeleri bağımsızla pekişti, yeni dead-config kanıtları eklendi).

