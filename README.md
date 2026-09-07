# PINEAL-HERETIC v3.1 · PINEAL 360° Bütüncül İnsan Tanıma & Adli Bilişsel İstasyon

> **"Kodu okuyanla belgeyi okuyan aynı şeyi görecek."**  
> Bu belge, Pineal-Heretic deposundaki tüm Python modüllerinin, 7 nöro-bilişsel motorun, 13 ajanın, adli OSINT tarayıcılarının, 14 sağlayıcılı hibrit yönlendiricinin ve bellek mimarisinin koddan doğrulanmış eksiksiz teknik kılavuzudur.

---

## 1. Sistemin Mühendislik ve Felsefi Temeli

Pineal, yüzeysel sosyal medya etiketleyicisi veya basit bir LLM wrapper'ı değildir. Çok kanallı kanıt toplayan, zaman serisi diferansiyelini hesaplayan, insan psikolojisindeki bastırılmış boşlukları ve savunma mekanizmalarını matematiksel olarak modelleyen **yerel bir adli istihbarat ve bilişsel profil istasyonudur**.

### Temel Çalışma İlkeleri
1. **Sıfır Halüsinasyon & Kanıt Mührü:** Hiçbir ajan veri uyduramaz. Her çıkarım somut bir nesneye, zaman damgasına, dilsel desene veya dijital ayak izine dayanmak zorundadır. Kanıt yetersizse sistem durur (`fail-closed`).
2. **Topolojik ve Matematiksel Psikodinamik:** İnsan karakteri statik kelimelerle ('piyon', 'strateji') ölçülemez. Profilin kendi anlamsal uzayındaki denetimsiz kümeler ($K$), durum yörüngesi türevi ($\Delta S / \Delta t$) ve kanallar arası gerilim matrisi hesaplanır.
3. **Çok Kanallı Çelişki Tespiti:** İnsanın iddia ettiği benlik (Beyan), dışarıya sergilediği vitrin (Sahneleme), kontrol edemediği biyolojik ritmi (Zaman) ve ağ konumu (Sosyal) arasındaki sürtünme doğrudan **Savunma Mekanizmaları Katsayısına** (Telafi ve Reaksiyon Oluşturma) dönüştürülür.
4. **Bayesian Epistemik Güven:** Metinsiz profillerde sistem kilitlenmez; sözel ağırlık sıfırlanarak epistemik bütçe doğrudan Görsel ve Zamansal kanallara aktarılır ($w_{\text{vis}} + w_{\text{temp}} = 1.0$).

---

## 2. Yedi Nöro-Bilişsel Dalga Motoru (`agent_core/engines/`)

Sistemin altında, LLM'den bağımsız olarak ham metin ve zaman serisi üzerinde deterministik dalga analizi yürüten 7 temel motor çalışır. Bunlar `PillarOrchestrator` tarafından iki fazlı asenkron olarak yönetilir:

```
                      ┌── FrequencyEngine  (Zaman Dalgası, Gece/Gündüz Enerji Payı)
                      ├── SeismosEngine    (Kutup Değişimi, Davranışsal Kırılmalar)
                      ├── VoidEngine       (Negatif Uzay, Bastırılan/Konuşulmayan Alanlar)
PillarOrchestrator ───┼── StrataEngine     (Uzunlamasına Katmanlar, Fosil Kayıtları)
                      ├── GravityEngine    (Anlatı Çekim Merkezleri, Kara Delik Odakları)
                      ├── PulseEngine      (Dijital Beden Dili, Biyometrik Sinyaller)
                      └── KeyEngine        (Tüm Motorların Kural Tabanlı Rezonans Sentezi)
```

| Motor | Dosya | Matematiksel / Analitik Görevi | Çıktı Modeli |
|---|---|---|---|
| **Frequency** | `frequency_engine.py` | Gönderi zaman damgalarını ($t$) dalga boyuna döker; sirkadiyen ritmi ve gece enerji payını (`night_energy_share`) hesaplar. | `FrequencyReport` |
| **Seismos** | `seismos_engine.py` | Metin polarite sıçramalarını ve duygusal şok dalgalarını ölçer; sismik fay kırılmalarını (`SeismicEvent`) tespit eder. | `SeismosReport` |
| **Void** | `void_engine.py` | **Negatif Alan Analizi:** Toplumda beklenen 10 temel kategoriden (aile, para, din, siyaset, kariyer vb.) hangilerinin profilde kasten/bilinçdışı *hiç konuşulmadığını* tespit eder. | `VoidReport` |
| **Strata** | `strata_engine.py` | Profilin zaman içindeki jeolojik katmanlarını inceler; sönümlenen eski kimlikleri (`extinction_threshold`) ve kimlik kaymasını (`IdentityDrift`) modeller. | `StrataReport` |
| **Gravity** | `gravity_engine.py` | Profildeki tekrarlayan takıntı merkezlerini ve anlatı çekim kuyularını (`GravityWell`) hesaplar. | `GravityReport` |
| **Pulse** | `pulse_engine.py` | Cümle uzunluğu varyansı, noktalama ritmi ve metin nefes aralıklarından dijital beden dili çıkarır. | `PulseReport` |
| **Key** | `key_engine.py` | 6 motorun çıktılarını şeffaf mantık kurallarıyla birleştirir; tek bir nihai rezonans vektörüne (`ResonanceVector`) sentezler. | `KeyReport` |

---

## 3. Uzman Ajan Sürüsü (`agent_core/agents/` & `agent_core/shadow/`)

`PinealExecutor` durum makinesi, profili 360° derinlikte işlemek için uzmanlaşmış ajan zincirini devreye sokar:

| Ajan | Dosya | Görevi ve Sorumluluğu |
|---|---|---|
| **PassionMapper** | `passion_mapper.py` | Hedefin neşe, yaratıcılık, akış anları (`flow_triggers`) ve entelektüel tutku alanlarını somut alıntılarla haritalandırır. |
| **FrictionDetector** | `friction_detector.py` | Hedefin sınırlarını, hassasiyetlerini, tükenmişlik sinyallerini ve mesafeli durduğu kırmızı çizgileri tespit eder. |
| **CognitiveProfiler** | `cognitive_profiler.py` | Hedefin iletişim tonunu, anlamsal karmaşıklık seviyesini ve mizah üslubunu modeller. |
| **DepthAnalyst** | `depth_analyst.py` | 4 kanallı psikodinamik gerilim matrisini ve kırılmaları okuyarak gerçeklik indeksini (`reality_index`) ve çelişkileri raporlar. |
| **ResonanceCalculator** | `resonance_calculator.py` | Kullanıcı frekansı ile hedef profil arasındaki uyumu **saf numpy vektör matematiğiyle** hesaplar (Eşik: <0.70 ise `halted_frequency`). |
| **ResonanceSynthesizer** | `resonance_synthesizer.py` | Manipülasyon içermeyen, ortak tutkulara ve karşılıklı saygıya dayanan sahici bir ilk temas köprüsü (`AuthenticBridge`) kurar. |
| **HumanBehavior** | `human_behavior.py` | OpenCV ile görsel kompozisyon, omuz gerilimi ve arka plan boşluğunu deterministik gözlem olarak derler. |
| **OSINTInvestigator** | `osint_investigator.py` | Dijital ayak izi skorunu, bağlı platformları ve sızıntı kayıtlarını analiz eder. |
| **AuthenticityAuditor** | `authenticity_auditor.py` | Görsel manipülasyon, sahnelenmiş/kurgu içerik ve estetik yapaylık derecesini denetler. |
| **PatternInterrupt** | `pattern_interrupt.py` | Diyalog ağaçları (agresif, savunmacı, ilgili) ve kutsal kural ihlal skorunu hesaplar. |
| **MirrorOfTruth** | `mirror_truth.py` | Kullanıcının kendi öz frekansını ve yüzey personası arasındaki uyumu modeller. |
| **ShadowExecutor** | `shadow/shadow_executor.py` | Telafi ve kırılma indekslerini doğrudan taktik strateji vektörlerine (`mirroring`, `alliance`, `thrill`) dönüştürür. |
| **LilithGrowth** | `lilith_growth.py` | Matematiksel güvenlik katmanıyla donatılmış büyüme ve nöro-mimari analiz ajanı. |
| **InterpreterAgent** | `interpreter_agent.py` | Taktik kod üretimi ve adli script yürütme ajanı. |
| **DialogueManager** | `chat/dialogue_manager.py` | İstemci ile yürütülen çok turlu diyalog bağlamını yönetir. |

---

## 4. Dört Sütunlu Psikodinamik Derinlik Motoru

Statik sözlükler ve naif kelime sayma mantıkları tamamen çöpe atılmıştır. Sistem insanı aşağıdaki 4 matematiksel sütunla analiz eder:

### Sütun 1: Denetimsiz Semantik Kümeleme (`agent_core/services/theme_cluster.py`)
- **Yöntem:** Karakter 3-gram TF vektörleri, kosinüs benzerliği ($\tau = 0.30$) ve union-find kümeleme.
- **Dinamik $K$:** Önceden tanımlı tema listesi yoktur; tema sayısı veriden doğar.
- **Metrikler:** En büyük küme payından **Kompülsif Tekrar Skoru (`repetition_score`)** ve izole tekil sapmalardan **İzole Anomali Sayısı (`isolated_anomaly_count`)** üretilir.

### Sütun 2: Durum Yörüngesi $S(t)$ ve Faz Kırılması (`agent_core/services/timing_forensics.py`)
- Gönderiler zaman fonksiyonuna dizilir ($t_0 \to t_N$).
- Seri simetrik iki yarıya bölünerek gün-bölümü entropisi ve aralık varyansı ($gap$) karşılaştırılır.
- Entropi sıçramaları (`entropy_jump`) ve varyans kaymaları (`variance_shift`) üzerinden profilin hayatındaki **Faz Kırılma Noktaları (Phase Ruptures)** tespit edilir.

### Sütun 3: 4 Kanallı Çapraz Gerilim Matrisi (`agent_core/services/psychodynamic_depth.py`)
Her kanal için Şiddet ($I$), Tutarlılık ($Coh$) ve Bütünlük ($C$) hesaplanır:
- **Kanal 1 (Beyan):** Metin ve biyografi
- **Kanal 2 (Sahneleme):** Görseller, format entropisi, nesne çeşitliliği
- **Kanal 3 (Biyolojik Ritim):** Zaman damgaları, gece payı, yörünge kırılmaları
- **Kanal 4 (Sosyal Metrik):** Takip/takipçi oranı, etkileşim oranı (ER)

Kanallar arası gerilim:
$$T[i][j] = |I_i - I_j| \times \min(C_i, C_j)$$
Buradan yapısal **Telafi Katsayısı (`compensation_index`)** ve **Reaksiyon Oluşturma Katsayısı (`reaction_formation_index`)** üretilir.

### Sütun 4: Bayesian Dinamik Epistemik Kapı
- `if not text: halt` katliamı silinmiştir.
- $w_i = C_i / \sum C$ formülü ile çalışır.
- Profilde metin yoksa $w_{\text{declaration}} = 0$ olur ve tüm epistemik ağırlık Görsel ve Zamansal kanallara aktarılır ($w_{\text{vis}} + w_{\text{temp}} = 1.0$). Sistem asla kör duruşa geçmez.

---

## 5. Adli OSINT ve Zenginleştirme Altyapısı (`agent_core/services/`)

Pineal, hedef hakkındaki verileri toplamak için endüstri standardı adli araçları barındırır:

| Servis | Dosya | Açıklama |
|---|---|---|
| **Ghost Scraper** | `scraper/instagram_ghost.py` | Playwright tabanlı gizli tarayıcı. `/p/` ve `/reel/` URL'lerini, video bağlantılarını, post türlerini ve $t_0 \to t_N$ kronolojik zaman damgalarını (`taken_at`) çeker. |
| **Maigret Scanner** | `services/maigret_scanner.py` | 3000'den fazla sosyal ağ ve platformda kullanıcı adının izini sürer. |
| **Holehe Scanner** | `services/holehe_scanner.py` | E-posta ve telefon üzerinden şifre sıfırlama uçlarını kullanarak hesap tespiti yapar. |
| **Socid Enricher** | `services/socid_enricher.py` | Google/Telegram/Instagram hesap ID'leri üzerinden profil zenginleştirmesi sağlar. |
| **Search Engine** | `services/search_engine.py` | Tavily, SerpAPI ve Exa API'lerini birleştiren üçlü web doğrulama motoru. |
| **Crawl Enricher** | `services/crawl_enricher.py` | `crawl4ai` destekli derin web sayfası kazıma motoru. |

---

## 6. Çoklu Sağlayıcı (14-Provider) Yönlendirme ve Kasa

Sistem tek bir sağlayıcıya bağımlı değildir; 16 anahtarlık yerel envanteri (`.pineal_vault.json` ve `.env`) doğrudan yönetir:

- **Resmi OpenAI Uyumlu Sağlayıcılar:** Google Gemini (`/v1beta/openai/`), DeepSeek (`api.deepseek.com/v1`), NVIDIA NIM (`integrate.api.nvidia.com/v1`).
- **Ücretsiz / Yüksek Hızlı Sağlayıcılar:** Groq (30 RPM, `gpt-oss-120b`, `llama-3.3-70b`), Cerebras (5 RPM, `gpt-oss-120b`).
- **Açık Ağırlıklı Sağlayıcılar:** Together AI, DeepInfra, Nous Research Portal (indirimli Sonnet ve Luna).
- **Ağ Geçitleri & OSINT:** OpenRouter, Tavily, SerpAPI, Exa AI, E2B Sandbox.
- **Kasa Ayrıştırma:** `.pineal_vault.json` içindeki iç içe `providers.{ad}.api_key` yapısı şemadan bağımsız güvenle okunur.
- **Fail-Closed Harcama Koruması:** `PINEAL_ALLOW_PAID_ESCALATION=1` ve `PINEAL_ALLOW_UNPRICED_MODELS=1` bayrakları operatör tarafından açıkça verilmedikçe bilinmeyen fiyatlı rotalara harcama yapılmaz.

---

## 7. Çift Katmanlı Bellek ve Aspasia Gerçekliği

- **Kanonik Bellek (`agent_core/services/canonical_memory.py`):**  
  Her görevin kanıt zinciri disk üzerinde `memory/<task_id>.json` dosyasında atomik ve değiştirilemez olarak saklanır. Veri tabanı çökmelerinden etkilenmez (SoT).
- **Semantik Bellek (`agent_core/services/hindsight_memory.py`):**  
  Geçmiş görevler ve profiller arasında vektörel/anlamsal sorgulama imkanı tanır (`PINEAL_MEMORY_ENGINE=hindsight`).
- **Aspasia Disk Köprüsü (`DiskMemoryBridge`):**  
  `task_executor` görevi tamamladığında derinlik verilerini `forensic_digest` mührüyle kanonik kanıta basar. Aspasia, sunucu yeniden başlasa veya RAM boşalsa bile diskteki bu mührü okur; boşta beklerken hayali ajan uydurmaz (`ROUTING-ADAY` vs `GÖZLEMLENEN` ayrımı korunur).

---

## 8. Kurulum ve Çalıştırma

### A) Windows (Tek Komutla Başlatma)
```bat
baslat.bat
```
Sanal ortamı kontrol eder, bağımlılıkları yükler, frontend derlemesini sağlar ve istasyonu `http://localhost:8000` adresinde ayağa kaldırır.

### B) Manuel Kurulum
```bash
# 1. Python bağımlılıkları
pip install -r requirements.txt
pip install -r requirements-osint.txt
python -m playwright install chromium

# 2. Frontend derleme
cd frontend
npm ci && npm run build
cd ..

# 3. Sunucuyu başlatma
python -m uvicorn backend.api:app --host 127.0.0.1 --port 8000
```
Geliştirme arayüzü: `http://localhost:5173` | Üretim: `http://localhost:8000`

---

## 9. Yapılandırma Sözlüğü (`.env` ve `.pineal_vault.json`)

| Anahtar / Değişken | Katman | Açıklama |
|---|---|---|
| `GEMINI_API_KEY` | Vision / Multimodal | Google Gemini 2.5/3.7 Flash resmi OpenAI uç noktası erişimi. |
| `DEEPSEEK_API_KEY` | Reasoning | DeepSeek V3 ve R1 doğrudan API çıkarımı. |
| `GROQ_API_KEY` | Hızlı / Ücretsiz | Groq 30 RPM ücretsiz katman (Llama 3.3, gpt-oss-120b). |
| `CEREBRAS_API_KEY` | Hızlı / Ücretsiz | Cerebras wafer-scale çıkarım motoru. |
| `NVIDIA_API_KEY` | Donanım Hızlandırma | NVIDIA NIM optimize çıkarım uçları. |
| `TOGETHER_API_KEY` | Açık Ağırlıklı | Together AI model havuzu. |
| `DEEPINFRA_API_KEY` | Açık Ağırlıklı | Düşük maliyetli açık ağırlıklı modeller. |
| `OPENROUTER_API_KEY` | Ağ Geçidi | Frontier modeller için genel gateway anahtarı. |
| `TAVILY_API_KEY` | OSINT Arama | LLM'ler için optimize olgusal web arama motoru. |
| `SERPAPI_API_KEY` | OSINT Arama | Google Arama ve ters görsel sorgu motoru. |
| `EXA_API_KEY` | OSINT Arama | Nöral ve semantik web arama motoru. |
| `E2B_API_KEY` | Sandbox | İzole kod yürütme kum havuzu. |
| `PINEAL_ALLOW_PAID_ESCALATION` | Politika | `1` iken ücretli rotalara geçişe izin verir. |
| `PINEAL_ALLOW_UNPRICED_MODELS` | Politika | `1` iken fiyatı katalogda olmayan doğrudan sağlayıcılara izin verir. |
| `PINEAL_POST_DETAIL_ENABLED` | Kazıyıcı | `1` iken gönderi detaylarına giderek zaman damgası ve beğeni çeker. |
| `PINEAL_POST_DETAIL_LIMIT` | Kazıyıcı | Detayı çekilecek maksimum post sayısı (Varsayılan: `12`). |

---

## 10. Test ve Doğrulama Disiplini

Sistem, sözleşmelerin bozulmasını önleyen **1.014 testlik** devasa bir test süitiyle korunmaktadır:
```bash
# Tüm test süitini çalıştır (1014 test):
pytest -q

# Yeni psikodinamik motor, kazıyıcı ve Aspasia derinlik testleri:
pytest tests/unit/test_gorev1_reel_video_chrono.py tests/unit/test_gorev2_depth_engine.py tests/unit/test_vault_providers_schema.py tests/unit/test_aspasia_depth_hukmu.py tests/unit/test_gorev2_artiklar.py -q
```
- **Sıfır Regresyon:** Her yeni geliştirme `comm -13` diferansiyel filtresinden geçirilerek 0 regresyon kanıtıyla repoya girer.
- **Mutasyon Testi:** Güvenlik kontrolleri bilerek bozulduğunda testlerin kırmızıya (`FAILED`) düştüğü kanıtlanmıştır.

---

## 11. Mimari Durum Notları

- **`rust_core/` Durumu:** FAZ 9 Karar B uyarınca şu an bağımsız derlenen deneysel bir bileşendir (`cargo test`). Ürün çalışma zamanına entegrasyonu (özellikle token tasarrufu için RTK entegrasyonu) yol haritasındadır.
- **Veri Gizliliği:** Kişisel veriler yalnızca yerel `memory/` dizininde saklanır; dış sunuculara telemetri veya profil sızdırılmaz. Sır değişkenler `redact_structure` filtresinden geçirilir.
- **Etik Çerçeve:** Pineal adli bir analiz istasyonudur; hiçbir platforma gizli/otomatik mesaj atmaz veya bot faaliyeti yürütmez.
