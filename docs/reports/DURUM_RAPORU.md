# DURUM RAPORU — "Ürün hazır" demeden önce kapanması gerekenler

**Tarih:** 2026-08-30
**Branch:** `arena/01a0505e-pineal-clean`
**Amaç:** "Ürün hazır" iddiasını üç kabul kapısına bağlayan hazırlık maddelerinin
**ne olduğu, hangisinin bu oturumda kanıtlandığı, hangisinin hâlâ dış onay/ortam
gerektirdiği** tek yerde toplamak. Bu rapor kendi içinde kanıt üretmez; her iddia
"koddan doğrulandı / statik analizle doğrulandı / bu ortamda doğrulanamadı"
etiketini taşır.

> Çerçeve: `[ŞİMDİ] 5 hazırlık maddesi → [3 KABUL KAPISI] → "dürüst ürün" diyebiliriz`.
> Üç kapı, dokümanlardan yeniden kurulmuştur: (1) canlı LLM uçtan uca kapısı
> (`live_llm_gate.py`), (2) dağıtım/deployment kanıtı (Docker), (3) OSINT
> gerçek-ağ taraması + dürüstlük kapısı. Hepsi `RUNBOOK.md`/`README.md` ile tutarlı.

---

## 1) Android neden kırmızı? + mimari sorusu — KISMI KAPANDI (neden bulundu)

### 1a. Mimari cevabı (koddan doğrulandı)
Mobil uygulama **bizim backend'e bağlanmıyor; Gemini'ye doğrudan, kendi başına
gidiyor.** Bu bir ince istemci değil, ayrı/paralel bir üründür.

- `android/app/src/main/java/com/example/pineal/engine/gemini/GeminiClient.kt`
  Retrofit tabanlıdır; `BASE_URL = "https://generativelanguage.googleapis.com/"`,
  yalnızca `v1beta/models/{gemini-3.1-pro-preview | gemini-1.5-flash}:generateContent`.
- Android tarafında **hiçbir** backend referansı yok: `grep` ile `localhost`,
  `127.0.0.1`, `10.0.2.2`, `:8000`, `/api/`, `PINEAL_TOKEN`, `X-API-Key`
  **bulunamadı**. Yani Svelte+FastAPI+Aspasia+6 damga ürünü ile Android
  (`com.aistudio.pineal.heretic`) aynı zinciri paylaşmıyor.
- `PinealAnalyzerEngine.kt` tek atımlık (single-shot) Gemini "deep inference" ile
  JSON üretip kendi Room DB'sine (`data/local/*`) yazıyor; `HolisticProfile`
  şeması backend'in `memory_models.py`'sinden **bağımsız, ayrı bir kopya.**

**Ürün kararı gerekli:** Android, backend'in kablosuz istemcisi mi olacak
(pipeline'ı oradan tüketecek) yoksa mevcut "Gemini Edge AI" bağımsız sürümü mü
kalacak? Bu netleşmeden "Android'i yeşile çekmek" tek başına anlamsızdır.

### 1b. Android'in kırmızı olmasının kök nedeni (statik analizle doğrulandı)
`android/app/src/main/java/com/example/pineal/engine/PinealAnalyzerEngine.kt:133-139`:

```kotlin
emit(PipelineEvent.TelemetryUpdate(TelemetryData(
    cacheHitRate = "N/A (Canlı Çıkarım)",
    cacheHits = 0,
    cacheHitRate = "N/A (Canlı Çıkarım)",   // 2. kez
    cacheHits = 0,                           // 2. kez
    llmCallsObserved = 1
)))
```

`TelemetryData` (`data/model/Models.kt:111-114`) `cacheHitRate` ve `cacheHits`
parametrelerini **birer kez** tanımlıyor. Aynı isimli argümanın iki kez verilmesi
Kotlin'de derleme hatasıdır → `gradle assembleDebug` ve dolayısıyla CI'daki
`android` işi **kırmızı** olur.

**Ek bulgular:**
- `GeminiClient.kt` model adları (`gemini-1.5-flash` — kullanımdan kaldırılmış,
  `gemini-3.1-pro-preview`) backend vision modelinden (`google/gemini-3.7-flash`)
  ayrışıyor; sürüm uyumsuzluğu ve maliyet/model teyidi gerektirir.
- `android/gradle/wrapper/` ve `android/gradlew` **repo'da yok**; CI `android`
  işi sırası `gradle wrapper` → `gradle lintDebug || true` → `gradle assembleDebug`
  diyor. Sisteme kurulu Gradle sürümüne ve erişime bağlı (repo'da kilitli wrapper
  olmadığı için sürüm kayması riski var).
- `debug.keystore` dosyası `rootDir` altında yok ama `signingConfigs.debug` bunu
  `if (file(...).exists())` ile şartlı yaptığı için tek başına kırılmaz.

**Doğrulama sınırı:** Bu sandbox'ta **JDK/Gradle yok** (`java`/`gradle` yok),
bu yüzden statik olarak kesinleştirdiğim tek derleme hatası budur; bunun dışındaki
tüm Kotlin'in gerçekten derlendiğini **burada doğrulayamıyorum.** "Yeşil" iddiası
için JDK+Android SDK'lı bir ortamda `assembleDebug` koşulmalıdır.

---

## 2) Dağıtım iddiasının bir kez provası — AÇIK (bu ortamda kanıtlanamadı)

- README/RUNBOOK: "Docker ile: `docker compose up --build`". Sandbox'ta
  `docker: command not found` (Docker sürücüsü yok). Yani `docker-compose.yml`
  **ve** `Dockerfile` var ama **çalıştırılamadı**.
- "Config var" ≠ "çalışıyor". Bu madde için iki seçenek: (a) Docker ayağa
  kaldırılıp gerçek smoke koşulur, ya da (b) dokümandaki iddia yumuşatılır
  (ör. "bu imaj best-effort; bu oturumda çalıştırılmadı"). Kullanıcının
  "config var ile çalışıyor ayrımı" kuralı gereği **henüz kapanmadı**.
- Bağıl not: backend Python bağımlılıkları (fastapi/pydantic/uvicorn/ruff/pytest)
  **bu sandbox'ta yüklü değil**, bu yüzden manuel `uvicorn` smoke'u da koşulmadı.

---

## 3) LLM kapısından ÖNCE: fiyat/promo kontrolü — AÇIK (ölçüm dış ortam ister)

- README/RUNBOOK: Tier-1 `upstage/solar-pro4` promo **2026-09-10'a kadar**;
  kullanıcı notu **11 Eylül 2026**. Bugün **2026-08-30** → **~11-12 gün** kaldı.
- Gerçek zincir (`agent_core/services/llm_gateway.py` → `CHAINS`):
  `depth solar-pro4 → glm-5.2 → deepseek-v4-pro` · `dialogue solar-pro4 → deepseek-v4-flash`
  · `fast ling-3.0-flash → deepseek-v4-flash`.
- Bu zincirin gerçek maliyetini ölçmek için `OPENROUTER_API_KEY` + `LIVE_LLM_E2E=1`
  ile canlı çağrı gerekir; burada **anahtar/hesap yok** → ölçülemedi.
- Öneri: canlı LLM testine bütçe sürmeden **önce** (a) harcama tavanı koy
  (`OPENROUTER_MAX_SPEND_USD`, `.env.example:11`, 0=kapalı; env tanımsızsa da 0),
  (b) promo sonrası fiyatla zincir maliyetini yeniden hesapla. Zemin kaymasın.

---

## 4) OSINT gerçek-ağ protokolü — AÇIK (karar listesi yazılmadan anahtar açılmaz)

- Deneysel OSINT kapıları `README`/`RUNBOOK` gereği **default KAPALI**:
  `ENABLE_MAIGRET=false`, `ENABLE_HOLEHE=false`, `ENABLE_CRAWL4AI=false`
  (`.env.example:48-57`). Kapalıyken uçlar dürüst `available:false` döner.
- Gerçek ağda tarama = gerçek hedef. Aşağıdaki karar listesi yazılmadan
  hiçbir anahtar açılmamalı:
  1. **Kim taranacak:** yalnız kendi hesapları / açıkça onaylanmış test hedefleri.
  2. **Hangi limitlerle:** küçük limit env'leri hazır (kapı alt değişkenleri
     `.env.example`'da); ilk koşu bu sınırlarda.
  3. **IP engellenme riski kabulü:** sağlayıcı/ev IP'si engellenebilir; bu
     kabul yazılı mı?
  4. **Etik çizgi:** tarama davranışı, kullanıcı/kişisel veri ve platform şartları;
     `INTEGRATION_PLAN.md`'deki "dürüstlük sözleşmesi" (mock/uydurma yasak,
     belge: "iz yok" iddiası yalnız sıfır-hata taramada).
- Bu liste tamamlanmadan OSINT kapısına gerçek-ağ koşusu **yapılmamalıdır**.

---

## 5) Raporun main'e taşınması — KISMI KAPANDI (bu oturumda push edildi)

- Not: Önceki oturumda bahsi geçen "local'deki `DURUM_RAPORU.md`" **bu checkout'ta
  ve git geçmişinde yok** (repo geneli ve `git ls-files` taramasında bulunamadı).
  Bu yüzden "mevcut local raporu pushlamak" mümkün değildi; bu dosya bu oturumun
  **doğrulanabilir bulgularından** yeniden yazıldı.
- Bu rapor `arena/01a0505e-pineal-clean` branch'ine commit edilip push edilmiş ve
  ana `main`'e **pull request** açılmıştır.

---

## Özet tablo

| # | Madde | Durum | Bu oturumda kanıt | Kalan |
|---|---|---|---|---|
| 1 | Android kırmızı + mimari | **Neden bulundu** | direkt-Gemini mimarisi; `PinealAnalyzerEngine.kt:133-139` mükerrer argüman derleme hatası | `assembleDebug` JDK'lı ortamda doğrulanmalı; ürün kararı: backend istemcisi mi, bağımsız mı |
| 2 | Docker provası | AÇIK | Docker yok → çalıştırılamadı | Docker smoke veya doküman iddiasını yumuşat |
| 3 | Fiyat/promo | AÇIK | promo bitişi ~2026-09-10/11, bugün 2026-08-30 | canlı anahtarla maliyet ölçümü + `OPENROUTER_MAX_SPEND_USD` |
| 4 | OSINT gerçek-ağ | AÇIK | kapılar default KAPALI | hedef/limit/risk/etik karar listesi |
| 5 | Raporu main'e taşı | **KAPANDI** | bu dosya oluşturulup push edildi + PR | PR onayı (`gh` PR açık) |

**Hüküm:** "ürün hazır" demeden önce listelenen beş hazırlık maddesinden
ikisinin nedeni/çıktısı bu oturumda netleşti (Android kök nedeni + mimari;
raporun main'e taşınması). Geri kalan üçü **dış ortam/karar gerektirir**
(Docker çalıştırma, canlı LLM maliyeti, OSINT hedef/limit kararı). Bu üçü
kapanınca üç kabul kapısına sırayla girilir ancak; o ana kadar "ürün hazır"
**en dürüst hüküm değildir.**
