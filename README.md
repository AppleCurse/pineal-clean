# PINEAL-HERETIC v3.1 · PINEAL 360° Bütüncül İnsan Tanıma & Adli Bilişsel İstasyon

> **"Kodu okuyanla belgeyi okuyan aynı şeyi görecek."**
> Bu belge, depodaki koddan doğrulanmış teknik kılavuzdur. Doğrulama noktası: HEAD `2006f696`,
> 2026-09-08. Sayısal iddiaların tamamı (`git grep`, `config/*.json`, `.env.example`, CI
> `.github/workflows/ci.yml`, test koşusu) ile çapraz kontrol edilmiştir.
> Bu sürümde yalnızca **kodda karşılığı olan** özellikler anlatılır; kodda olmayan hiçbir
> sağlayıcı/model/özellik listelenmez.

---

## 1. Sistemin Mühendislik ve Felsefi Temeli

Pineal; çok kanallı kanıt toplayan, zaman serisi ve metin analizi yapan, insan psikolojisindeki
bastırılmış alanları ve savunma mekanizmalarını **deterministik motorlarla** modelleyen yerel bir
analiz ve profil istasyonudur. LLM'ler yalnızca uzman ajanların doğal dil üretim/çıkarım
adımlarında kullanılır; ölçüm ve karar motorları LLM'sizdir.

### Temel Çalışma İlkeleri
1. **Kanıt Mührü & Fail-Closed:** Hiçbir ajan veri uyduramaz; her çıkarım kanıt nesnesine
   bağlanır. Kanıt yetersizse sistem halts/durur (`InsufficientEvidenceError`, `halted_critical`).
   Canlı LLM çağrısına kapı yoksa yanıt üretilmez (`REAL_LLM_CALL_NOT_EXECUTED`) — boş/uydura
   yanıt dönmez.
2. **Deterministik Psikodinamik:** Karakter analizi `agent_core/engines/` (7 motor) ve
   `agent_core/services/` içindeki `theme_cluster`, `timing_forensics`, `psychodynamic_depth`
   modülleriyle yapılır — bu modüller hiçbir LLM çağrısı yapmaz (bağımsız denetimle doğrulandı).
3. **Çok Kanallı Çelişki Tespiti:** Beyan (metin), Sahneleme (görsel), Zaman (zaman damgası) ve
   Sosyal (takip/etkileşim) kanalları arasındaki gerilimden savunma mekanizması katsayıları üretilir.
4. **Epistemik Güven Bütçesi:** Metin yoksa sözel kanal ağırlığı sıfırlanır; bütçe görsel ve
   zamansal kanallara aktarılır.

---

## 2. Yedi Nöro-Bilişsel Dalga Motoru (`agent_core/engines/`)

LLM'den bağımsız, ham metin/zaman serisi üzerinde deterministik dalga analizi yürüten 7 motor,
`PillarOrchestrator` (iki fazlı) tarafından yönetilir:

```
                      ┌── FrequencyEngine  (Zaman Dalgası, Gece/Gündüz Enerji Payı)
                      ├── SeismosEngine    (Kutup Değişimi, Davranışsal Kırılmalar)
                      ├── VoidEngine       (Negatif Uzay, Bastırılan/Konuşulmayan Alanlar)
PillarOrchestrator ───┼── StrataEngine     (Uzunlamasına Katmanlar, Fosil Kayıtları)
                      ├── GravityEngine    (Anlatı Çekim Merkezleri, Kara Delik Odakları)
                      ├── PulseEngine      (Dijital Beden Dili, Biyometrik Sinyaller)
                      └── KeyEngine        (Tüm Motorların Kural Tabanlı Rezonans Sentezi)
```

| Motor | Dosya | Analitik Görev |
|---|---|---|
| Frequency | `frequency_engine.py` | Zaman damgalarını dalga boyuna döker; sirkadiyen ritim, `night_energy_share`. |
| Seismos | `seismos_engine.py` | Metin polarite sıçramaları; `SeismicEvent` fay kırılmaları. |
| Void | `void_engine.py` | Beklenen 10 kategori ailesinden hiç konuşulmayanların tespiti. |
| Strata | `strata_engine.py` | Zaman içi katmanlar; `IdentityDrift`, sönümlenen kimlikler. |
| Gravity | `gravity_engine.py` | Tekrarlayan takıntı merkezleri; `GravityWell`. |
| Pulse | `pulse_engine.py` | Cümle/noktalama ritmi; dijital beden dili. |
| Key | `key_engine.py` | 6 motor çıktısını kural tabanlı birleştirir; `ResonanceVector`. |

---

## 3. Uzman Ajan Envanteri

### 3a. Zincir ve tier kayıtları — `config/agent_tiers.json` (18 zincir, `get_agent_chain` ile okunur)

| Ajan | Tier |
|---|---|
| aspasia (AspasiaChief) | heavy |
| authenticity_auditor | heavy |
| autonomous_verifier | verify |
| autonomous_verifier_extract | simple |
| cognitive_profiler | heavy |
| depth_analyst | heavy |
| dialogue_manager | simple |
| friction_detector | heavy |
| human_behavior | heavy |
| interpreter | simple |
| lilith_growth | simple |
| mirror_truth | heavy |
| osint_investigator | heavy |
| passion_mapper | simple |
| pattern_interrupt | simple |
| resonance_synthesizer | heavy |
| shadow_executor | heavy |
| vision_analyzer | vision |

### 3b. Dosya konumları

| Dosya | Ajan / Sorumluluk |
|---|---|
| `agents/passion_mapper.py`, `agents/friction_detector.py`, `agents/cognitive_profiler.py` | Tutku/sınır/bilişsel stil profilleme (ana döngüde çalışır). |
| `agents/depth_analyst.py` | Gerçeklik indeksi (`reality_index`) ve çelişki tespiti (ana döngü dışı derinlik turu). |
| `agents/resonance_calculator.py` | Kullanıcı-hedef frekans uyumu (saf vektör matematiği; <0.70 → `halted_frequency`). |
| `agents/resonance_synthesizer.py` | Manipülasyonsuz ilk temas köprüsü (`AuthenticBridge`). |
| `agents/human_behavior.py` | Görsel kompozisyon analizi (görsel kanal). |
| `agents/authenticity_auditor.py` | Görsel manipulasyon/yapaylık denetimi (yalnız görsel kanıt varken). |
| `agents/autonomous_verifier.py` | Hedef doğrulama + extract fazı (zincirde `autonomous_verifier(_extract)`). |
| `agents/pattern_interrupt.py` | Diyalog ağaçları, kutsal kural ihlal skoru. |
| `agents/mirror_truth.py` | Kullanıcı öz-frekansı ile yüzey personası uyumu. |
| `agents/lilith_growth.py` | Büyüme analizi (CLI/deneysel). |
| `agents/interpreter_agent.py` | Taktik kod üretimi (yalnız `ENABLE_INTERPRETER=true`). |
| `agents/osint_investigator.py` | Dijital ayak izi skoru, bağlı platform analizi (LLM'siz kanal). |
| `shadow/shadow_executor.py` | Telafi/kırılma indekslerini taktik vektörlere dönüştürür (derinlik turu). |
| `services/vision_analyzer.py` | Görsel kanal özetleyici (vision tier). |
| `chat/dialogue_manager.py` | Çok turlu diyalog bağlamı (`/api/experimental/chat/respond`). |
| `aspasia/aspasia_chief.py`, `aspasia/interface.py` | Aspasia (gözlemci/üst akıl) + `DiskMemoryBridge`. |

---

## 4. Dört Sütunlu Psikodinamik Derinlik Motoru

### Sütun 1: Denetimsiz Semantik Kümeleme (`services/theme_cluster.py`)
Karakter 3-gram TF vektörleri + kosinüs benzerliği + union-find kümeleme; `repetition_score`,
`isolated_anomaly_count` üretir. Önceden tanımlı tema listesi yoktur.

### Sütun 2: Durum Yörüngesi ve Faz Kırılması (`services/timing_forensics.py`)
Gönderiler zaman fonksiyonuna dizilir; iki yarı arasında entropi/varyans karşılaştırması ile faz
kırılma noktaları tespit edilir.

### Sütun 3: 4 Kanallı Çapraz Gerilim Matrisi (`services/psychodynamic_depth.py`)
Beyan / Sahneleme / Biyolojik Ritim / Sosyal Metrik kanallarında şiddet-tutarlılık-bütünlük
ölçülür; `compensation_index` ve `reaction_formation_index` üretilir. `QuoteGuard` uydurma
alıntıyı ayıklar.

### Sütun 4: Bayesian Epistemik Bütçe
Metin yoksa `w_declaration = 0`; bütçe görsel+zamansal kanala aktarılır. Motorlar LLM'sizdir.

---

## 5. Veri Toplama ve Zenginleştirme Altyapısı

| Servis | Dosya | Durum / Kapı |
|---|---|---|
| Instagram Ghost Scraper | `scraper/instagram_ghost.py` | Playwright + kullanıcı cookie'si; `/p/` ve `/reel/` çeker. **Yalnız Instagram**; X (Twitter) kazıması kodda sabit kapalı (`x_scraper: false`). |
| Maigret tarayıcı | `services/maigret_scanner.py` | `ENABLE_MAIGRET=true` ise (varsayılan kapalı). |
| Holehe tarayıcı | `services/holehe_scanner.py` | `ENABLE_HOLEHE=true` ise (varsayılan kapalı). |
| Socid Enricher | `services/socid_enricher.py` | Platform ID zenginleştirme. |
| Search Engine | `services/search_engine.py` | Tavily/SerpAPI/Exa (anahtarlar vault `.search_keys`). |
| Crawl Enricher | `services/crawl_enricher.py` | `ENABLE_CRAWL4AI=true` ise (varsayılan kapalı). |

Denetim notu: maigret/holehe/crawl4ai kapıları **varsayılan kapalıdır**; canlı tarama davranışları
yalnız kapı açıkken ve ilgili bağımlılık kuruluysa çalışır.

---

## 6. Sağlayıcı Kataloğu, Routing ve Kasa (gerçek durum)

- **Katalog:** `config/provider_catalog.json` — 26 sağlayıcı kaydı. **7'sinde** model
  tanımlıdır: `openrouter` (9), `nous-research` (8), `deepseek` (3), `groq` (2),
  `cerebras` (1), `google-gemini` (1), `google-gemini-backup` (1) — son ikisi FAZ-2-P4
  (Google resmi OpenAI-uyumlu endpoint, model adı öneksiz `gemini-3.7-flash`; backup =
  aynı endpoint'in 2. anahtarı, 429 sonrası otomatik rotasyon). Diğer 19 kayıt (openai,
  anthropic, mistral, xai, together, fireworks, deepinfra,
  sambanova, nvidia-nim, huggingface, perplexity, azure, cohere, cloudflare, dashscope, ollama,
  lm-studio, vllm, openai-compatible) model taşımaz; bunlar yalnız
  `PINEAL_PROVIDER_MODELS_<PROVIDER>` operatör beyanı (`llm_gateway._operator_declared_models`)
  ve transport desteği için vardır.
- **Routing SoT:** `agent_core/services/final_routing_policy.py` `ROUTES` + `MODEL_PRICING` +
  `TASK_GROUPS`; chain SoT `agent_core/services/llm_gateway.py` `AGENT_CHAINS` +
  `config/task_routing.json` (delta) + env override. Çift SoT kopyası
  `config/provider_catalog.json`'dur; üçü `scripts/verify_openrouter_catalog.py` ve kontrat
  testleriyle senkron tutulur.
- **Anahtarlar:** `.env`/ortam ve `.pineal_vault.json` okunur (kasa yalnız **okuma**; disk yazımı
  yoktur, oda belleğinde tutulur — restart'ta kaybolur). Kasa şeması: `providers.<ad>.api_key`
  (iç içe) ve eski düz `api_key`/`provider_keys`. Kasadan alınan direct-provider anahtarları
  yalnız ilgili odanın gateway'ine uygulanır.
- **Tier-bazlı harcama kuralları** (FAZ-1/FAZ-2, `_tier_route_decision` — kilitli):

| Tier | Rota | Davranış |
|---|---|---|
| simple | free (direct free / OR-free) | teklif edilir |
| simple | paid (direct veya OR-legacy) | **HARD DENY** → teklif yok; tümü reddedilirse boş liste |
| heavy/vision/verify | indirimli direct (ör. `anthropic/claude-sonnet-5@nous-research` $1.6/$8) | izin (escalation env'siz — relax) |
| heavy/vision/verify | liste-fiyat direct / frontier | paid firewall (escalation şart) |
| heavy/vision/verify | OR-legacy (liste fiyatı) | **FAZ-2.1 liste engeli:** modelin daha ucuz indirimli direct kanalı kuruluysa yalnız `PINEAL_ALLOW_PAID_ESCALATION=1` ile teklif edilir; daha ucuz kanalı olmayan modellerde (örn. `google/gemini-3.7-flash` yalnız-OR) koşulsuz kalır (kırılma yok). Her karar `tier_audit_trail`'e `gate_context` ile yazılır. |
| unknown | her şey | heavy-eşdeğeri + `tier_unresolved` izi |

- **Fail-closed harcama koruması:** `PINEAL_ALLOW_PAID_ESCALATION=1` verilmeden paid/frontier
  direct rotalar reddedilir (heavy/vision/verify indirimli direct hariç);
  `PINEAL_ALLOW_UNPRICED_MODELS=1` verilmeden fiyatı bilinmeyen modellere çağrı yapılmaz.
  Üretimde (`PINEAL_ENV=production`) pozitif `OPENROUTER_MAX_SPEND_USD` zorunludur; yoksa
  başlangıç reddedilir.
- **OpenAI-uyumlu `/v1` yolu:** `PINEAL_LLM_BACKEND=unified` ise `RoutedChatExecutor`
  (katalogdan otomatik config); `legacy` ise `LLMGateway`. Stream yalnız unified'da çalışır;
  stream+tools birlikte kabul edilmez. Anahtarsız ortamda `/v1/models` boş liste döner (fail-closed).

---

## 7. Çift Katmanlı Bellek ve Aspasia Gerçekliği

- **Kanonik Bellek (`services/canonical_memory.py`):** Kanıt zinciri disk üzerinde
  `memory/<task_id>.json` dosyasında saklanır. Varsayılan motor (`PINEAL_MEMORY_ENGINE=canonical`).
- **Semantik Bellek (`services/hindsight_memory.py`):** `PINEAL_MEMORY_ENGINE=hindsight` ile
  aktif; geçmiş görevlerde vektörel sorgulama.
- **Aspasia Disk Köprüsü (`DiskMemoryBridge`)** (`task_executor` → `aspasia/interface.py`):
  görev tamamlanınca derinlik verileri kanonik kanıta `forensic_digest` mührüyle basılır; Aspasia
  diskteki mührü okur, hayali ajan uydurmaz (`ROUTING-ADAY` vs `GÖZLEMLENEN` ayrımı).
- **Yanıt önbelleği:** `services/response_cache.py` (SQLite, `PINEAL_RESPONSE_CACHE`,
  `PINEAL_CACHE_MAX_ROWS`).

---

## 8. Kurulum ve Çalıştırma

### A) Docker (üretim yolu)
```bash
docker compose up --build        # PINEAL_ENV=${PINEAL_ENV:-production}; 0.0.0.0:8000
```
Tek-imajlı FastAPI servisi; healthcheck `/health`; volume'lar `pineal_memory` (`/app/memory`) ve
`pineal_cache` (`/app/cache`). Not: `docker-compose.yml` içindeki `pineal_vault:/app/vault-data`
volume'ü şu an kod tarafından kullanılmaz (kod kasa dosyasını çalışma dizininde arar) — bilinen
tutarsızlık, düzeltme FAZ-3 girdisi.
> Tek-süreç modeli: odalar, kasa, hız sınırı ve kuyruklar process-local'dir; `replicas: 1`.
> Yatay ölçek ve restart davranışı üretimde doğrulanmamıştır.

### B) Windows (tek komut)
```bat
baslat.bat
```
Sanal ortam + bağımlılıklar + frontend derlemesi + `http://localhost:8000`.

### C) Manuel
```bash
pip install -r requirements.txt          # çekirdek
pip install -r requirements-osint.txt    # OSINT tarayıcı bağımlılıkları (opsiyonel)
python -m playwright install chromium    # Instagram Ghost Scraper için
cd frontend && npm ci && npm run build && cd ..
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```
Geliştirme: `cd frontend && npm run dev` → `http://localhost:5173` (API'ye proxy).
`PINEAL_ENV` belirsizse sistem **production** kabul eder (fail-closed): `PINEAL_TOKEN` ve pozitif
`OPENROUTER_MAX_SPEND_USD` ister; geliştirme için `PINEAL_ENV=development` + `PINEAL_REQUIRE_AUTH=false`.

---

## 9. Yapılandırma Gerçeği (`.env` / `.pineal_vault.json`)

Kaynak: `.env.example` (tam küme) + kodda okunan değişkenler. **Kodda olmayan hiçbir anahtar
bu tabloda yoktur** (ör. `E2B_API_KEY`, `llama-3.3-70b` — yoktur, README'den kaldırılmıştır).

### LLM / Routing
| Anahtar | Gerçek kullanım |
|---|---|
| `OPENROUTER_API_KEY` | OpenRouter taşıyıcısı (ana legacy/OR yolu). |
| `OPENROUTER_MAX_SPEND_USD` | Üretimde zorunlu pozitif değer; harcama limiti. |
| `OPENROUTER_TIER_1_MODEL` / `OPENROUTER_TIER_2_MODEL` | Tier model atamaları. |
| `OPENROUTER_BASE_URL` / `OPENROUTER_VISION_MODEL` | Alternatif uç / görsel model. |
| `LLM_REQUEST_TIMEOUT_SECONDS` / `LIVE_LLM_E2E` | Zaman aşımı / canlı uç test kapısı. |
| `PINEAL_LLM_BACKEND` | `unified` \| `legacy` (varsayılan legacy). |
| `PINEAL_ROUTER_CONFIG` | Unified router config yolu (yoksa katalogdan otomatik). |
| `PINEAL_ALLOW_PAID_ESCALATION` | `1` → paid/frontier direct'e geçiş izni. |
| `PINEAL_ALLOW_UNPRICED_MODELS` | `1` → fiyatı bilinmeyen modele izin (kodda okunur; `.env.example`'a eklendi). |
| `USE_LOCAL_LLM` + `LOCAL_LLM_URL` + `LOCAL_LLM_MODEL` | Yerel LLM yolu (Kasa override eder). |
| Direct sağlayıcı anahtarları | `GROQ_API_KEY`, `CEREBRAS_API_KEY`, `NOUS_API_KEY`, `DEEPSEEK_API_KEY`, `MISTRAL_API_KEY`, `TOGETHER_API_KEY`, `FIREWORKS_API_KEY`, `DASHSCOPE_API_KEY`, `SAMBANOVA_API_KEY`, `NVIDIA_API_KEY`, `HUGGINGFACE_API_KEY`, `DEEPINFRA_API_KEY`, `PERPLEXITY_API_KEY`, `GEMINI_API_KEY`, `IFLOW_API_KEY`, `GEMINI_BACKUP_API_KEY`, `GEMINI_VERTEX_TOKEN` — ilgili provider için direct rota açar (katalogda modeli olmayanlar yalnız `PINEAL_PROVIDER_MODELS_*` beyanıyla kullanılır). |

### Auth / Güvenlik / Kaynak
| Anahtar | Gerçek kullanım |
|---|---|
| `PINEAL_ENV` | Allowlist dışı her değer → production (fail-closed). |
| `PINEAL_TOKEN` / `PINEAL_REQUIRE_AUTH` | REST (`X-API-Key`) + WebSocket auth; production'da zorunlu. |
| `VITE_PINEAL_TOKEN` | Frontend build'ine gömülen token. |
| `PINEAL_ALLOWED_ORIGINS` | CORS allowlist (boşsa localhost). |
| `PINEAL_MAX_ROOMS`, `PINEAL_ROOM_TTL_SECONDS`, `PINEAL_MAX_CLIENT_ID_LENGTH`, `PINEAL_MAX_RATE_BUCKETS`, `PINEAL_RATE_SWEEP_INTERVAL_SECONDS` | Oda/rate kaynak tavanları. |
| `PINEAL_CACHE_MAX_ROWS` | Cache emniyet kemeri. |

### OSINT / Kazıyıcı / Bellek
`TAVILY_API_KEY`, `SERPAPI_API_KEY`, `SERPAPI_KEY`, `EXA_API_KEY`, `OSINT_INDUSTRIES_KEY`,
`STEALTH_PROVIDER`, `INVISIBLE_BROWSER_BINARY`, `CLOAK_BROWSER_EXECUTABLE`,
`PINEAL_MIN_SCRAPER_CONFIDENCE`, `PINEAL_POST_DETAIL_ENABLED` (varsayılan `true`),
`PINEAL_POST_DETAIL_LIMIT` (varsayılan 12, üst sınır 12), `PLAYWRIGHT_DOWNLOAD_HOST`,
`ENABLE_MAIGRET` + `MAIGRET_*`, `ENABLE_HOLEHE` + `HOLEHE_*`, `ENABLE_CRAWL4AI` + `CRAWL4AI_*`,
`ENABLE_INTERPRETER`, `ALLOW_LOCAL_TO_CLOUD_FALLBACK`, `PINEAL_MEMORY_ENGINE`,
`PINEAL_RESPONSE_CACHE`, `PINEAL_CACHE_PATH`.

---

## 10. Test ve Doğrulama Disiplini (gerçek durum)

Tam süit HEAD `2006f696`'da: **1135 toplandı / 1132 passed / 3 skipped** (bağımsız denetim koşusu,
2026-09-08). CI (`ci.yml`) kapıları:
1. **backend:** `ruff check` + `pytest --cov=agent_core --cov=backend --cov-fail-under=80` +
   gölge kararlılık (`python scripts/generate_routing_shadows.py && git diff --exit-code`) +
   katalog sözleşmesi (`python scripts/verify_openrouter_catalog.py`).
2. **frontend:** `svelte-check` + `vite build` + dist imza grep.
3. **smoke:** gerçek uvicorn + 4 endpoint (200/sağlık/telemetry/aspasia/WS).
4. **rust-core:** `cargo check && cargo test --locked`.
5. **android:** lint + test + assemble.

Not: `verify_openrouter_catalog.py`'nin **yerel** kısmı her CI koşusunda çalışır; **canlı**
OpenRouter çapraz kontrolü yalnız `OPENROUTER_API_KEY` secret'ı tanımlıysa koşar (yoksa açıkça
`SKIP:` basar). Mutasyon kanıtları: kilitli harcama testleri bozulduğunda suite KIRMIZI'ya düşer
(FAZ-1/FAZ-2 kayıtları; `tests/unit/test_tier_variant_gate.py`).

---

## 11. Mimari Durum Notları

- **`rust_core/`:** Bağımsız derlenen deneysel bileşen (`cargo check/test --locked` CI'da).
  Ürün Python çalışma zamanına **entegre değildir** (Python tarafında köprü/subprocess yok;
  `runtime_status` "experimental_optional / ürün kararı etkisiz" bildirir).
- **`android/`:** Ayrı Gradle projesi; Python servisiyle bağı yoktur (CI'da ayrı leg).
- **Veri gizliliği:** Kişisel veriler yerel `memory/` dizininde tutulur; dış sunuculara telemetri
  gönderilmez; log/telemetri öncesi `redact_structure` sırları ayıklar. Kasa anahtarları yalnız
  oda belleğinde tutulur.
- **Etik çerçeve:** Hiçbir platforma otomatik/gizli mesaj gönderilmez; X kazıması kodda kapalıdır;
  Instagram kazıması kullanıcı cookie'si ve Playwright gerektirir (canlı hedefe karşı CI'da test
  edilmez).
- **Bilinen açık kararlar / notlar:** (1) OR-legacy liste engeli FAZ-2.1'de uygulandı (ucuz
  kanal kuruluysa escalation şart; yalnız-kanal modeller koşulsuz) — kalan tradeoff: indirimli
  direct sağlayıcı geçici hata/cooldown'dayken liste fiyatı ödemek istemeyen operatör hata alır
  (escalation=1 ile bilinçli ödeme seçilebilir); (2) UI "ACTIVE MODEL/VIA" etiketi şu an statik
  fallback gösterir (backend `AgentRun` `model`/`via` üretmiyor) — düzeltme kararı bekliyor;
  (3) katalogda 0 modelli sağlayıcılar operatör beyanına bağlıdır; (4) tek-süreç mimarisi,
  restart/cok-oda davranışı üretimde ölçülmedi.
