# "FINAL KARAR — Hangi Model Nereden Avantajlı" tablosu denetimi (2026-09-02)

**Hedef:** `AppleCurse/pineal-clean` @ `70c3831` · **Yöntem:** Tablonun her satırı canlı web kaynaklarına bağlandı; repo kurallarıyla (`CAPABILITY_ROUTING_DECISION_2026-09-02.md`, `llm_gateway.py`, `live_llm_gate.py`) çapraz kontrol edildi. Kod/config değiştirilmedi.

---

## 1. Yönetici özeti

Bu tablo bu oturumun **üçüncü "nihai" kararı** ve önceki ikisiyle (ve kendi içindeki prensiplerle) çelişiyor. Satır-satır denetimde:

- **2 satır açıkça çürütüldü** (biri resmi deprecation sayfasıyla, biri fiyat kaynağıyla),
- **1 satır slug-bayat** (aile gerçek, yazılan slug katalogda yok),
- **4 satır teyitsiz** (kaynağı bulunamayan sağlayıcı/indirim iddiaları),
- **1 mimari ilke ihlali:** tablo omurgayı "free" yapıyor — kullanıcının önceki tüm taslaklarının ve repo karar belgesinin ortak kuralı ise "**free havuz hiçbir ajanın birincili olamaz**".

Hüküm: **Bu haliyle uygulanamaz.** Kullanılabilir parçalar madde 5'te.

---

## 2. Satır satır hüküm

| Tablodaki satır | Hüküm | Kanıt |
|---|---|---|
| GENEL CHAT → Groq `llama-3.3-70b-versatile` (14,400 RPD) | ❌ **ÇÜRÜTÜLDÜ — model ölü.** Groq resmi deprecation sayfası: shutdown **2026-08-16**; yerine `openai/gpt-oss-120b` veya `qwen/qwen3.6-27b`. Bugün 2026-09-02: satır mevcut olmayan modele bağlanıyor. | console.groq.com/docs/deprecations |
| VISION yüksek hacim → Google AI Studio `gemma-3-27b-it` (14,400 RPD) | ⚠️ **Kısmen.** Model gerçek ve multimodal; AI Studio'da free katmanı var. Ama **14,400 RPD rakamı teyit edilemedi** — Gemini ailesi free için kaynaklar 250–1,500 RPD veriyor; 14.4k Groq'un rakamı ve iki satırda aynı sayının tekrarı kopya-hatası şüphesi taşıyor. Ayrıca frontier vision'u free open modele indirgemek Pineal'in vision-kalite ilkesiyle çelişir. | tokenmix.ai/blog/gemini-api-free-tier-limits; precisionaiacademy.com |
| VISION+VIDEO → `stepfun/step-3.7-flash:free` "nous-research FREE" | ❌ **Teyitsiz/yanlış.** Canlı free listelerinde (2026-07/08 üç bağımsız liste) bu slug yok. StepFlash 3.7 için bulunan kayıt: "free değil, düşük maliyetli" (reddit r/openrouter, 2026-05-30). "nous-research"ün stepfun/upstage/meituan host ettiği iddiasına hiçbir kaynakta rastlanmadı. | teamday.ai (2026-08-03 liste); buldrr.com (2026-07); reddit |
| CODE hızlı → `openai/gpt-oss-120b` (Cerebras FREE + Groq) | ✅ **Makul.** Groq'da gpt-oss-120b production; Cerebras free-trial limitleri (5 RPM / 30K TPM / 1M TPD, 4 model) önceki taslakla tutarlı. Not: Pineal code-autocomplete ürünü değil — satır Pineal ajanlarına tercüme edilmeden anlamsız. | promptfoo.dev Groq kataloğu; Groq deprecations |
| CODE uzman → `poolside/laguna:free` 128K | ⚠️ **Slug bayat.** Free olan lagünler `laguna-s-2.1:free` ve `laguna-xs-2.1:free` (262K; 2026-08-03 canlı listede mevcut). `laguna-m.1:free` aynı hafta delist edilmiş. Çıplak `poolside/laguna:free` + 128K iddiası katalogda bulgulanmadı. | teamday.ai (2026-08-03); bit-flows.com |
| UZUN DOKÜMAN → `upstage/solar-pro4:free` 524K | ❌ **Teyitsiz.** Ağustos free listelerinde solar-pro4 yok (buna karşılık `inclusionai/ling-3.0-flash:free` **var** — repo registry'sinin tuttuğu slug yaşayan free olarak döndü). Ayrıca repo yorumu: solar/ling promosyonu **2026-09-10'da bitiyor** — "sonsuz free omurga" planı 8 gün ömürlü. | teamday.ai; llm_gateway.py:139-141 yorumu |
| REPO-SCALE → `meituan/longcat-2.0:free` 1M | ❌ **ÇÜRÜTÜLDÜ.** LongCat-2.0 gerçek (stealth "Owl Alpha" olarak listelenmiş) ama "ücretsiz değil" (reddit r/openrouter, 2026-05-30). `…:free` slug'ı hiçbir listede yok. | reddit r/openrouter |
| FRONTIER ucuz → `gpt-5.6-luna` Nous'ta $0.20/$1.20 | ✅ **HESAP-KANITLI (düzeltme, üçüncü tarama).** Kullanıcı bu kanalı satın aldığını ve fiyatı kendi panelinde gördüğünü bildirdi — hesap sahibinin paneli birinci elden kanıttır (ACCOUNT_VERIFIED). Ayrıca tutar notu: $0.20/$1.20, OpenAI'ın 30 Tem 2026 resmi %80 indirimiyle çakışıyor ($1/$6 → $0.20/$1.20); kanal fiyatı liste-üstü bir risk taşımıyor. | Kullanıcı hesabı (2026-09-02); aipricecompare.org; digitalapplied.com (30 Ağu 2026) |
| FRONTIER akıllı → `claude-sonnet-5` Nous'ta $1.60/$8 | ✅ **HESAP-KANITLI (düzeltme).** Kullanıcı Nous aboneliğini satın aldığını bildirdi; paneldeki $1.60/$8 birinci elden kanıt. Web arama indeksim bu ücretli kanalı kapsamıyor — bu, kanalın yokluğu anlamına GELMEZ; "bağımsız teyit edilemedi" yalnızca benim erişimimin sınırıydı. Tutarlılık notu: liste-altı frontier satışı piyasada olağan (örn. OpenRouter gpt-5.6-sol'ü listenin %50 altında satıyor) ve $1.60/$8, resmi $2/$10'un %20 altında makul bir bantta. | Kullanıcı hesabı (2026-09-02); openrouter.ai/openai/gpt-5.6-sol (piyasa bağlamı) |
| Kıyas tablosu: "Direkt Claude Opus 4.5 $15/$75", "Sonnet 4 $3/$15" | ❌ **Bayat kıyas.** Güncel Anthropic hattı: Opus 5 $5/$25, Sonnet 5 $2/$10 (kalıcı), Fable 5 $10/$50. Kıyas eski fiyatlarla kurulduğu için avantaj tablosu şişkin. | benchlm.ai (Eyl 2026); anthropic.com |
| Groq free 30 RPM / 14,400 RPD | ✅ gpt-oss ailesi için makul (Llama satırıyla karıştırılmamalı). | Groq docs |
| Cerebras 1M TPD free | ⚠️ Tutarlı ama **trial**; resmi duyuru limitlerin geçici düşürüldüğünü söylüyor — omurga yapılamaz. | Önceki taslak + bu tablo aynı rakam |
| NVIDIA NIM 40 RPM dev / AnyAPI 100k tok/gün | — Bu turda doğrulanmadı (ikincil önemde; ikisi de omurga adayı değil). | — |

---

## 3. Mimari çelişkiler (tablo ↔ oturumun kendi prensipleri ↔ repo)

1. **Free = birincil ihlali.** Repo karar belgesi: "Free havuz yalnız son fallback; hiçbir ajanın birincili değil." Önceki tüm taslaklar aynı kuralı tekrarlıyor. Bu tablo genel chat, vision, uzun doküman ve repo ölçeğini **doğrudan free'ye** bağlıyor.
2. **Ajan-eşlemesi yok.** Pineal'ın yönlendirmesi ajan-temelli (`AGENT_CHAINS`); bu tablo genel SaaS görevlerine (code autocomplete, repo-scale) yazılmış. Ajanlara tercüme edilirse FrictionDetector/Verifier yine ucuz katmana düşüyor — iki tur önce "kesin çıkar" denen hatanın geri dönüşü.
3. **Veri politikası.** Free katmanlar prompt'u eğitimde kullanabilir (Google free açıkça belgeliyor; OpenRouter bazı free modeller için retention uyarısı gösteriyor). Pineal kişisel profil/hassas OSINT verisi işliyor → `free ≠ güvenli`.
4. **Kadro çürümesi.** `:free` kadrosu haftalık delist görüyor (laguna-m.1 örneği; "going away" tarihleri). Repo kuralı zaten doğru yönü söylüyor: hardcode slug yok, `/api/v1/models`'ten çek. Bu tablo tam hardcode.
5. **Spend-guard uyumu.** Bu slug'ların hiçbiri `MODEL_PRICING`'de yok; guard bilinmeyen fiyatla `UNKNOWN_PRICING` düşürüyor. Yeni sağlayıcı/slug eklemek fiyat-kayıt işini de zorunlu kılar.

---

## 4. Entegrasyon gerçekleri (bu tablo koda dökülse ne gerekir?)

- Mevcut bulut yolu **yalnız OpenRouter** (`OPENROUTER_API_KEY`, OpenAI-uyumlu). Groq/Cerebras/NIM/AnyAPI doğrudan bağlanacaksa `UnifiedRouter`'a yeni `connections` (OpenAI-uyumlu endpoint'ler — düşük maliyet ama sıfır değil).
- OpenRouter `:free` slug'ları **sıfır yeni kodla** kullanılabilir — ama repo kuralı gereği runtime çekilmeli, zincirlere sabit yazılmamalı.
- Multi-provider eklenirse `model_allowlist`, health-check ve spend muhasebesi sağlayıcı-bazlı genişletilmeli (`provider_manager.py`).

---

## 5. Kabul edilebilir parçalar (repo kurallarına uygun hâli)

1. `openai/gpt-oss-20b/120b` (Groq) / gpt-oss-120b (Cerebras trial) → **fast/extract worker adayı** olarak fast_cheap havuzuna; birincil değil.
2. `:free` rotator havuzu adayları (hardcode etmeden, runtime katalogdan): `gemma-4-31b-it:free` (multimodal), `nemotron-3-ultra-550b-a55b:free` (1M), `laguna-s-2.1:free`/`xs-2.1:free` (code), `ling-3.0-flash:free`. Bunlar mevcut karar belgesinin "free yalnız son fallback" kuralına girer.
3. **Nous kanalı (düzeltme):** Kullanıcının satın aldığı, fiilen kullandığı kanal — hesap paneli birinci elden kanıttır ve hem Luna ($0.20/$1.20) hem Sonnet 5 ($1.60/$8) bu statüyle kabul edildi. Önceki revizyonlardaki "kanal adı yanlış/teyitsiz" ifadeleri geri alınmıştır: sandbox'tan doğrudan ağ erişimi yok, web arama indeksi ücretli Nous yüzeyini kapsamıyor; bu bir erişim sınırıydı, varlık hükmü değildi. Katalog-teyitli nihaî kanıt için `scripts/verify_nous_catalog.py` kullanıcı makinesinde `NOUS_API_KEY` ile koşulur.
4. **D-02 bağlantısı:** Repo `MODEL_PRICING`'deki `openai/gpt-5.6-sol-pro: $2/$10` değerinin OpenRouter'daki `gpt-5.6-sol` fiyatı ($2/$10) ile birebir örtüştüğü görüldü — fiyat gerçekçi, **slug soneki (`-pro`) hâlâ teyitsiz** ve canlı katalog kontrolünü bekliyor.

---

## 6. Karar aygıtı (bu tartışmayı bitiren komut)

Bu oturum sandbox'tan doğrudan dış ağa çıkamıyor (TLS engelli). Slug çekişmelerini kalıcı bitirmek için depoya `scripts/verify_openrouter_catalog.py` eklendi — anahtar gerektirmez (katalog ucu açık), kendi makinenizde 10 saniyede çalışır:

```bash
python3 scripts/verify_openrouter_catalog.py        # ✅/❌ tablo + canlı :free kadrosu
python3 scripts/verify_openrouter_catalog.py --json # CI'a bağlanabilir (omurga slug'ı yoksa exit 1)
```

Çıktıyı yapıştırırsanız: solar-pro4/longcat/laguna/step-flash/sol-pro sorularının hepsi aynı gün **kaynakta** çözülür; bir sonraki "final" matris ancak o çıktı üstüne yazılmalı.

---

## 7. Bu denetimin iddia etmedikleri

- Groq/Cerebras/NIM/AnyAPI'nin kota sayfaları bu turda tek tek açılmadı (ikincil omurga dışı iddialar).
- `:free` modellerin Pineal görev kalitesi bilinmiyor — bench yok; "deneme/fallback" sınırlaması bu yüzden.
- Sağlayıcı indirim kanallarının ToS uyumu (kullanım hakları, veri retention) değerlendirilmedi; teyit edilirse ayrı kontrol gerekir.
