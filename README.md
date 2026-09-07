# PINEAL-HERETIC v3.1 · PINEAL 360° Bütüncül İnsan Tanıma & Adli Bilişsel İstasyon

Sosyal medya profillerini (Instagram / X) anonim tarayan; fotoğrafları ve videoları **çoklu modlu görsel zeka (VisionAnalyzer)** ile inceleyen; kişiyi tutkular, neşe, savunma mekanizmaları, sınırlar ve bilişsel üslup boyutlarında **360° kanıta dayalı ve matematiksel** olarak çözümleyen, LLM destekli tek kullanıcılı yerel bir analiz istasyonudur.

Kararları `PinealExecutor` + `CognitiveRouter` + `PsychodynamicDepthEngine` verir; **Aspasia** karar verici değil, sistem durumunu ve hafızayı açıklayan, `DiskMemoryBridge` ile disk kayıtlarına bağlı kurmay gözlemci/personadır.

---

## 1. Temel Mimari ve Yeni Nesil Motorlar

Bu sürüm, sistemin önceki statik ve tek sağlayıcıya bağımlı yapısını tamamen yıkan 4 ana motoru içerir:

### A. 14 Sağlayıcılı Hibrit Çıkarım Havuzu (Multi-Provider Engine)
Sistem artık tek bir sağlayıcıya (OpenRouter) kilitlenmez. 16 anahtarlık yerel envanteri (`.pineal_vault.json` ve `.env`) doğrudan tanır:
- **Resmi OpenAI Uyumlu Uç Noktalar:** Google Gemini (`/v1beta/openai/`), DeepSeek (`api.deepseek.com/v1`), NVIDIA NIM (`integrate.api.nvidia.com/v1`).
- **Ultra Hızlı Ücretsiz Katman:** Groq (30 RPM), Cerebras (5 RPM).
- **Açık Ağırlıklı Havuz:** Together AI, DeepInfra, Nous Research Portal.
- **Olgusal OSINT & Doğrulama:** Tavily, SerpAPI, Exa AI.
- **Hiyerarşik Kasa:** `.pineal_vault.json` içindeki `providers.{ad}.api_key` yapısı şemadan bağımsız güvenle parse edilir; sırlar asla loglara sızmaz.
- **Savunma Derinliği:** `PINEAL_ALLOW_PAID_ESCALATION=1` ve `PINEAL_ALLOW_UNPRICED_MODELS=1` bayrakları olmadan bütçe koruması fail-closed kalır.

### B. Zaman Serisi & Video Kazıyıcı (GÖREV 1 — Scraper Engine)
- **`/reel/` ve Video Desteği:** Yalnızca `/p/` değil, `/reel/` URL'leri de taranır. Post türleri (`image`, `video`, `reel`, `carousel`) ve video bağlantıları toplanır.
- **1-e-1 Doğrulanmış Eşleşme:** Görseller ve post linkleri arasındaki kör `zip()` indeksi kaldırılmıştır. Her görsel kendi shortcode ve metin bloğuyla doğrulanmış tekil nesne olarak paketlenir.
- **Kronolojik Zaman Ekseni:** Zaman damgaları (`taken_at`), beğeni ve yorum sayıları parse edilerek tüm gönderiler $t_0 \to t_N$ kronolojisine dizilir.

### C. 4 Sütunlu Psikodinamik Derinlik Motoru (GÖREV 2 — Depth Engine)
İlkel kelime sayma sözlükleri (`['strateji', 'piyon']`) ve sanat tarihi etiketleri tamamen kaldırılmıştır. Sistem insanı 4 matematiksel sütunla analiz eder:
1. **Denetimsiz Semantik Kümeleme (`theme_cluster.py`):** Karakter 3-gram ve kosinüs benzerliği ile çalışır. Profilin metinlerinden $K$ adet doğal tema türer; **Kompülsif Tekrar Skoru (`repetition_score`)** ve **İzole Anomali Tespiti (`isolated_anomaly_count`)** üretilir.
2. **Durum Yörüngesi $S(t)$ ve Faz Kırılması (`timing_forensics.py`):** Gönderiler zaman fonksiyonuna dökülür; varyans makası, yarı-entropi ve **Faz Kırılma Noktaları (`entropy_jump`, `variance_shift`)** tespit edilir.
3. **4 Kanallı Çapraz Gerilim Matrisi (`psychodynamic_depth.py`):**  
   - *Kanal 1 (Beyan):* Biyografi ve yazılı açıklamalar (Ego ideali)
   - *Kanal 2 (Sahneleme):* Görseller, format çeşitliliği, estetik dil (Dış vitrin)
   - *Kanal 3 (Biyolojik Ritim):* Zaman damgaları, sirkadiyen döngü (Dürtü kontrolü)
   - *Kanal 4 (Sosyal Metrik):* Takipçi/takip oranı, etkileşim asimetrisi  
   Bu kanallar arasındaki gerilimden yapısal **Telafi İndeksi (`compensation_index`)** ve **Reaksiyon Oluşturma İndeksi (`reaction_formation_index`)** hesaplanır.
4. **Bayesian Dinamik Epistemik Kapı:** `if not text: halt` katliamı silinmiştir. Profilde metin yoksa ($w_{\text{decl}} = 0$), epistemik bütçe otomatik olarak Görsel ve Zamansal kanallara aktarılır ($w_{\text{vis}} + w_{\text{temp}} = 1.0$). Sistem metinsiz profillerde asla durmaz.

### D. Aspasia Disk Köprüsü (`DiskMemoryBridge`)
Aspasia artık geçici RAM'e mahkûm değildir. RAM boşalsa bile diskteki `CanonicalMemory` kayıtlarını okur; sistem boşta beklerken hayali ajanlar uydurmaz (`ROUTING-ADAY` vs `GÖZLEMLENEN`), geçmiş operasyonları unutmaz.

---

## 2. Dış Cephanelik ve Hafıza Mühendisliği (Seçilmiş Entegrasyonlar)

Sistemi hantal servislerle boğmak yerine ("Çok sikmekle çok çocuk olmaz"), Pineal'in omurgasına organik olarak kaynayan **3 altın bileşen** benimsenmiştir:

| Bileşen | Kaynak | Pineal'deki Entegrasyon Yeri | Sağladığı Güç |
|---|---|---|---|
| **RTK (Rust Token-saver)** | `rtk-ai/rtk` | `rust_core/` | Ham veri promptlarını Rust katmanında %40-%85 oranında sıkıştırarak token kotasını ve bütçeyi 4 katına çıkarır. |
| **One-API / ai-wanderer Mantığı** | `songquanpeng/one-api` & `sshnaidm/ai-wanderer` | `llm_gateway.py` | Ağır Go sunucusu kurulmaz; **akıllı havuz mantığı** kullanılır: 429 alan anahtar 5 dk soğutulur, Groq (30 RPM) dolunca anında Cerebras Free'ye atlanır. |
| **Pollinations.ai** | `pollinations.ai` | HTTP İstemcisi | Kurulumsuz, anahtarsız acil durum görsel ve çıkarım can simidi; tüm API kotaları bitse dahi analizin sürmesini sağlar. |

*(Not: G4F, 9Router, CLIProxyAPI ve Cloudflare Worker gibi harici kırılgan ve hantal yapılar sistemin hafifliğini ve kararlılığını korumak adına elenmiştir.)*

---

## 3. Sistem Mimarisi (Veri Akış Diyagramı)

```
[ HEDEF PROFİL (URL / Instagram) ]
        │
        ▼
[ Hayalet Tarayıcı ] (Playwright + Stealth; /p/ + /reel/ + zaman damgaları)
        │
        ▼
[ 1-e-1 Doğrulanmış Kronolojik Nesneler (t_0 -> t_N) ]
        │
        ├────────────────────────────────────────┐
        ▼                                        ▼
[ VisionAnalyzer ]                       [ TimingForensics ]
 (Multimodal / Gemini OpenAI)             (Durum Yörüngesi S(t) + Kırılmalar)
        │                                        │
        └───────────────────┬────────────────────┘
                            ▼
               [ ThemeCluster Engine ]
                (Denetimsiz 3-Gram Kümeleme, Kompülsif Tekrar)
                            │
                            ▼
             [ PsychodynamicDepth Engine ]
              ├─ 4 Kanallı Gerilim Matrisi (Beyan vs Vitrin vs Ritim vs Sosyal)
              ├─ Telafi & Reaksiyon Oluşturma İndeksleri
              └─ Bayesian Epistemik Kapı (Metinsiz profilde w_vis+w_temp=1.0)
                            │
                            ▼
PinealExecutor (Durum Makinesi + Ajan Orkestrasyonu)
 ├─ OSINTInvestigator & AuthenticityAuditor
 ├─ AutonomousVerifier (Tavily / SerpAPI / Exa)
 ├─ DepthAnalyst (Matematiksel yapıları psikanalitik senteze çevirir)
 ├─ ShadowExecutor (Kompülsiyon ve kırılmalara dayalı strateji vektörleri)
 └─ ResonanceCalculator (Saf numpy)
        │
        ▼
CanonicalMemory (memory/*.json kanıt zinciri)
        │
        ├─ DiskMemoryBridge (Aspasia için kalıcı bellek köprüsü)
        ├─ LLM Response Cache (cache/responses.db)
        └─ WebSocket Event Queue ──► Svelte 5 UI (Canlı Gösterge Paneli)
```

---

## 4. Kurulum ve Çalıştırma

### A) Windows (Tek Komutla Başlatma)
```bat
baslat.bat
```
Gerekli sanal ortamı kurar, bağımlılıkları yükler, frontend derlemesini kontrol eder ve istasyonu `http://localhost:8000` adresinde ayağa kaldırır.

### B) Manuel Kurulum
```bash
# 1. Bağımlılıkları yükleyin
pip install -r requirements.txt
pip install -r requirements-osint.txt
python -m playwright install chromium

# 2. Frontend'i derleyin
cd frontend
npm ci && npm run build
cd ..

# 3. Sunucuyu başlatın
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```
Arayüze `http://localhost:5173` (geliştirici modu) veya `http://localhost:8000` (üretim) üzerinden erişebilirsiniz.

---

## 5. Yapılandırma (`.env` ve Kasa Rehberi)

Anahtarlarınızı güvenli şekilde `.pineal_vault.json` kasasına koyabilir veya `.env` üzerinden tanımlayabilirsiniz:

| Değişken / Alan | Açıklama |
|---|---|
| `GEMINI_API_KEY` | Google Gemini multimodal görme ve spatial analiz anahtarı (OpenAI uyumlu endpoint). |
| `DEEPSEEK_API_KEY` | DeepSeek V3 ve R1 doğrudan akıl yürütme API anahtarı. |
| `GROQ_API_KEY` | Düşük gecikmeli çıkarım (30 RPM ücretsiz gpt-oss-120b / Llama 3.3). |
| `CEREBRAS_API_KEY` | Wafer-scale ultra hızlı inferans anahtarı. |
| `NVIDIA_API_KEY` | NVIDIA NIM donanım hızlandırmalı mikroservis anahtarı. |
| `TOGETHER_API_KEY`, `DEEPINFRA_API_KEY` | Açık ağırlıklı modeller için yüksek kapasiteli çıkarım havuzları. |
| `OPENROUTER_API_KEY` | Genel sınır modeller için ağ geçidi anahtarı. |
| `TAVILY_API_KEY`, `SERPAPI_API_KEY`, `EXA_API_KEY` | Olgusal web araması ve ters görsel OSINT motorları. |
| `PINEAL_ALLOW_PAID_ESCALATION` | `1` iken ücretli sınır modellere geçişe izin verir (fail-closed bütçe koruması). |
| `PINEAL_ALLOW_UNPRICED_MODELS` | `1` iken fiyat tablosunda olmayan doğrudan sağlayıcı modellerine izin verir. |
| `OPENROUTER_MAX_SPEND_USD` | Oturum başına harcama tavanı (Aşılırsa kod canlı çağrıları durdurur). |
| `PINEAL_POST_DETAIL_ENABLED` | `1` iken kazıyıcı post detaylarına giderek zaman damgası ve beğeni verilerini toplar. |
| `PINEAL_POST_DETAIL_LIMIT` | Detayı çekilecek maksimum gönderi sayısı (Varsayılan: `12`). |

---

## 6. Test ve Doğrulama Disiplini

Sistem, gevşek testleri ve sahte mock'ları reddeden **Mutasyon Testi (Fault Injection)** disipliniyle korunmaktadır:
```bash
# Tüm test süitini çalıştır (980+ test):
pytest -q

# Yeni motorların hedefli testleri:
pytest tests/unit/test_gorev1_reel_video_chrono.py tests/unit/test_gorev2_depth_engine.py tests/unit/test_vault_providers_schema.py -q
```
- **0 Regresyon İlkesi:** Her yeni mimari ekleme, `comm` regresyon filtresinden geçirilerek eski testleri kırmadığı kanıtlanarak merge edilir.
- **Mutasyon Kanıtı:** Güvenlik duvarı veya bellek kontrolleri kaldırıldığında testlerin kırmızıya (`FAILED`) düştüğü doğrulanmıştır.

---

## 7. Güvenlik, Gizlilik ve Yasal Sınırlar
- **Kişisel Veri:** Pineal tek kullanıcılı bir yerel analiz aracıdır. Elde edilen veriler yalnızca `memory/` klasöründe yerel JSON olarak tutulur; üçüncü şahıslara veya telemetri sunucularına aktarılmaz.
- **Sır Güvenliği:** API anahtarları asla istemci tarafına (frontend) veya log dosyalarına açık metin olarak iletilmez (`redact_structure`).
- **Etik Çerçeve:** Sistem platformlara otomatik/gizli mesaj atmaz, bot faaliyeti yürütmez. Amaç manipülasyon değil, adli düzeyde bilişsel ve psikodinamik haritalandırmadır.
