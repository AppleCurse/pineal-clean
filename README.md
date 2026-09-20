# PINEAL-HERETIC v3.2 · PINEAL 360° Bütüncül İnsan Tanıma & Adli Bilişsel İstasyon

> **"Kodu okuyanla belgeyi okuyan aynı şeyi görecek."**  
> Bu belge, depodaki canlı koddan doğrulanmış teknik ve operasyonel kılavuzdur.  
> **Doğrulama Noktası:** HEAD `1a97ee31` (2026-09-20 / 2026-09-21).  
> Bu sürümde yalnızca **kodda karşılığı olan** özellikler, rotalar ve mimari anlatılır; kodda olmayan hiçbir sağlayıcı, hayali model veya uydurma iddia yer almaz.

---

## 1. Pineal Nedir? (En Basit Anlatımla)

Pineal; bir hedefin açık kaynaklı dijital ayak izlerini (Instagram paylaşımları, metinleri, fotoğrafları, zamansal etkileşim ritimlerini) toplayan, bunları **yapay zekaya fal baktırmadan**, matematiksel ve deterministik algoritmalarla analiz eden **yerel bir adli psikodinamik profil istasyonudur**.

### Sistemin 3 Temel Farkı:
1. **LLM'ler Falcı Değildir:** Karakter analizi ve bastırılmış duygular LLM'lere "tahmin ettirilmez". 7 adet saf matematiksel dalga motoru metin ve zaman serisini doğrudan ölçer. LLM'ler yalnızca en son aşamada dil sentezi ve çapraz denetim için kullanılır.
2. **Kanıt Mührü (Fail-Closed):** Verisi veya kanıtı olmayan hiçbir iddia üretilemez (`InsufficientEvidenceError`). Sistem boşlukları sallayarak doldurmaz; veri yoksa o kanalı dürüstçe kapatır veya durur.
3. **Yerel 9Router Omurgası:** Harici SaaS servislerine veya tekil anahtarlara bağımlı kalmaz. Bilgisayarda çalışan yerel `9Router` (`127.0.0.1:20128/v1`) üzerinden 7 bağımsız, yedekli ve filtrelenmiş hat ile haberleşir.

```
[ Ham Kanıtlar ] ──> [ Deterministik Dalga Motorları ] ──> [ Uzman Ajanlar ] ──> [ 9Router Hub ] ──> [ Adli Kanıt Raporu ]
(Metin, Zaman, Resim)   (Saf Matematik / LLM'siz)      (Psyche Profiler)    (7 Canlı Rota)     (memory/<task_id>.json)
```

---

## 2. Sistemin 3 Katmanlı Mimarisi

### KATMAN 1: Veri Toplama ve Zenginleştirme (Sensörler)
- **Instagram Ghost Scraper (`scraper/instagram_ghost.py`):** Playwright motoru ve kullanıcı oturumuyla `/p/` (gönderi) ve `/reel/` çeker. Hedef profildeki metinleri, tarihleri ve medya bağlantılarını toplar.  
  *(Not: X / Twitter kazıması etik ve mimari kurallar gereği kodda kalıcı olarak kapalıdır: `x_scraper: false`).*
- **Arama Motoru (`services/search_engine.py`):** Tavily, SerpAPI veya Exa üzerinden hedef hakkında açık web doğrulaması yapar.
- **Deneysel OSINT Araçları (`services/maigret_scanner.py`, `holehe_scanner.py`):** Kullanıcı adı ve e-posta çapraz sorgulaması yapar. **Varsayılan olarak kapalıdır** (`ENABLE_MAIGRET=false`, `ENABLE_HOLEHE=false`), yalnızca operatör bayrağıyla açılır.

### KATMAN 2: Yedi Nöro-Bilişsel Dalga Motoru (Saf Matematik — LLM'siz)
Bu motorlar `agent_core/engines/` altında yaşar. Hiçbir harici API veya LLM çağırmazlar:

```
                      ┌── FrequencyEngine  (Sirkadiyen Ritim, Gece/Gündüz Enerji Dağılımı)
                      ├── SeismosEngine    (Kutup Değişimi, Ani Davranışsal Fay Kırılmaları)
                      ├── VoidEngine       (Negatif Uzay: 10 Temel Konudan Bilinçli Kaçınma)
PillarOrchestrator ───┼── StrataEngine     (Zaman İçinde Değişen / Sönümlenen Maskeler)
                      ├── GravityEngine    (Anlatı Çekim Merkezleri, Tekrarlayan Takıntılar)
                      ├── PulseEngine      (Dijital Beden Dili: Cümle/Noktalama Ritimleri)
                      └── KeyEngine        (6 Motorun Çıktısını Birleştiren Rezonans Sentezi)
```

| Motor | Dosya | Analitik Görev |
|---|---|---|
| **Frequency** | `frequency_engine.py` | Paylaşım saatlerini dalga boyuna döker; uykusuzluk, gece üretkenliği (`night_energy_share`). |
| **Seismos** | `seismos_engine.py` | Duygu durumundaki sert zikzakları ve kırılma noktalarını (`SeismicEvent`) tespit eder. |
| **Void** | `void_engine.py` | İnsanın bahsetmediği konuları (aile, para, başarısızlık vb.) bularak "bastırılan alanı" çıkarır. |
| **Strata** | `strata_engine.py` | Yıllar içindeki kimlik kaymalarını (`IdentityDrift`) ve terk edilmiş maskeleri inceler. |
| **Gravity** | `gravity_engine.py` | Kişinin sürekli lafı getirdiği ana takıntı odaklarını (`GravityWell`) ölçer. |
| **Pulse** | `pulse_engine.py` | Metindeki nefes ritmini; ünlem, soru işareti, duraksama sıklığını sayısallaştırır. |
| **Key** | `key_engine.py` | Yukarıdaki 6 motorun çıktısını kural tabanlı birleştirip `ResonanceVector` üretir. |

#### Dört Sütunlu Psikodinamik Derinlik:
1. **Semantik Kümeleme (`services/theme_cluster.py`):** Karakter 3-gram TF vektörleri ve kosinüs benzerliği ile çalışır. Ezber tema listesi yoktur; hedef kişinin kendi kelime dünyasından kümeler kurar.
2. **Durum Yörüngesi (`services/timing_forensics.py`):** Zaman dizisini ikiye bölerek varyans ve entropi sıçramalarını yakalar.
3. **Çapraz Gerilim Matrisi (`services/psychodynamic_depth.py`):** Sözü ile davranışı arasındaki açığı ölçerek telafi (`compensation_index`) ve reaksiyon oluşturma katsayılarını çıkarır.
4. **Bayesian Epistemik Bütçe:** Hedefin yazılı metni yoksa söz kanalı ağırlığı sıfırlanır (`w_declaration = 0`); bütçe otomatik olarak görsel ve zamansal kanallara devredilir.

---

## 3. 9Router Yerel Yönlendirme Katmanı (Local Gateway v0.5.81)

Pineal v3.2, tüm LLM iletişimini doğrudan harici sağlayıcılara yapmak yerine yerel makinede çalışan **9Router hub'ı** (`http://127.0.0.1:20128/v1`) üzerinden yürütür.

### Neden 9Router?
- **Gizlilik:** Dış dünyaya token sızmasını önler; Pineal yalnızca yerel loopback ile konuşur.
- **Sıfır Maliyet & Akıllı Kota:** Antigravity OAuth havuzunu ve Groq ücretsiz çıkarım katmanını kullanır. Kanıt zincirine dürüstçe `cost_usd: null` ve `cost_note: "antigravity_oauth_quota"` basılır.
- **Deterministik Fallback:** 9Router veritabanında (`settings.data`) tüm stratejiler `fallback` olarak kilitlenmiştir (`comboStrategy: fallback`). Bir model yanıt vermezse sıradaki yedek devreye girer; rastgele seçim yapılmaz.

### 7 Canlı Rota ve Yedekleme Mimarisi (200 OK Doğrulanmış)

| Rota Adı | Birincil Model (Primary) | 1. Yedek (Fallback 1) | 2. Yedek (Fallback 2) | Görevi & Canlı Gecikme |
|---|---|---|---|---|
| `pineal-deep-reasoning` | `ag/claude-sonnet-4-6` | `ag/gemini-3.8-flash` | `gemini/gemini-3.8-flash` | Derin psikodinamik sentez ve rezonans köprüsü (~1.27s - 1.47s) |
| `pineal-general-reasoning`| `ag/gemini-3.8-flash` | `gemini/gemini-3.8-flash` | `kimchi/qwen3.8-27b` | Davranış, bilişsel stil ve sürtünme analizi (~0.88s - 1.36s) |
| `pineal-fast-extract` | `groq/openai/gpt-oss-120b`| `ag/gpt-oss-120b-medium` | `kimchi/qwen3.8-27b` | Hızlı tutku haritalama ve veri ayrıştırma (**~180ms - 300ms**) |
| `pineal-vision` | `ag/gemini-3.8-flash` | `gemini/gemini-3.8-flash` | `kimchi/qwen3.8-27b` | Görsel adli tıp ve fotoğraf kompozisyonu (~1.12s, görsel: ~2.36s) |
| `pineal-juror-google` | `ag/gemini-3.8-flash` | `gemini/gemini-3.8-flash` | — | Bağımsız Jüri: Google Ailesi (~0.78s - 0.94s) |
| `pineal-juror-claude` | `ag/claude-sonnet-4-6` | — | — | Bağımsız Jüri: Anthropic Ailesi (~0.88s - 1.19s) |
| `pineal-juror-open` | `groq/openai/gpt-oss-120b`| `kimchi/qwen3.8-27b` | — | Bağımsız Jüri: Açık Kaynak Ailesi (~0.31s) |

#### Özel İzole Rota: `pineal-claude-scarce`
- **Model:** `kr/claude-sonnet-4.5`
- **Durum:** Kiro hesabının aylık yalnızca ~50 kredisi olduğu için genel havuzdan **tamamen çıkarılmıştır**. Yalnızca operatörün açıkça onayladığı manuel eskalasyon durumlarında çağrılır; rutin test veya analizlerde harcanmaz.

#### Çapraz Jüri Kuralı (Anti-Halüsinasyon)
Doğrulama aşamasında (`AutonomousVerifier`), 3 farklı model ailesinden oluşan bağımsız bir jüri paneli (`Google`, `Claude`, `Open`) karar verir. **Temel Kural:** Analizi üreten model Claude ise, Claude jüriden otomatik olarak çıkarılır. Hiçbir model kendi yazdığı çıktıyı denetleyip onaylayamaz.

---

## 4. Uzman Ajan Envanteri ve Rota Eşleşmesi

Sistemdeki ajanlar `agent_core/agents/` altında bulunur. Kod tekrarını önlemek amacıyla profil ajanları `TargetPsycheProfiler` ortak tabanından miras alır:

```
                      ┌── PassionMapper     (Tutkular, Yüksek Enerji Alanları)
TargetPsycheProfiler ─┼── FrictionDetector  (Kişisel Sınırlar, Öfke/Sürtünme Tetikleyicileri)
                      └── CognitiveProfiler (Bilişsel Düşünce ve Karar Alma Stili)
```

| Ajan Adı | Bağlı Olduğu Rota | Yedek / Mekanizma | Analitik Sorumluluk |
|---|---|---|---|
| `passion_mapper` | `pineal-fast-extract` | (combo) | Hedefin tutku duyduğu, enerjisinin yükseldiği konuları çıkarır. |
| `friction_detector` | `pineal-general-reasoning` | (combo) | Kırılma ve savunma yaratan hassas noktaları tespit eder. |
| `cognitive_profiler`| `pineal-general-reasoning` | (combo) | Soyut/somut, analitik/sezgisel düşünme kalıplarını belirler. |
| `depth_analyst` | `pineal-deep-reasoning` | (combo) | Gerçeklik indeksi (`reality_index`) ve çelişki raporlar. |
| `resonance_calc` | `local-numpy` | — | Kullanıcı ile hedef frekansını vektörel karşılaştırır (<0.70 ise durur). |
| `resonance_synthesizer`| `pineal-deep-reasoning`| (combo) | Manipülasyonsuz, şeffaf ilk temas köprüsü tasarlar. |
| `human_behavior` | `pineal-general-reasoning` | (combo) | Sosyal davranış ve beden dili sinyallerini sentezler. |
| `vision_analyzer` | `pineal-vision` | (combo) | Profil fotoğraflarını ve sahneleme öğelerini inceler. |
| `authenticity_auditor`| `pineal-vision` | (forensic) | Görsellerde yapay zeka üretimi veya manipülasyon arar. |
| `autonomous_verifier`| `pineal-verifier-panel` | (3 jüri) | Çıkarımları 3 farklı aileden jüriye onaylatır. |
| `osint_investigator` | `pineal-osint-pipeline` | (pipeline) | Web arama motorları üzerinden çapraz teyit yapar. |
| `mirror_truth` | `pineal-deep-reasoning` | (combo) | Kullanıcının kendi niyeti ile yüzey personasını yüzleştirir. |
| `aspasia` | `DiskMemoryBridge` | — | Üst akıl denetçisi; diskteki adli mühürleri denetler. |

---

## 5. Çift Katmanlı Bellek ve Adli Kanıt

- **Kanonik Bellek (`services/canonical_memory.py`):** Her görevin tüm girdileri, motor çıktısı, çağrılan modeller ve jüri onayları `memory/<task_id>.json` dosyasında kriptografik mühürle saklanır.
- **Aspasia Arayüzü (`aspasia/interface.py`):** Üst akıl gözlemcisidir; orchestrator değildir. Diskteki `forensic_digest` mührünü okur. Gerçekte çağrılmamış hiçbir ajanı veya modeli "çalıştı" diye raporlamaz (`ROUTING-ADAY` vs `GÖZLEMLENEN` ayrımı).
- **Yanıt Önbelleği (`services/response_cache.py`):** Mükerrer çağrıları önlemek için SQLite üzerinde SHA-256 hash anahtarlı deterministik önbellekleme yapar.

---

## 6. Kurulum ve Çalıştırma

### A) Windows (Tek Tıkla Başlatma)
En kolay kurulum yoludur. Sanal ortamı hazırlar, frontend'i derler ve uvicorn sunucusunu açar:
```bat
baslat.bat
```
Tarayıcıda: `http://localhost:8000`

### B) Docker ile Çalıştırma
```bash
docker compose up --build
```
`pineal_memory` ve `pineal_cache` volume'ları ile veriler konteyner kapansa dahi korunur.

### C) Manuel Geliştirici Kurulumu
```bash
# 1. Python bağımlılıklarını kur
pip install -r requirements.txt
python -m playwright install chromium

# 2. Frontend derlemesini yap
cd frontend
npm ci
npm run build
cd ..

# 3. Sunucuyu başlat
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```
Geliştirme esnasında canlı arayüz düzenlemek için:
```bash
cd frontend && npm run dev
# http://localhost:5173 adresinden Vite proxy ile bağlanır
```

---

## 7. Yapılandırma Kılavuzu (`.env`)

Sistem kök dizindeki `.env` dosyasını okur. Örnek yapılandırma şablonu:

```env
# === 9ROUTER YEREL HUB BAĞLANTISI ===
PINEAL_LLM_BACKEND=unified
PINEAL_LLM_BASE_URL=http://127.0.0.1:20128/v1
PINEAL_LLM_API_KEY=sk-pineal-your-key-here
X_9ROUTER_TOKEN_SAVER=off

# === ORTAM VE GÜVENLİK ===
PINEAL_ENV=development
PINEAL_REQUIRE_AUTH=false
PINEAL_TOKEN=your-secret-access-token

# === DOĞRULAMA VE ARAMA MOTORLARI ===
TAVILY_API_KEY=tvly-...
# SERPAPI_API_KEY=...
# EXA_API_KEY=...

# === OPSİYONEL OSINT KAPILARI (VARSAYILAN KAPALIDIR) ===
ENABLE_MAIGRET=false
ENABLE_HOLEHE=false
ENABLE_CRAWL4AI=false
```

---

## 8. Test, Doğrulama ve Sağlık Kontrolleri

Pineal, sıkı sözleşme testleri ve otomatik sağlık kontrolleri ile korunur:

### 1. Yerel Test Paketi (Pytest)
```bash
python -m pytest tests/unit/ tests/integration/
```
- **Durum:** **1.041 test (1.038 passed, 3 skipped, 0 failed)**.
- Harcama testleri, model sözleşmeleri ve sahte model isimlerinin engellenmesi AST düzeyinde test edilir (`test_frontend_agent_model_contract.py`).

### 2. Canlı 9Router Preflight Sağlık Denetimi
7 canlı rotanın ve multimodal görsel hattının anlık ayakta olup olmadığını tek komutla test eder:
```bash
python scripts/preflight_9router.py
```
*Tüm rotalara canlı probe atar, gecikmeleri ölçer ve `reports/9router_preflight_latest.json` dosyasına işler.*

### 3. Frontend Tip ve Build Kontrolü
```bash
cd frontend
npm run check
npm run build
```
*Svelte ve TypeScript tip doğrulaması 0 hata ile geçer.*

### 4. CI/CD Otomasyonu (`.github/workflows/`)
- `ci.yml`: Her `git push` işleminde backend testlerini, frontend derlemesini, Rust bileşenlerini ve sözleşme gölgelerini otomatik doğrular.
- `preflight.yml`: Yerel 9Router hattını periyodik olarak canlı probe ile denetler.

---

## 9. Sıkça Sorulan Sorular (SSS)

**S: Neden hedef hakkında hemen süslü bir burç yorumu gibi analiz çıkmıyor?**  
**C:** Çünkü Pineal fal bakmaz. Kanıt Mührü ilkesi gereği, metin veya zaman damgası toplanmadan hiçbir psikolojik motor çalıştırılmaz. Kanıt yetersizse sistem durur (`InsufficientEvidenceError`).

**S: Bir LLM rotası çökerse veya internet giderse ne olur?**  
**C:** 9Router üzerinde tanımlı deterministik `fallback` devreye girer. Örneğin `pineal-deep-reasoning`'de Claude Sonnet yanıt vermezse otomatik olarak 1. yedek olan Gemini 3.8 Flash'a geçer. Geçiş kanıt zincirinde (`resolved_model`) açıkça belgelenir.

**S: Kişisel veriler dışarı sızar mı?**  
**C:** Hayır. Analiz edilen tüm veriler yerel makinenizdeki `memory/` klasöründe JSON formatında saklanır. Dışarıya hiçbir telemetri veya gizli veri gönderilmez.
