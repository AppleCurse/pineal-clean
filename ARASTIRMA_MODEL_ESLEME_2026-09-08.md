# PINEAL — AJAN→MODEL→SAĞLAYICI ARAŞTIRMASI (2026-09-08)

**Yöntem:** Web'den 2026-09 itibarıyla canlı sağlayıcı katalogları/fiyatları toplandı;
repo'nun mevcut `AGENT_CHAINS`/`agent_tiers.json`/katalog/ROUTES yapısıyla çapraz eşleştirildi.
Fiyatlar $/1M token (input/output), **anlık görüntü** — sağlayıcı sayfasından doğrulanmalı
(CI canlı-kontrol adımı tam da bunun için var).

---

## 0. Canlı fiyat gerçeği (2026-09, kaynaklı)

| Model | OR (OpenRouter) | Doğrudan sağlayıcı | Not |
|---|---|---|---|
| `google/gemini-3.7-flash` | $0.75/$3.75 | **Google: $0.75/$3.75** (31.12.2026'ya kadar; sonra $1.50/$7.50). AI Studio **free tier'da $0** (5–15 RPM, veri eğitime gider) | repo ROUTES'u OR fiyatıyla birebir ✓; Google direkt = aynı fiyat ama aracısız + ücretsiz katman var |
| `openai/gpt-5.6-luna` | **$0.20/$1.20** (quality 77, pop#2; batch $0.10/$0.60) | — | repo'nun nous $0.20/$1.20 fiyatı OR ile birebir ✓ |
| `anthropic/claude-sonnet-5` | $2/$10 (promo 31.08.2026'da BİTTİ → $3/$15) | Anthropic $3/$15 (Sonnet 4.6 hattı) | repo list $2/$10 = promo dönemi; **nous $1.6/$8 = promo üstü %20** — promo bitince nous indirimi de geçersizleşir |
| `anthropic/claude-opus-5` | $5/$25 | $5/$25 (cache $0.50/$6.25) | en pahalı kademe; yalnız hakem/kritik |
| `x-ai/grok-4.6` | ~$2/$6 | xAI $2/$6 (cache $0.50) | repo zincirlerindeki grok-4.6 gerçek ✓; eski grok-4 ($3/$15) emekli |
| `x-ai/grok-4.3` | $1.25/$2.50 | xAI $1.25/$2.50 (1M ctx) | grok-4/4.1 ID'leri 4.3'e redirect oluyor |
| `deepseek/deepseek-v4-flash` | **$0.09/$0.18** (quality 54) | DeepSeek $0.14/$0.28 (cache $0.029) | **OR < birinci taraf!** repo MODEL_PRICING $0.0679/$0.168 ikisiyle de uyuşmuyor (bayat) |
| `z-ai/glm-5.3-flash` | **$0.08/$0.25** (quality 81, ctx 1.3M) | — | 2026'nın en yüksek kalite/$ oranı |
| `z-ai/glm-5.2` | $0.97/$3.04 (AA 74) | — | repo kataloğunda "emekli" — aslında canlı ve güçlü |
| `minimax/minimax-m3` | $0.30/$1.20 (multimodal, 1M ctx, quality 63) | — | görsel/video girdili ucuz multimodal |
| `nvidia/nemotron-3-ultra-550b` | ~$0.42/$2.61 + **`:free` rotası** | NVIDIA NIM | OR'da şu an popüler free |
| `openai/gpt-oss-120b` | OR'da ? | **Groq: free katman** (30 RPM/14.4K RPD) veya $0.15/$0.60; **Cerebras $0.35/$0.75** | repo free "verified" groq için doğru; **Cerebras free katmanı 21.07.2026'da KALDIRILDI** (yerine $5 tek seferlik trial, kart zorunlu) → repo katalog notu BAYAT |
| `openai/gpt-oss-20b` | — | Groq $0.075/$0.30 (en ucuz self-serve) | llama-3.1/3.3 70B Groq'ta Enterprise-only'ye taşındı |
| OR free havuzu | döner: DeepSeek/Mistral/Gemini **şu an $0 DEĞİL**; Poolside/Cohere/Nemotron free aktif | | repo'nun poolside `:free` kullanımı canlıyla uyumlu ✓ |
| OR komisyon | çıkarımda markup yok; **kredi yüklemede ~%5.5 ücret** (BYOK %5) | | ağır kullanımda doğrudan hesap = bu ücret yok |

Kaynaklar: [1](https://costgoat.com/pricing/openrouter), [2](https://www.usagepricing.com/blueprint/groq), [3](https://www.usagepricing.com/blueprint/cerebras), [4](https://ai.google.dev/gemini-api/docs/pricing), [5](https://ofox.ai/blog/openrouter-pricing-hidden-markup-breakdown-2026/), [6](https://pecollective.com/tools/anthropic-api-pricing/), [7](https://benchlm.ai/xai/api-pricing), [8](https://openrouter.ai/blog/insights/the-open-weight-models-that-matter-june-2026/), [9](https://tokenmix.ai/blog/gemini-api-pricing)

---

## 1. Ajan → önerilen beyin (başarı kriteri = görev fonksiyonu)

Sınıflar (kullanıcının kendi 4 kategorisi): **A**ğır mantık/psikodinamik · **V**ision/multimodal ·
**D**ata/ön-filtre (ucuz) · **O**turum/diyalog. Her ajanın kodda ne yaptığından (PASS-3) hareketle:

| Ajan (tier) | İşlev | Önerilen birincil beyin | Yedek | En avantajlı kaynak (2026-09) | Repo'da şu an | Delta |
|---|---|---|---|---|---|---|
| depth_analyst (heavy) | 4-kanal gerilim, reality_index, uzun metin | **claude-sonnet-5** | glm-5.2 | OR $2/$10 (veya Anthropic direkt) | deepseek-v4-pro→OR | model üstü aynen, kaynak: OR'da bırak (deepseek direct'i ROUTES'e alma — kalite düşük) |
| mirror_truth (heavy) | benlik vs persona nüansı | **claude-sonnet-5** | glm-5.2 | OR $2/$10 | claude→nous | ✓ (nous promo bitince fiyatı $2'ye çek) |
| resonance_synthesizer (heavy) | sahici ilk temas metni | **gpt-5.6-luna** | claude-sonnet-5 | OR $0.20/$1.20 | claude→nous | **luna'ya geç → ~10× ucuz, kalite 77** |
| aspasia (heavy) | üst akıl/orkestrasyon | **claude-sonnet-5** | grok-4.6 | OR $2/$10 | claude→nous | ✓ |
| autonomous_verifier (verify) | iddia↔kanıt denetimi | **claude-sonnet-5** | grok-4.3 | OR | claude→nous | ✓ |
| shadow_executor (heavy) | NLP+taktik vektör çıkarımı (JSON) | **deepseek-v4-flash** | glm-5.3-flash | OR $0.09/$0.18 | claude→nous | **~22× ucuz**; JSON'a uygun |
| friction_detector (heavy) | kırmızı çizgi/hassasiyet | **gemini-3.7-flash** | glm-5.3-flash | Google direkt free tier / $0.75 | claude→nous | farklılaş + ucuzla |
| cognitive_profiler (heavy) | ton/karmaşıklık/mizah | **gpt-oss-120b** | deepseek-v4-flash | Groq free | gemini→OR | **$0** |
| authenticity_auditor (heavy) | görsel manipülasyon | **gemini-3.7-flash (görsel)** | minimax-m3 | Google direkt (vision) | deepseek-flash→OR (VISION YOK!) | **metin modeli görsel analiz edemez — kritik** |
| vision_analyzer (vision) | görsel kanal özeti | **gemini-3.7-flash (görsel)** | minimax-m3 / grok-4.6 | Google direkt free/$0.75 | gemini→OR | kaynak: OR→Google direkt (aynı fiyat, aracısız; free tier var) |
| human_behavior (heavy) | OpenCV+kompozisyon | **gpt-oss-120b** | gemini flash | Groq free | claude→nous | $0 (OpenCV ön-işlem zaten görseli yapıyor) |
| osint_investigator (heavy) | ayak izi skoru (LLM'siz!) | — (kodda LLM çağırmıyor) | — | — | grok→OR (ölü zincir) | zinciri dormant işaretle; para harcanmasın |
| passion_mapper (simple) | alıntı+tutku çıkarımı | **gpt-oss-120b** | poolside/laguna:free | Groq free | groq free ✓ | ✓ |
| pattern_interrupt (simple) | diyalog ağacı/skorsal | **gpt-oss-120b** | laguna free | Groq free | groq free ✓ | ✓ |
| autonomous_verifier_extract (simple) | alan çıkarımı | **gpt-oss-120b** | laguna free | Groq free | ✓ | ✓ |
| lilith_growth (simple) | büyüme analizi | **gpt-oss-120b** | laguna free | Groq free | ✓ | ✓ |
| dialogue_manager (simple) | taktik mesaj üretimi | **gpt-oss-120b** | laguna free / glm-5.3-flash | Groq free | claude (paid) → **ENFORCE BOŞ** | kırık → free'e bağla |
| interpreter (simple) | kod üretimi | **gpt-oss-120b** (kod yetenekli) | glm-5.3-flash | Groq free | claude (paid) → **ENFORCE BOŞ** | kırık → free'e bağla |

---

## 2. Kaynak avantaj haritası (özet)

1. **Groq = bedava data-işçisi.** gpt-oss-20b/120b free katman (30 RPM); 4 basit ajan + cognitive + human_behavior burada $0 erir. 120B kalitesi "hamaliye/çıkarım" için yeterli; yetersizse zincirde sıradaki modele düşülür (zaten öyle çalışıyor).
2. **Google Gemini direkt = vision'ın gerçek adresi.** OR'da gemini $0.75/$3.75 ve **free değil**; Google'da aynı fiyat veya AI Studio free tier $0 (5–15 RPM). Vision ajanları OR'dan Google'a taşınınca (a) aracı yok (b) ücretsiz katman açılır (c) "429→backup→vertex" senaryon ancak DOĞRUDAN hesapta anlamlı — OR üzerinden backup/vertex imkânsız. **G1 kodu gerekiyor** (`llm_gateway.py:230` "rotasyon ayrı iş" diyor — o iş bu).
3. **DeepSeek V4 Flash ucuz JSON beyni — OR'dan al, direct'ten değil.** OR $0.09/$0.18 < DeepSeek birinci taraf $0.14/$0.28. Repo MODEL_PRICING'teki $0.0679/$0.168 **ikisine de uymuyor** (bayat) → düzelt.
4. **Luna %80 indirim ailesi repo'da ölü.** gpt-5.6-luna OR $0.20/$1.20 (quality 77): resonance_synthesizer gibi "kaliteli ama pahalı olmamalı" metin üreticileri için birebir. Katalog+ROUTES var, zincir yok → tek satırla ajan ataması.
5. **GLM-5.3-flash $0.08/$0.25 quality 81** → JSON/çıkarım için en yüksek kalite/$; şu an repo'da hiç yok. (repo "emekli" dediği glm-5.2 aslında canlı.)
6. **Cerebras "free verified" BAYAT** — 21.07.2026'da free katman kalktı ($5 trial, kart şart, 30 gün). Repo ROUTES'u cerebras'ı $0 free gösteriyor → canlıda ya hata ya fatura. **Groq free'i koru, Cerebras'ı paid ($0.35/$0.75) veya kaldır.**
7. **OR kredi ücreti ~%5.5** (BYOK %5). Doğrudan hesaplar (Google, Groq, xAI, Anthropic) ağır hacimde bu ücreti keser.
8. **Claude promo bitti (31.08.2026):** sonnet-5 $2/$10 → $3/$15. Nous "$1.6/$8 %20 indirim" iddiası promo dönemi fiyatına dayanıyordu; **nous indirimi canlıda doğrulanamıyor** (repo verify script'i yalnız OR+nous isimlerini yerel kontrol ediyor, canlı nous fiyatı yok) → ya OR'dan $2/$10 (şu anki gerçek) ya da Anthropic direkt.

---

## 3. Önerilen eylem paketi (repo değişikliği, onay bekliyor)

| Paket | Değişiklik | Kapsam |
|---|---|---|
| P1 (acil doğruluk) | Cerebras free→$0.35/$0.75 veya katalogdan düş; deepseek MODEL_PRICING güncelle; claude list fiyatı $2→$3 (promo bitti) notu | config/ROUTES + verify script sabitleri |
| P2 (ölü para) | dialogue_manager + interpreter zincirlerini free'e bağla (ENFORCE boş hatası kapanır); osint zincirini dormant işaretle | AGENT_CHAINS/agent_tiers |
| P3 (ucuz beyinler) | resonance_synthesizer→luna; shadow_executor→deepseek-v4-flash(OR); cognitive/human_behavior→gpt-oss-120b; friction→gemini-flash | AGENT_CHAINS |
| P4 (vision gerçek) | google-gemini'ye katalog modeli + Google direkt transport + 429→backup→vertex rotasyonu (G1 kodu) | llm_gateway + katalog + attestation |
| P5 (yeni fırsat) | glm-5.3-flash'ı katalog+ROUTES'e al, JSON ajanlarına yedek yap | katalog/ROUTES/zincir |

Not: P1–P3 config-only ve test kontratlarıyla kilitlenebilir; P4 yeni kod (en büyük); P5 yeni model kaydı + canlı doğrulama gerektirir (anahtar). Fiyatlar 2026-09-08 görüntüsüdür; uygulamadan önce sağlayıcı sayfası/CI canlı-kontrol ile teyit önerilir.
