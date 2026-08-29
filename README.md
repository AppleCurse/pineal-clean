# PINEAL-HERETIC v3.0 · PINEAL 3.0 — 360° Bütüncül İnsan Tanıma

Sosyal medya profillerini (Instagram / X) anonim tarayan; fotoğrafları **çoklu modlu
görsel zeka (VisionAnalyzer)** ile inceleyen; kişiyi tutkular, neşe, hassasiyetler,
sınırlar ve bilişsel üslup boyutlarında **360° kanıta dayalı** çözümleyen, LLM
destekli tek kullanıcılı yerel bir analiz istasyonudur.

Kararları `PinealExecutor` + `CognitiveRouter` verir; **Aspasia** karar verici değil,
sistem durumunu ve telemetriyi açıklayan gözlemci/personadır.

> Bu depo güncel olarak şu yeni bileşenleri içermektedir:
> `rust_core/` (Rust katmanı — derlenmeyen/CI'da koşmayan, Python'a bağlanmamış deneysel kod; dosyada birim testleri mevcut), 6 Forensik Damga Paneli (Snapshot + SearchEngine ayrımı), 
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
   Zincirler: depth `solar-pro4 → glm-5.2 → deepseek-v4-pro` ·
   dialogue `solar-pro4 → deepseek-v4-flash` ·
   fast `ling-3.0-flash → deepseek-v4-flash` (env:
   `OPENROUTER_CHAIN_<TASK>`).

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
cp .env.example .env      # anahtarları doldurun (opsiyonel)
docker compose up --build
```

### C) Manuel
```bash
pip install -r requirements.txt
python -m playwright install chromium  # ZORUNLU ADIM (Docker disi manuel kurulumlarda)
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
| `PINEAL_TOKEN` | Tanımlanırsa tüm API `X-API-Key` ister; UI için `VITE_PINEAL_TOKEN`. |
| `PINEAL_ALLOWED_ORIGINS` | CORS (boşsa localhost kümesi). |

Anahtarlar UI'daki **Kasa (Vault)** panelinden de girilebilir.

## 6. Testler
```bash
pytest                          # unit + entegrasyon + e2e + ws sıra + güvenlik + LLM protokol
                                # Güncel sayı: pytest --collect-only -q | tail -1
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
- **Veri silme (retention):** `GET /api/tasks` ile geçmişi görün, `DELETE /api/tasks/{id}` ile kalıcı silin.
- Hata modeli: uygulama katmanı hataları (401/429/404/500, Aspasia) `{error:{code,message}}` biçimindedir; FastAPI şema doğrulama hataları (422) ise FastAPI'nin standart `{detail:[...]}` biçimini kullanır (kasten değiştirilmez).

## 9. Kullanım Sınırları
Araştırma/analitik amaçlıdır; kişisel veri işler — yasalara ve platform şartlarına
uymak kullanıcının sorumluluğundadır. Ürün kimliği "sahici iletişim köprüsü"dür ve
sistem hiçbir platforma otomatik/gizli mesaj **göndermez**. Şeffaflık notu: pipeline
içinde deterministik bir "gölge profil" analiz bileşeni (`shadow_executor`:
dark-triad puanlama + NLP dizisi) her görevde forensik damga olarak kaydedilir;
mesaj/kontra-hamle üretimi araçları (`shadow/generate`, `chat/respond`) yalnız
kullanıcının açıkça çağırdığı deneysel endpoint'lerdedir: `/api/experimental/*`.
X (Twitter) kazıması devre dışıdır (`XScraperUnsupportedError`); Instagram kazıması
tarayıcı kurulumuna (`playwright install chromium`) ve platform erişimine bağlıdır.
