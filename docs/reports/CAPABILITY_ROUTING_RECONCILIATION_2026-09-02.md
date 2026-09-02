# Capability routing — nihai aday matrislerin uzlaştırma denetimi (2026-09-02)

**Tarih:** 2026-09-02 · **Hedef:** `AppleCurse/pineal-clean` @ `70c3831`
**Yöntem:** Kullanıcının yapıştırdığı 6+ routing taslağı/inihai matrisi birbirine ve mevcut koda bağlandı; kritik model iddiaları canlı web aramasıyla doğrulandı. Kod veya config değiştirilmedi — bu belge yalnız denetim + öneridir; uygulama ayrı onay ister.

> **Ek notu:** İletilen `FINAL-KARAR-MATRIX*.json` / `FINAL-KARAR-TABLO.pdf` dosyaları sandbox'a ulaşmadı (iki denemede de). Denetim, mesaj gövdesindeki tam metinler üzerinden yürütüldü. JSON'lar tablolardan farklıysa paylaşılması gerekir.

---

## 1. Yönetici özeti

1. Yapıştırılan metin **tek bir "nihai" matris değil, birbirleriyle çelişen en az 4 aday matris** içeriyor. En kritik çelişki: **FrictionDetector** dört farklı adayda dört farklı katmana konuyor (Sonnet 5 / DeepSeek V4 Flash / Groq gpt-oss-20b) — üstelik tüm taslakların ortak prensibi "Friction ucuz modele verilmez" dediği halde iki aday bunu ihlal ediyor.
2. Repoda zaten **uygulanmış** bir karar var: `docs/reports/CAPABILITY_ROUTING_DECISION_2026-09-02.md` + `llm_gateway.py` `AGENT_CHAINS`. Bu, adaylardan "Ortak ve doğru bulgular / nihai routing matrisi (karar)" taslağının birebir uygulanmış hâli.
3. Canlı doğrulama bu oturumda mümkün oldu ve reponun çekirdek model isimlerini **teyit etti**: `gemini-3.7-flash` (GA, $0.75/$3.75), `grok-4.6` (500K, $2/$6), `claude-sonnet-5` (GA; **$2/$10 fiyatı 10 Ağu 2026'da kalıcı yapıldı** — taslaklardaki "1 Eylül'de $3/$15'e döner" endişesi geçersiz), `deepseek-v4-flash`/`v4-pro` (1M, resmi API).
4. Kod↔belge drift'i tespit edildi (madde 5): karar belgesi "TIER_1 = gemini-3.7-flash" yazıyor; kod ve `.env.example` TIER_1 = `anthropic/claude-sonnet-5`.
5. `live_llm_gate.py:47` hakem varsayılanı `openai/gpt-5.6-sol-pro` — canlı kaynaklar `gpt-5.6-sol`'ü teyit ediyor; **`-sol-pro` soneki teyit edilemedi** (slug riski, yalnız E2E gate betiğini etkiler, env ile ezilebilir).

**Hüküm:** Yeni matris uygulanmasın. Mevcut uygulanan matris, adayların "çelişki-ayıklanmış ortak senteziyle" aynı ve canlı doğrulaması diğer adaylardan daha güçlü. Önerilen tek elle-tutulur değişiklikler madde 6'da.

---

## 2. Aday matris envanteri ve çelişki haritası

| Aday | Vision birincil | Friction | OSINT sentez | Verdict | Durum |
|---|---|---|---|---|---|
| A — "Ortak doğru bulgular / nihai (karar)" | gemini-3.7-flash | **claude-sonnet-5** | grok-4.6 | claude-sonnet-5 | = **REPO UYGULAMASI** |
| B — "nihai (çelişki ayıklı)" | Gemini Flash (runtime ID) | Sonnet 5 veya V4 Pro | grok-4.6 | Sonnet 5 veya grok-4.6 | A ile uyumlu (sınıf düzeyi) |
| C — "🔴 en kritik düzeltme" | gemini-3.7-flash | **deepseek-v4-flash** ⚠ | grok-4.6 → 4.20-multi | grok-4.6 | Prensip ihlali (friction ucuz); "Grok her yerde" temeli bench'siz |
| D — "Dürüst özet - 5 cümle" | gemini-3.5-flash (free) | **gpt-oss-20b (Groq)** ⚠ | grok-4.6 | qwen3.6-27b (Groq) | Prensip ihlali; extract=hüküm ayrımını sağlayıcı düzeyinde kırmıyor |
| E — "1. Dürüst Yönetici Özeti" (eski) | gemini-2.5-flash | llama-3.3-70b ⚠ (deprecate iddiası kendi metninde) | deepseek-reasoner ⚠ (artık V4-Flash thinking alias'ı) | deepseek-reasoner | Tarihi geçmiş |
| F — "Pineal Ajan Bazlı" (son büyük taslak) | gemini-3.5-flash | deepseek-v4-flash ⚠ | gemini-3.1-pro / grok-4.20 | gemini-3.1-pro | Kendisi "repoyu görmedim, diff'i sonra" diyor |

Ortak sağlam prensipler (tüm adaylarda aynı, kodda da mevcut): Vision SPOF yok · Friction ucuzda olmaz · OSINT koleksiyon LLM'siz · Extract ≠ hüküm · Free havuz omurga değil · Cookie/MITM/Kiro yok.

---

## 3. Canlı doğrulama tablosu (web, 2026-09-02)

| İddia | Sonuç | Kaynak |
|---|---|---|
| `gemini-3.7-flash` gerçek, GA, 1M ctx, multimodal-in, $0.75/$3.75 | ✅ Teyit (repo fiyatı canlı fiyatla birebir) | ai.google.dev/gemini-api/docs/latest-model; datacamp.com/blog/gemini-3-7-flash |
| `grok-4.6` gerçek, 500K, text+image in, $2/$6 (≥200k: $4/$12) | ✅ Teyit | x.ai/api; docs.x.ai/developers/pricing |
| `grok-4.20-*` / `grok-4.3` ailesi: 1M ctx, $1.25/$2.50 | ✅ Teyit (xAI fiyat tablosunda) | docs.x.ai/developers/pricing |
| `claude-sonnet-5` gerçek; **$2/$10 intro fiyatı 10 Ağu 2026'da KALICI yapıldı** ($3/$15 standardı yürürlükten kalktı) | ✅ Teyit | anthropic.com/news/claude-sonnet-5 (changelog edit Aug 10, 2026) |
| `deepseek-v4-flash` (public beta) / `deepseek-v4-pro` (GA), 1M ctx, 384K out; ayrıca deneysel `deepseek-v4-flash-vision-exp` | ✅ Teyit | chat-deep.ai/models/deepseek-v4 (DeepSeek API özetleri) |
| `gemini-3.5-flash` free tier (15 RPM / 1500 RPD; EU/UK/CH'de free yok) | ✅ Teyit — ama "3.7 varken birincili 3.5'e indirme" için sebep yok | ayautomate.com free-models sayfası |
| `gpt-5.6-sol/terra/luna` GA (9 Tem 2026), alias `gpt-5.6`→Sol; fiyatlar kaynaklara göre $5/$30 vb. | ✅ aile teyit; **`gpt-5.6-sol-pro` slug'ı teyit EDİLEMEDİ** | marktechpost.com 2026-07-09; mindstudio.ai blog |
| Qwen3.7-Plus / GLM-5.3-Flash / Nemotron 3 Ultra free / MiniMax M3 free / Kimi K2.6 | ⚠ Bu oturumda doğrulanmadı (arama bütçesi dışı bırakıldı) | — |
| `solar-pro4` / `ling-3.0-flash` OpenRouter'da live mı | ⚠ Doğrulanmadı (bilinçli dışarıda bırakıldı; registry'de /v1 uyumu için duruyorlar) | — |
| "X modeli daha az halüsinasyon yapar" sıralaması | ❌ Hiçbir kaynakta Pineal iş yükü için bağımsız kanıt yok — taslakların kendisi de bunu itiraf ediyor | — |

---

## 4. Mevcut kod ↔ aday matris diff (ajan bazında)

Kod: `llm_gateway.py:159-210` (`CHAINS`, `AGENT_CHAINS`, `TASK_CAPABILITIES`, `AGENT_CAPABILITIES`, `VISION_MODELS`), call-site wiring bu oturumda grep ile teyit edildi.

| Ajan | Kod (`AGENT_CHAINS`) | Adayların dediği | Hüküm |
|---|---|---|---|
| VisionAnalyzer | gemini-3.7-flash → grok-4.6 | A/B/C: aynı; D/F: 3.5-flash/Qwen3-VL | ✅ Kod doğru; SPOF kırık (yedek var). Qwen3-VL 3. yedek adayı — ÖNCE canlı OpenRouter doğrulaması şart |
| OSINT koleksiyon | LLM yok | Tüm adaylar: LLM yok | ✅ Uyumlu |
| OSINT sentez | grok-4.6 → deepseek-v4-pro | A/B/C/D: grok-4.6 birincil | ✅ Uyumlu. Opsiyonel iyileştirme: yedeğe `grok-4.20-multi-agent` (1M, $1.25/$2.50 — v4-pro'dan ucuz; xAI teyitli) |
| FrictionDetector | claude-sonnet-5 → deepseek-v4-pro | A/B: sonnet-5 ✓; C/F: v4-flash ⚠; D: gpt-oss-20b ⚠ | ✅ Kod, adayların kendi ortak prensibiyle uyumlu; C/D/F'nin ucuz önerileri reddedilmeli (adaylar bunu kendi içinde çelişerek söylüyor) |
| AutonomousVerifier extract | `autonomous_verifier_extract`: deepseek-v4-flash → gemini-3.7-flash | Tüm adaylar: ucuz/mekanik | ✅ Uyumlu |
| AutonomousVerifier hüküm | `autonomous_verifier`: claude-sonnet-5 → grok-4.6 | A/B: sonnet-5 ✓ | ✅ Uyumlu; extract ile sağlayıcı ayrımı kodda mevcut (deepseek vs anthropic/x-ai) |
| PassionMapper / CognitiveProfiler | claude-sonnet-5 → gemini-3.7-flash | A/B: aynı; C: gemini/grok birincil; F: sonnet-4-6 | ✅ Uyumlu. Sonnet 4.6 hâlâ var ama Sonnet 5 güncel nesil |
| ResonanceSynthesizer | claude-sonnet-5 → deepseek-v4-pro | A/B: aynı | ✅ Uyumlu |
| Aspasia | claude-sonnet-5 → gemini-3.7-flash | A/B: aynı; C: grok-4.6 birincil | ✅ Uyumlu |

---

## 5. Bu denetimin bulduğu iki yeni drift (kod ↔ belge)

### D-01 — Karar belgesi tier satırı kodla çelişiyor (LOW, dokümantasyon)

`CAPABILITY_ROUTING_DECISION_2026-09-02.md` şunu yazıyor: "Genel tier varsayılanları: **TIER_1 = gemini-3.7-flash**". Gerçek:
- `llm_gateway.py:157` → `TIER_1_MODEL` varsayılanı `anthropic/claude-sonnet-5`
- `.env.example:10` → `OPENROUTER_TIER_1_MODEL=anthropic/claude-sonnet-5`
- `README.md:34` → Tier-1 `anthropic/claude-sonnet-5`

Üç kaynak kodla uyumlu, belge tek başına çeliyor → **belge düzeltilmeli** (tek satır). Kod değişikliği GEREKMEZ.

### D-02 — E2E hakem slug'ı teyitsiz (LOW, E2E betiği)

`live_llm_gate.py:47`: `DEFAULT_JUDGE_MODEL = "openai/gpt-5.6-sol-pro"`. Canlı kaynaklar `gpt-5.6-sol`'ü teyit ediyor; `-sol-pro` sonekinde bir model bulgulanamadı. `MODEL_PRICING`'deki `$2/$10` kaydı da bu varsayımla beraber şüpheli (kaynaklarda Sol için $4/$20 veya $5/$30 geçiyor). Etki: yalnız E2E gate; üretim yolu değil; `OPENROUTER_JUDGE_MODEL` env'i ile ezilebilir. Öneri: canlı OpenRouter kataloğunda teyit edilmeden bu slug sabit kalmasın — ya teyit edilsin ya `-sol`'e çekilsin.

---

## 6. Önerilen karar (uygulama için ayrı onay bekler)

1. **Matris değişikliği yok.** Repo matrisi (aday A/B) hem adayların çelişki-ayıklanmış ortak paydası hem de canlı teyidi en güçlü set. C/D/F'nin cognitive-router değişiklikleri Pineal-bench kanıtı olmadan "Grok/Gemini her yere" taşıması yapılmamalı.
2. **D-01 belge düzeltmesi** (tek satır).
3. **D-02 slug teyidi** sonraki canlı-katalog koşusunda; o zamana dek env override notu.
4. Opsiyonel backlog (öncelik sırasıyla, hepsi canlı katalog teyidi ister):
   - OSINT sentez yedeği: `x-ai/grok-4.20-multi-agent` (1M ctx, $1.25/$2.50 — mevcut yedek v4-pro'dan ucuz ve teyitli).
   - Vision üçüncü yedek: Qwen3-VL — yalnız OpenRouter canlı kataloğunda görülürse.
   - Runtime model-ID çözümleme (karar belgesinin "bilinçli dışarıda bırakılanlar" maddesi): doğru yön, hâlâ açık iş.
   - Free havuz rotator'u: hardcode slug yok, `GET /api/v1/models` üzerinden — taslakların ortak doğru önerisi.
5. **Kullanıcının bölgesi (TR):** Gemini free tier'ın EU/UK/CH kısıtı kaynaklarda TR'yi kapsamıyor görünse de TR kullanılabilirliği bu denetimden teyit edilemedi — ücretsiz katmanın omurga olmaması kuralı zaten bunu önemsizleştiriyor.

---

## 7. Sınırlar (bu denetim neyi iddia ETMEZ)

- OpenRouter canlı kataloğuna gerçek anahtarla bakılmadı (`LIVE_LLM_E2E` kapısı kapalı kaldı); slug "live mı" soruları için `scripts/` veya canlı gate koşusu gerekli.
- Model kalite/uydurma oranlarına dair hiçbir iddia kabul veya reddedilmedi — kanıt yok.
- Fiyatlar 02.09.2026 web kaynaklarından; spend-guard tablosu ile canlı fiyatlar arasındaki fark operasyonel risktir (bilinen, belgelenmiş durum).
