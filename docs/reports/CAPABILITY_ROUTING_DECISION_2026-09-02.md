# Capability routing — karar matrisi (2026-09-02)

Kaynak: üç bağımsız piyasa/lab taramasının çelişki-ayıklanmış sentezi (kullanıcı
araştırma paketi, 2026-09-02). Bu belge yalnız **uygulanan** kararları ve
gerekçeyi sabitler; halüsinasyon/skor iddiası içermez.

> Not: Capability-routing altyapısı (UnifiedRouter ↔ gateway,
> `TASK_CAPABILITIES` / `AGENT_CAPABILITIES` / `capable_chain`) PR #52 ile
> main'e girdi. Bu değişiklik **o altyapının üstündeki model seçimini**
> (matrisi) uygular; altyapıyı yeniden yazmaz.

## Ajan → model matrisi (uygulanan)

| Ajan | Birincil | Yedek | Not |
|---|---|---|---|
| VisionAnalyzer | google/gemini-3.7-flash | x-ai/grok-4.6 | Vision tek slug'a kilitli değil |
| OSINTInvestigator (koleksiyon) | — LLM yok — | — | Değişmedi; ham veri LLM'e gitmez |
| OSINTInvestigator (sentez) | x-ai/grok-4.6 | deepseek/deepseek-v4-pro | Web/X search aracı ayrı iş |
| FrictionDetector | anthropic/claude-sonnet-5 | deepseek/deepseek-v4-pro | Ucuz/fast katmandan çıkarıldı |
| AutonomousVerifier (extract) | deepseek/deepseek-v4-flash | google/gemini-3.7-flash | Mekanik, ucuz kalsın |
| AutonomousVerifier (hüküm) | anthropic/claude-sonnet-5 | x-ai/grok-4.6 | Extract'tan farklı sağlayıcı |
| PassionMapper / CognitiveProfiler | anthropic/claude-sonnet-5 | google/gemini-3.7-flash | Üslup + sentez |
| ResonanceSynthesizer | anthropic/claude-sonnet-5 | deepseek/deepseek-v4-pro | Köprü kalitesi |
| Aspasia | anthropic/claude-sonnet-5 | google/gemini-3.7-flash | Persona + vision |

## Kurallar (bu kararın parçası)

- Verifier'da extract ve hüküm aynı model/sağlayıcıda olmaz — kod içinde iki
  ayrı isimli zincir (`autonomous_verifier_extract` ≠ `autonomous_verifier`).
- Free havuz (OpenRouter `:free`, Nemotron, MiniMax, Cerebras) yalnız son
  fallback; hiçbir ajanın birincili değil. Bu matrise dahil edilmedi.
- `solar-pro4`, `ling-3.0-flash`, `glm-5.2`, `grok-4-1-fast-*`: hiçbir
  varsayılan zincirde yok. `MODEL_REGISTRY` kayıtları yalnızca /v1 yüzey
  uyumluluğu için korunuyor.
- Genel tier varsayılanları: TIER_1 = gemini-3.7-flash, TIER_2 =
  deepseek-v4-flash (env ile override edilebilir).
- `VISION_MODELS` genişletildi: gemini-3.7-flash, claude-sonnet-5, grok-4.6.
  Böylece vision isteği metin-only birincil yerine vision'lı yedeğe düşer.
- Cookie / MITM / reverse-engineer / Kiro-proxy: yok.

## Bilinçli dışarıda bırakılanlar

- **Runtime model-ID çözümleme** (Gemini patch sürümünü `models.list()` ile
  çek, günlük yenile): doğru yön ama bu commit'in kapsamı değil; ayrı iş.
- Claude/Grok'un doğrudan sağlayıcı entegrasyonu: şimdilik OpenRouter
  slug'ları (`anthropic/*`, `x-ai/*`) kullanılıyor; mevcut yürütme yolu
  OpenAI-uyumlu sohbet protokolüyle sınırlı.
- Lang-smoke: MiniMax/GLM-5.3 JSON disiplini ölçülmedi — cheap pool'a
  birincil yazılmadı.

## Fiyat kayıtları (2026-09-02 lab/aggregator docs)

- anthropic/claude-sonnet-5: $2 / $10 (1M token)
- x-ai/grok-4.6: $2 / $6
- deepseek-v4-flash: ~$0.067 / $0.15 (mevcut kayıt korundu)
- google/gemini-3.7-flash: $0.75 / $3.75 (mevcut kayıt korundu)
