# PINEAL-HERETIC v3.0 · PINEAL 3.0 — 360° Bütüncül İnsan Tanıma

Sosyal medya profillerini (Instagram / X) anonim tarayan; fotoğrafları **çoklu modlu
görsel zeka (VisionAnalyzer)** ile inceleyen; kişiyi tutkular, neşe, hassasiyetler,
sınırlar ve bilişsel üslup boyutlarında **360° kanıta dayalı** çözümleyen, LLM
destekli tek kullanıcılı yerel bir analiz istasyonudur.

Kararları `PinealExecutor` + `CognitiveRouter` verir; **Aspasia** karar verici değil,
sistem durumunu ve telemetriyi açıklayan gözlemci/personadır.

> Bu depo güncel olarak şu yeni bileşenleri içermektedir:
> `rust_core/` (FAZ 9 Karar B: **experimental/optional**, Python ürün çalışma zamanına
> bağlanmamış kod; CI'da `cargo check` + `cargo test` kapısı vardır, ancak Docker'a
> paketlenmez, aktivasyon bayrağı yoktur ve hiçbir API/pipeline kararını etkilemez),
> 6 Forensik Damga Paneli (Snapshot + SearchEngine ayrımı),
> i18n çift dil desteği (TR/EN) ve yeni OSINTInvestigatorAgent & AuthenticityAuditorAgent zincirleri.

---

## 1. Mühendislik Felsefesi

1. **İnsanı bir bütün olarak tanımak:** yalnızca yaralar/zafiyetler değil; neşe ve
   tutku alanları ile sınırlar ve hassasiyetler eş zamanlı haritalanır.
2. **Sıfır halüsinasyon:** genel geçer kalıp üretilmez; her çıkarım somut nesne,
   mekân ve alıntıya dayanır. Kanıt yoksa sistem **durmaya** programlıdır.
3. **Multimodal görsel zeka:** fotoğraflar kör geçilmez; kadraktaki nesneler
   (kitaplar, analog kameralar, mekânlar, estetik dil) taranıp kanıt zincirine girer.
4. **Hibrit akıl:** hızlı durum/telemetri yerel modelle (Ollama) veya OpenRouter
   ile yürür — anahtar sizdedir. Varsayılan modeller (env ile ezilebilir;
   P2 ekonomik model seti, slug'lar OpenRouter kataloğundan doğrulandı):
   Tier-1 `upstage/solar-pro4` (`OPENROUTER_TIER_1_MODEL`, promo fiyat
   2026-09-10'a kadar),
   Tier-2 `inclusionai/ling-3.0-flash` (`OPENROUTER_TIER_2_MODEL`),
   Vision `google/gemini-3.7-flash` (`OPENROUTER_VISION_MODEL` — listedeki
   metin modelleri vision desteklemediği için korundu).
   Koddaki gerçek zincirler (`agent_core/services/llm_gateway.py` → `CHAINS`):
   depth `solar-pro4 → glm-5.2 → deepseek-v4-pro` ·
   dialogue `solar-pro4 → deepseek-v4-flash` ·
   fast `ling-3.0-flash → deepseek-v4-flash` (env: `OPENROUTER_CHAIN_<TASK>`;
   ajan bazlı: `OPENROUTER_AGENT_CHAIN_<AJAN>`).

## 2. Sistem Mimarisi (koddan doğrulanmış)

```
[ HEDEF PROFİL (URL / Veri) ]
        │
        ▼
[ Hayalet Tarayıcı ]  (Playwright + stealth; IG: instagram_ghost — X kazıma devre dışı, bkz. §9)
        │
        ▼
[ VisionAnalyzer ]    (görseller → somut nesne/mekân kanıtı; LLM multimodal)
        │
        ▼
PinealExecutor        (durum makinesi: processing → completed | failed | halted_*)
 ├─ MirrorOfTruth (kullanıcı öz frekansı)
 ├─ OSINTInvestigator (Açık kaynak derin analiz)
 ├─ AuthenticityAuditor (Orijinallik ve görsel kanıt kontrolü)
 ├─ AutonomousVerifier (web iddia teyidi; Tavily)
 ├─ HumanBehaviorAnalyzer (OpenCV + dilbilimsel mikro izler)
 ├─ PassionMapper · FrictionDetector · CognitiveProfiler
 ├─ ResonanceCalculator (saf numpy; <0.70 → halted_frequency)
 └─ ResonanceSynthesizer (sahici ilk temas köprüsü)
        │
        ▼
HolisticProfile (360°) + CanonicalMemory (memory/*.json kanıt zinciri;
PINEAL_MEMORY_ENGINE=hindsight ile anlamsal arama katmanı açılır)
        │
        ├─ 6 Forensik Damga: follower_audit · timing_forensics · depth_report
        │   · visual_evidence · shadow_profile · osint_footprint
        ├─ LLM yanıt önbelleği (PINEAL_RESPONSE_CACHE; birebir, cross-safe)
        ├─ Telemetry events → FIFO kuyruk → WebSocket (sıralı, kayıpsız)
        └─ Svelte UI + Aspasia (gözlemci sohbet; görsel de yüklenebilir)
```

**Durum makinesi:** `initialized → processing → completed | partially_completed | failed | halted_evidence | halted_frequency | halted_critical` (güven eşiği 0.6; rezonans eşiği 0.70).

## 3. 360° Veri Modelleri (`agent_core/domain/memory_models.py`)

- **`PassionProfile`** — neşe/yaratıcılık/merak: `core_passions`, `energizing_topics`, `flow_triggers`, `evidence_quotes`
- **`FrictionProfile`** — sınırlar/hassasiyetler: `sensitivities`, `stress_triggers`, `boundary_signals`
- **`CognitiveStyle`** — dil ve düşünce kalıbı: `communication_tone`, `complexity_level`, `humor_style`
- **`AuthenticBridge`** — sahici ortak payda + saygılı açılış mesajı: `shared_passions`, `resonance_score`, `suggested_opening_message`
- **`HolisticProfile`** — dört boyutun mühürlendiği tam insan haritası

## 4. Kurulum

### A) Windows (tek komut)
```bat
baslat.bat
```
venv kurar, bağımlılıkları indirir, frontend'i derler (dist yoksa) ve
`http://localhost:8000` üzerinde ayağa kaldırır.

### B) Docker
```bash
cp .env.example .env      # en azından production PINEAL_TOKEN değerini doldurun
docker compose up --build
```

### C) Manuel
```bash
pip install -r requirements.txt
pip install -r requirements-osint.txt   # 2. adım: crawl4ai (psutil meta-çatışması için ayrı dosya; opsiyonel)
python -m playwright install chromium  # ZORUNLU ADIM (Docker dışı manuel kurulumlarda)
cd frontend && npm ci && npm run build && cd ..
uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

Canlı profil çözümleme demosu: `python scripts/analyze_target_instagram.py` (Chrome gerektirir).

## 5. Yapılandırma (`.env`)

| Değişken | Anlamı |
|---|---|
| `OPENROUTER_API_KEY` | LLM anahtarı. Yoksa pipeline ilk LLM'li ajanda durur (halüsinasyon önleme, tasarımdır). |
| `OPENROUTER_TIER_1_MODEL` | Birincil LLM modeli (varsayılan `upstage/solar-pro4`). |
| `OPENROUTER_TIER_2_MODEL` | Hızlı ikincil model (varsayılan `inclusionai/ling-3.0-flash`). |
| `OPENROUTER_MAX_SPEND_USD` | Oturum harcama tavanı (0=kapalı). Aşılırsa `SpendCapExceeded` ve canlı çağrı durur. |
| `LIVE_LLM_E2E` | `1` değilken dış LLM çağrıları kod tarafından reddedilir. |
| `USE_LOCAL_LLM`, `LOCAL_LLM_URL`, `LOCAL_LLM_MODEL` | Ollama/LM Studio (anahtar gerekmez). |
| `TAVILY_API_KEY`, `SERPAPI_API_KEY`, `EXA_API_KEY` | AutonomousVerifier web araması (Tavily/SerpAPI/Exa; yoksa DuckDuckGo yedeği). |
| `OPENROUTER_VISION_MODEL` | Görselli isteklerde vision modeli (varsayılan `google/gemini-3.7-flash`; VisionAnalyzer ve görselli Aspasia istekleri). |
| `PINEAL_ENV` | `development` (varsayılan) veya `production`. Production, `PINEAL_TOKEN` olmadan startup'ta fail-closed durur. Docker varsayılanı production'dır. |
| `PINEAL_REQUIRE_AUTH` | Development'ta da token zorunluluğunu açar. |
| `PINEAL_TOKEN` | Tanımlanırsa tüm API `X-API-Key` ister. UI bunu iki yoldan taşır: (1) çalışma zamanı — arayüzde Kasa panelindeki "API ERİŞİM ANAHTARI" alanı (yeniden derleme gerekmez, önerilen); (2) derleme zamanı — `VITE_PINEAL_TOKEN` (Docker build arg). WebSocket anahtarı URL yerine ilk auth mesajında taşınır. |
| `PINEAL_ALLOWED_ORIGINS` | CORS (boşsa localhost kümesi). |
| `ENABLE_MAIGRET`, `ENABLE_HOLEHE`, `ENABLE_CRAWL4AI` | Deneysel OSINT kapıları — **hepsi default KAPALI**; kapalıyken pipeline davranışı değişmez. Limit/timeout alt değişkenleri `.env.example`'da. |
| `STEALTH_PROVIDER` | `playwright_stealth` (default) \| `invisible` \| `cloak` \| `none`. invisible/cloak yalnız binary yolu gösterilirse kullanılabilir (indirme yapmaz): `INVISIBLE_BROWSER_BINARY`, `CLOAK_BROWSER_EXECUTABLE`. |

Deneysel uçlar: `POST /api/experimental/{maigret/scan, holehe/scan, crawl/fetch, socid/extract}` ve
`GET /api/experimental/stealth`. Sözleşme: kullanılamayan tarama `available:false` + makine-okunur
sebep döner; veri ASLA uydurulmaz. Kanıt zinciri ve araç hükümleri: `INTEGRATION_PLAN.md`.

Anahtarlar UI'daki **Kasa (Vault)** panelinden de girilebilir.

### Rust core çalışma zamanı statüsü

FAZ 9'da **Karar B** seçilmiştir: `rust_core/` yalnızca deneysel/optional bir
repository bileşenidir. Python bağımlılığı değildir, ürün Docker imajına kopyalanmaz,
çalışma zamanı aktivasyon bayrağı yoktur ve FastAPI → executor → agent zincirinde
çağrılmaz. `/health` ve `/api/telemetry` bu durumu makine-okunur olarak
`product_runtime_integrated:false` ve `product_decision_effect:false` alanlarıyla
raporlar. Rust kodunun CI'da derlenip test edilmesi ürün entegrasyonu kanıtı değildir.
Bu statü ancak gerçek Python ürün yolu Rust'ı çağırır ve çıktısının ürün kararına
etkisi cross-stack E2E ile kanıtlanırsa değiştirilebilir.

## 6. Testler
```bash
pytest                          # Güncel sayı için: pytest --collect-only -q | tail -1
                                # unit + entegrasyon + e2e + ws sıra + güvenlik + LLM protokol
cd frontend && npm run check && npm run build
```

## 7. Sık Görülen Sorunlar
| Belirti | Çözüm |
|---|---|
| "Görev durumu: failed" | LLM yok → anahtar + `LIVE_LLM_E2E=1` veya yerel model |
| Aspasia "bağlantıda kırılma" | Aynı — zarif fallback; anahtarla gerçek yanıt |
| Tarayıcı boş sayfa | `frontend/dist` yok → build edin |
| 429 | Bilinçli hız limiti (initiate 5/dk, aspasia 20/dk) — 1 dk bekleyin |
| 401 | `PINEAL_TOKEN` tanımlı ama istemci göndermiyor |
| Scrape 429/403 | Platform limit/cookie — Kasaya güncel cookie |

## 8. Güvenlik ve Veri
- Sır koruması: anahtar/cookie yalnızca bellekte; loglara/telemetriye sızmaz (test kilitli).
- **Görev yaşam döngüsü:** `POST /api/initiate` çağrısı immutable `task_id` döndürür; çalışan görev `POST /api/tasks/{id}/cancel` veya `/halt` ile terminal ve idempotent biçimde durdurulur.
- **Veri silme (retention):** `GET /api/tasks` ile geçmişi görün, `DELETE /api/tasks/{id}` ile kalıcı silin.
- Hata modeli: uygulama katmanı hataları (401/429/404/500, Aspasia) `{error:{code,message}}` biçimindedir; FastAPI şema doğrulama hataları (422) ise FastAPI'nin standart `{detail:[...]}` biçimini kullanır (kasten değiştirilmez).

## 9. Android İstemcisi (Bağımsız Uygulama)

`android/` dizini, Python backend'den **tamamen bağımsız** bir Kotlin/Jetpack Compose
Android uygulamasıdır. Python FastAPI sunucusunu kullanmaz; doğrudan
`https://generativelanguage.googleapis.com/` (Google Gemini API) ile konuşur.
API anahtarı `x-goog-api-key` HTTP başlığıyla taşınır (query string'de değil).

CI'da ayrı bir `android` job'u olarak lint + unit test + assemble doğrular.
**Android release, backend release'den bağımsızdır.**

## 10. Kullanım Sınırları
Araştırma/analitik amaçlıdır; kişisel veri işler — yasalara ve platform şartlarına
uymak kullanıcının sorumluluğundadır. Ürün kimliği "sahici iletişim köprüsü"dür ve
sistem hiçbir platforma otomatik/gizli mesaj **göndermez**. Şeffaflık notu: pipeline
içinde deterministik bir "gölge profil" analiz bileşeni (`shadow_executor`:
dark-triad puanlama + NLP dizisi) her görevde forensik damga olarak kaydedilir;
mesaj/kontra-hamle üretimi araçları (`shadow/generate`, `chat/respond`) yalnız
kullanıcının açıkça çağırdığı deneysel endpoint'lerdedir: `/api/experimental/*`.
X (Twitter) kazıması devre dışıdır (`XScraperUnsupportedError`); Instagram kazıması
tarayıcı kurulumuna (`playwright install chromium`) ve platform erişimine bağlıdır.
