# PINEAL-CLEAN — MEVCUT DURUM RAPORU
**Tarih:** 2026-08-30 · **Yöntem:** Kod ağacı yeniden, tek tek okunarak hazırlandı (commit geçmişine ve önceki belgelere dayanmadan). Her bölümün karşılığı koddadır; yalnızca okunanda yazılmıştır.
**Durum:** Son bağımsız koşu: 452 passed, 2 skipped; ruff ve hosted Android CI henüz bağımsız doğrulanmadı.

---

## 1. Sistem tek bakışta

Pineal, bir **360° insan-profili analiz ve sahici iletişim** sistemidir. Akış:

```
Kullanıcı (web arayüzü)
   → FastAPI sunucusu (backend/api.py)
      → PinealExecutor (durum makinesi)
         → CognitiveRouter (hangi ajanlar çalışacak?)
            → 13 uzman ajan (her biri kanıt toplar, kimse uydurmaz)
               → HolisticProfile (360° profil) + Kanıt zinciri (memory/*.json)
   → WebSocket ile arayüze canlı telemetri
```

Temel ilke kodun her yerinde aynıdır: **kanıt yoksa sistem durur, asla içerik üretmez.**

---

## 2. Sunucu katmanı — `backend/api.py`

Tüm HTTP/WebSocket yüzeyi tek dosyada, gruplar hâlinde:

| Grup | Uçlar | Ne yapar |
|---|---|---|
| Görev | `POST /api/initiate` | Analiz görevini başlatır; hedef profili + kullanıcı girdilerini alır |
| Kasa | `POST /api/vault` | API anahtarları/cookie'leri oturuma mühürler (yerel kasa; env'e de bakar) |
| Canlı akış | `WS /ws/{client_id}` · `GET /api/telemetry` | Sıralı, kayıpsız canlı log/telemetri |
| Yetkilendirme | `POST /api/scraper/authorize-alternative` | X kazıma kapalı olduğundan kullanıcıya açık yetki sorar; onaylanırsa kanıt-kaynaklı public-web araştırması yapar |
| Müdahale | `POST /api/executor/intervene` · `POST /api/override` | Çalışan görevle kullanıcı etkileşimi |
| Sohbet | `POST /api/aspasia/chat` · `POST /api/experimental/chat/respond` | Aspasia: gözlemci sohbet katmanı (profil kanıtlarıyla konuşur) |
| Deneysel OSINT | `POST /api/experimental/{maigret/scan, holehe/scan, crawl/fetch, socid/extract}` · `GET /api/experimental/stealth` | Kullanıcı-adı / e-posta taraması, sayfa-okuma, kimlik kaydı çıkarma, stealth seçim görünümü — **hepsi env-kapılı, default kapalı** |
| Shadow/Interpreter | `POST /api/experimental/shadow/{analyze, generate}` · `POST /api/experimental/interpreter/execute` | Dark-Triad analizi, strateji üretimi, kod-yorumlayıcı (ayrı kapı: `ENABLE_INTERPRETER`) |
| Görev verisi | `GET /api/tasks` · `DELETE /api/tasks/{task_id}` | Görev listesi + kalıcı silme (retention) |

Güvenlik: `PINEAL_TOKEN` tanımlanırsa tüm API `X-API-Key` ister; CORS `PINEAL_ALLOWED_ORIGINS` ile sınırlandırılır; tüm dış URL indirmeleri SSRF guard'dan (`is_safe_url`) geçer.

---

## 3. Görev yürütücü — `agent_core/task_executor.py`

`PinealExecutor` durum makinesidir: `initialized → processing → completed | partially_completed | failed | halted_evidence | halted_frequency | halted_critical`.

- **Ajan kaydı:** 13 ajan kurulu; 14'üncü (InterpreterAgent) yalnız `ENABLE_INTERPRETER=true` ile yüklenir.
- **Kanıt zinciri:** her ajan adımı `evidence_chain`'e imzalı kayıt düşer; `CanonicalMemory` görev başına JSON'da saklar.
- **Dürüst duruşlar:** yeterli kanıt yoksa görev `halted_*` ile durur; rezonans eşiği altındaysa `halted_frequency`; LLM yoksa ilk LLM'li ajan durur (sahte çıktı yok).

---

## 4. Zekâ yönlendirici — `agent_core/services/cognitive_router.py`

Girdiye bakar (hedef var mı? kullanıcı profili de var mı?) ve **hangi ajanların çalışacağını** planlar (`RoutePlan`). Hedef profilsiz görev "mirror_truth" yoluna kıvrılır; hem kullanıcı hem hedef varsa rezonans + sahici-köprü ajanları da plana girer.

---

## 5. Ajan kadrosu — `agent_core/agents/` (her biri tek görevli)

| Ajan | Görevi |
|---|---|
| `PassionMapperAgent` | Hedefin neşe/tutku/merak alanlarını kanıt alıntılarıyla haritalar |
| `FrictionDetectorAgent` | Sınırlar, hassasiyetler, yorulma/şikâyet noktaları |
| `CognitiveProfilerAgent` | Dil tonu, iletişim üslubu, karmaşıklık, mizah stili |
| `HumanBehaviorAnalyzer` | "Dijital cold reading": OpenCV ile görsel mikro-sinyaller + dilbilimsel izler; tamamen kod-deterministik (LLM'siz) |
| `AuthenticityAuditorAgent` | Beyanlarla görsel kanıtın çelişip çelişmediğini denetler (orijinallik) |
| `AutonomousVerifier` | Profildeki doğrulanabilir iddiaları web aramasıyla (Tavily/SerpAPI/Exa → DuckDuckGo yedeği) teyit eder |
| `DepthAnalyst` | "Gerçeklik endeksi": vitrin ile sızan gerçek arasındaki fark; çıktısı QuoteGuard'tan geçer |
| `MirrorOfTruth` | Kullanıcının kendi öz-frekansını (bio/gönderiler) yansıtır |
| `ResonanceCalculator` | Kullanıcı-hedef vektörleri arasında saf-numpy rezonans skoru (LLM'siz, matematik) |
| `ResonanceSynthesizerAgent` | Ortak paydadan **saygılı ilk temas mesajı** üretir |
| `PatternInterrupt` | Beklenti-kıran senaryo + mesaj tasarımı |
| `OsintInvestigatorAgent` | OSINT katmanı: anahtar varsa ticari API, yoksa dürüst boş fallback + kapılı maigret/holehe birleştirmesi |
| `InterpreterAgent` | Kod-yorumlayıcı (yalnız açık kapıyla; ana rotada planlanmaz) |

Her LLM'li ajanın çıktısı **Pydantic modeline** zorlanır (`extra="forbid"`); şemaya uymayan yanıt kabul edilmez.

---

## 6. Servis katmanı — `agent_core/services/`

| Servis | Rolü |
|---|---|
| `llm_gateway.py` | Model yönetimi: tier zincirleri (depth/dialogue/fast), ajan-özel zincirler, fiyat tablosu + harcama tavanı, canlı-LLM kilidi (`LIVE_LLM_E2E`), yerel model (Ollama/LM Studio) desteği, yanıt önbelleği entegrasyonu |
| `search_engine.py` | Çoklu arama sağlayıcı (Tavily/SerpAPI/Exa/DuckDuckGo) → `SearchOutcome` |
| `vision_analyzer.py` | Görselleri indirip boyut limitiyle multimodal modele verir; nesne/mekân kanıtı üretir |
| `quote_guard.py` | LLM'in verdiği alıntıları kaynak korpusa karşı doğrular; alıntısız/uydurma bulgular elenir; `public_web_sources` ile gerçek sayfa metinleri de korpusa girer |
| `decision_engine.py` + `uncertainty_engine.py` | Kanıt-kalitesi kapıları: boş/placeholder içerik kanıt sayılmaz; "tamamlandı" etiketi ancak gerçek çıktıyla verilir |
| `canonical_memory.py` | Görev belleği (JSON); kilitli asenkron okuma/yazma; kanıt zinciri birleştirme |
| `hindsight_memory.py` | Aynı API'ye anlamsal arama ekleri (SQLite + sentence-transformers; `PINEAL_MEMORY_ENGINE=hindsight`) |
| `memory_injector.py` | Geçmiş kanıtını yeni görev bağlamına enjekte eder |
| `response_cache.py` | Birebir (exact-key) LLM yanıt önbelleği (maliyet/gecikme düşürme) |
| `platform_registry.py` | Kazıma karar merkezi: `scrape_instagram` (Playwright + stealth seçici + cookie kasa) |
| `follower_audit.py` | Takipçi denetimi; ölçülemiyorsa "ölçülmedi" der, 0 yazmaz |
| `timing_forensics.py` | Gönderi saatlerinden zaman-forensiği |
| `socid_enricher.py` | Profil URL'sinden kararlı kimlik kaydı (socid-extractor; SSRF guard'lı) |
| `maigret_scanner.py` | Kullanıcı-adı varlık taraması (3302 site DB'sinden en-yüksek-rankli N; `ENABLE_MAIGRET`) |
| `holehe_scanner.py` | E-posta kayıt taraması (modül havuzu; eşzamanlı; `ENABLE_HOLEHE`) |
| `crawl_enricher.py` | Public-web sayfayı LLM-dostu metne çevirir (crawl4ai, tarayıcısız HTTP modu; `ENABLE_CRAWL4AI`) |
| `stealth_provider.py` | Stealth seçici: `playwright_stealth` (default) / `invisible` / `cloak` / `none`; binary yolları operatöre bırakılır |

Deneysel OSINT servislerinin ortak sözleşmesi: kullanılamayan tarama `available:false` + makine-okunur sebep döner; "iz yok" yalnız sıfır-hata taramada iddia edilir.

---

## 7. Veri modelleri — `agent_core/domain/`

- `memory_models.py`: `PassionProfile`, `FrictionProfile`, `CognitiveStyle`, `AuthenticBridge`, `HolisticProfile` (360° mühür), `TaskSnapshot`, `AspasiaSession`, `AgentRun`
- `pillar_models.py` / `pillar_wave2_models.py`: alt analiz motorlarının çıktı şemaları
- `pipeline_status.py`: durum makinesi sabitleri

---

## 8. Kanıt motorları — `agent_core/engines/`

Yedi deterministik motor (`Frequency, Seismos, Void, Strata, Gravity, Pulse, Key`) saf-kod profil bileşenleri üretir; `PillarOrchestrator` bunları toplayıp şemalı rapora çevirir. Bir bileşen hata verirse çıktı "başarılı" gibi gösterilmez — bileşen-hatası dürüstçe işaretlenir.

---

## 9. Kazıyıcılar — `agent_core/scraper/`

- `instagram_ghost.py`: kendi-kendi-barındıran IG kazıyıcı; Playwright sayfasıyla çalışır, **kanıt-sözleşmeli** (URL gerçeğe doğrulanır; post listesi 12 ile kırpılır; yeterli kanıt yoksa `InsufficientEvidenceError`)
- `run_scraper.py`: bağımsız CLI koşucusu

---

## 10. Psikoloji / Shadow / Aspasia

- `psychology/dark_triad.py`: profilden Dark-Triad eğilim markörleri (kanıt-yoksa 0.0; nötr-0.5 kılıfı yok)
- `shadow/shadow_executor.py`: strateji katmanı — kısmi markör eşiği geçmeden strateji türetilmez
- `aspasia/aspasia_chief.py`: profil kanıtlarıyla konuşan gözlemci sohbet şefi

---

## 11. Arayüzler

### Web — `frontend/` (Svelte + TypeScript)
`App.svelte` canlı WS akışını yönetir; `UnifiedCompactPanel.svelte` ana panel (görev durumu, loglar, telemetri, 360° profil, kanıt panelleri), `PillarFeed.svelte` alt-motor çıktı akışı. Çift dil (TR/EN, `i18n.ts`); `store.ts` reaktif durum. Vite ile derlenir (`npm run check && npm run build`).

### Mobil — `android/` (Kotlin)
Bağımsız istemci: `PinealAnalyzerEngine` (JSON şemalı analiz), `AspasiaChatEngine` (sohbet), `ForensicReconEngine` + `ReconDao` (Room ile yerel görev kayıtları), `GeminiClient` (mobil taraf LLM istemcisi), i18n TR/EN, Compose arayüz bileşenleri.

### Masaüstü deneyi — `rust_core/` (Rust)
Hız-katmanı denemesi: ajan portları (`mirror_truth`, `resonance_calculator`, `autonomous_verifier`), kazıyıcılar (`sherlock_core`, `web_crawler`), olay-veriyolu, görev-izolasyonu ve Tauri masaüstü köprüsü taslağı. CI'da `cargo check/test` ile derlenir; Python ürün yoluna bağlı değildir (ayrı deneysel hat).

---

## 12. Betikler ve kapılar

- `scripts/run_task.py`: uçtan uca CLI görev koşucusu
- `scripts/e2e_test.py`, `scripts/test_e2e_fixture.py`: uçtan uca prova
- `scripts/analyze_target_instagram.py`: tek-profil canlı demo (Chrome ister)
- `live_llm_gate.py`: **gerçek** LLM anahtarıyla hakemli uçtan uca doğrulama (sahte çağrı reddedilir)
- `scripts/benchmark_download.py`: indirme kıyaslaması

**Testler:** Yerel keşif bu checkoutta 454 test topluyor; son koşu 452 passed, 2 skipped — birim + entegrasyon + e2e + WS sıra/güvenlik/protokol. Kalıcı korumalar: production'da mock yasağı (AST-bazlı), default-kapı sözleşmesi (tüm deneysel uçlar kapalıyken `disabled` der), beyan→kurulu kütüphane zinciri, ölü-dosya yasağı, psutil çalışma-zamanı sözleşmesi.

**Yapılandırma:** tüm env örnekleri `.env.example`'da (LLM, arama anahtarları, bellek, güvenlik, OSINT kapıları, stealth). Kurulum: Windows `baslat.bat` · Docker `docker compose up --build` · Manuel `pip install -r requirements.txt && pip install -r requirements-osint.txt` (ikinci adım: crawl4ai; psutil meta-çatışması nedeniyle iki dosya) + `python -m playwright install chromium`.

**Canlı-koşu düzeltmeleri (196 teşhisi sonrası):** (1) `instagram_ghost.py` regex-kurtarma yolu artık altyazıları shortcode-penceresinden kurtarıyor — eskiden `caption=None` ile çöpe atıyordu; altyazı yoksa dürüstçe None kalır. (2) `baslat.bat` artık `requirements-osint.txt`'yi ve Playwright chromium'u da kuruyor — eskiden hiç kurmuyordu (OSINT ayak izinin %0 olması ve cognitive_profiler verisizliğinin ikinci kök nedeni). (3) Kullanıcının gerçek "çalışmıyor" arızası: ikinci başlatışta 8000 portu çakışması → `baslat.bat`'a port-koruması (sunucu açıksa sadece tarayıcı açar) + çalışma-klasörü sabitleme eklendi; kullanıcı makinesindeki bağımsız yama (Hermes ajanı) ile aynı iki arıza tespit edildi, iki yamanın en iyisi tek dosyada birleştirildi. Bu ikisi için 4 regresyon-kilidi testi eklendi. Not: bu düzeltmeler GitHub main'e (PR #35 sonrası `e4ab773`) henüz gitmedi; yeni oturumda pushlanacak.

---

## 13. Özet: her dalın tek cümlelik cevabı — "neden var?"

| Parça | Neden var |
|---|---|
| `backend/` | Tek giriş kapısı: görevleri alır, canlı akışla yürütür, sonuçları servis eder |
| `agent_core/agents/` | Her insan-boyutu için uzmanlaşmış, kanıt toplayan analistler |
| `agent_core/services/` | Ajanların ortak altyapısı: LLM, arama, bellek, denetim, kazıma, OSINT |
| `agent_core/engines/` | LLM'siz, saf-kod ölçümler (hız/güvenilirlik için deterministik bileşenler) |
| `agent_core/domain/` | Her şeyin şeması: veri ne görünecekse o kalıba girmek zorunda |
| `agent_core/scraper/` | Hedef profillerin gerçek kaynağı (kanıt dışında veri yok) |
| `agent_core/psychology|shadow|aspasia/` | Derin psikoloji, strateji ve sohbet katmanları |
| `frontend/` | Kullanıcının canlı kontrol + sonuç paneli (web) |
| `android/` | Aynı deneyimin mobil istemcisi |
| `rust_core/` | Gelecek hız/masaüstü hattının deneysel taslağı |
| `scripts/` + `live_llm_gate.py` | Otomasyon, prova ve gerçek-LLM kabul kapısı |
| `tests/` | Sözleşmelerin kalıcı garantisi (450 test; yanlışlıkla geri adım anında görünür) |

*Rapor: `DURUM_RAPORU.md` — kod okumasından üretildi; bakım sırasında kod değişince bu belge de güncellenmelidir.*

**Olay kaydi (venv sizmasi):** kullanici makinesinden yapilan push'ta (d887ed38) noktasiz `venv/` klasorunun tamami (~20 bin dosya, 144 MB, 88 MB'lik node.exe dahil) yanlikla depoya islenip GitHub'a gitti. Kok neden: .gitignore yalniz `.venv/` kapsiyordu; baslat.bat ise noktasiz `venv\` yaratiyor. Cozum: `venv/` .gitignore'a eklendi + `git rm -r --cached venv` ile takipten cikarma. Not: 144 MB git-gecmisinde kalir; gecmisin temizlenmesi ayri bir history-rewrite isidir (zorla-itme gerektirir, talep uzerine).
