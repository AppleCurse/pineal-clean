# PINEAL — UÇTAN UCA AKIŞ RÖNTGENİ (1. AŞAMA TEŞHİS RAPORU)

**Tarih:** 2026-09-21 · **HEAD:** `2edc9bb` (main) · **Çalışma dalı:** `arena/01a0c190-pineal-clean`
**Kapsam:** Beş kritik geçiş noktası, kod + çalıştırma kanıtı. **Hiçbir üretim kodu değiştirilmedi.**
**Ölçüm aracı:** `scripts/flow_roentgen.py` (bu raporla birlikte repoda; canlı LLM çağrısı yapmaz,
üretim belleğine yazmaz, tüm durumu geçici dizine kurar).

```bash
python scripts/flow_roentgen.py --mode all --out /tmp/rontgen.json
```

**Ortam doğrulaması:** `pytest tests/unit tests/integration` → **1037 passed, 4 skipped, 0 failed**.
Aşağıdaki bulguların hiçbirini test paketi görmüyor. Bazıları ise testlerle **kilitlenmiş** durumda
(§4.1/4.2, §6.3). Yeşil test ≠ doğru akış.

Ölçülen referans koşu (stub LLM, gerçek HTTP + gerçek WS):
`POST /api/initiate` → 200 · 69 WS çerçevesi · 0.15 s · 10 LLM çağrısı · 13 ajan koşusu ·
nihai durum `partially_completed` · mühür: `memory/op_…json`.

---

## 0. YÖNETİCİ ÖZETİ

| # | Öncelik | Bulgu | Kanıt |
|---|---|---|---|
| **B1** | **P0** | README'nin "tüm LLM trafiği yerel 9Router'dan geçer" iddiası **kod tarafından okunmuyor**: gateway `NINEROUTER_*` okur, README `PINEAL_LLM_*` yazar. README'yi uygulayan kurulum ya 401 alır ya da sessizce **openrouter.ai bulutuna** gider. | `llm_gateway.py:694-697` vs `README.md:176-177`; `PINEAL_LLM_BASE_URL` repo genelinde **0** Python referansı; `.env.example:10,25` |
| **B2** | **P0** | Timeout/iptal sonrası görev, odada **kalıcı hayalet** olarak kalır (`status=processing`); retention sweep onu **bilerek** silmez, `_active_tasks_full` onu "aktif" sayar → oda **kalıcı 503**. Kanıtlandı: 3 askıda görev → 3 hayalet → oda dolu, tek çıkış elle DELETE. | ölçüm: `flow_roentgen --mode ghost`; `api.py:1333,1414-1470,1483,1639` |
| **B3** | **P0** | **`resonance_synthesizer` üretimde hiç çalışmıyor**: `user_profile` **anahtar sözleşmesi** uyuşmuyor (`bio`/`posts` bekliyor, üretim `private_rituals/late_night_playlist/secret_envies` yazıyor) → her görevde erken dönüş → `halted`. Yani "sahici ilk temas mesajı" (`suggested_opening_message`) hiç üretilmiyor. Testler yanlış şekli kilitliyor. | ölçüm: LLM izinde synthesizer için **0 çağrı**; `api.py:1746-1755` · `resonance_synthesizer.py:20,33-40` · `tests/unit/test_resonance_synthesizer.py:14,39` |
| **B4** | **P1** | **3'lü jüri paneli ve çapraz jüri kuralı kodda YOK.** Üç jüri rotası yalnız `MODEL_REGISTRY` ismi; `autonomous_verifier` tek zincir çağırıyor ve zincir **Claude ile başlıyor** → Claude üretip Claude onaylıyor. README §91 bunun tersini vaat ediyor. | `autonomous_verifier.py:82,144` · `llm_gateway.py:354-356,445` · `agent_tiers.json` (jüri katmanı yok) · `README.md:91,116` |
| **B5** | **P1** | **7-Pillar çıktısı heba ediliyor.** Motorlar çalışıyor ve 8 alanı `status`'a yazıyor, ama zincire yalnız 7 anahtarlık **özet** giriyor; ham haritalar ne WS'ye ne mühre ulaşıyor. Tek tüketicisi olan `PillarFeed.svelte` hiçbir yerden import edilmiyor. | ölçüm: `frequency_map…pillar_bundle` → `snapshot=False result=False`; `task_executor.py:583-600`; `api.py:1624-1630,1937-1942` |
| **B6** | **P1** | Görev başına **2 adet denetim dışı Claude çağrısı**: `_calculate_authentic_vector` (`tier=1`, "asla kibar olma" promptu) ne `agent_runs`'ta ne kanıt zincirinde; LLM izinde `agent=None`. Mühürde iz yok, harcama var; uncertainty/upstream kapılarından da geçmiyor. | ölçüm: `AuthenticVectorResult ×2`, `agent=None`; `task_executor.py:773,777,1179-1202` |
| **B7** | **P1** | `pattern_interrupt` görev başına **iki kez** LLM'e gidiyor: bir kez rotada, bir kez `ShadowExecutor` içinde (mirror için [054] koruması var, pattern için yok). Çıktısı `input_data`'ya yazılmadığı için ikinci çağrı kaçınılmaz. | ölçüm: `GeneratedMessage ×2`; `shadow_executor.py:107,181`; `task_executor.py:~790` |
| **B8** | **P2** | **Bütçe matematiği tutmuyor:** tek ajanın en kötü LLM merdiveni `3 model × 3 deneme × 45s = 405s` > tüm görev timeout'u `300s`. Timeout `TimeoutError` olarak ayırt edilmez, görev **baştan** koşar (vision + OSINT yeniden). Model timeout'u 45s; "Groq 0.3s / Claude 1.4s / multimodal 2.7s" gecikmeleri *tek çağrı* için sığar, ama toplam bütçe görev seviyesinde kırılır. | `llm_gateway.py:702-703,2088,2483` · `api.py:1850-1861` |
| **B9** | **P2** | **Ajanlar arası körlük kısmi:** upstream bulgu bloğu yalnız `TargetPsycheProfiler` (3 lens ajanı) ve `resonance_synthesizer` tarafından okunuyor; 8 LLM kullanan ajan (mirror_truth, human_behavior, pattern_interrupt, depth_analyst, shadow_executor, autonomous_verifier, authenticity_auditor, osint) bloğu hiç görmüyor. Synthesizer'ın okuyucusu ise B3 yüzünden fiilen ölü. | ölçüm: `target_psyche_profiler` 3 çağrı / hepsi dolu; `resonance_synthesizer` 0 çağrı |
| **B10** | **P2** | UI'de **kurgu dolu** alanlar: statik `pineal-verifier-panel`, `pineal-osint-pipeline`, `local-numpy` adları kodda yok; başarısız derinlik/görsel/OSINT modalları "Kanıtlar incelendi / Fotoğraf analiz edildi / Temiz" diye yazıyor. ASPASIA sohbeti 4 kurgu mesajla açılıyor. | `UnifiedCompactPanel.svelte:136,141,145,808,813-814,820,825,253-256` + repo grep (yalnız docs/UI/test) |
| **B11** | **P2** | Aynı veri, **iki farklı serileştirme sözleşmesi**: mühür `default=str` ile yazar, WS `json.dumps` ile (kanıt zinciri `model_dump()` **python modunda**). Tarih/Enum sızarsa `_send_result` çerçevesi **sessizce düşer** (`_room_sender` yalnız `print` eder) → UI sonsuza dek "İŞLENİYOR". Bugün latent. | ölçüm: `datetime` → `TypeError`; `task_executor.py:324,1117` · `canonical_memory.py:153` · `api.py:1319,1952` |
| **B12** | **P3** | Ölü UI parçaları: `telemetryEvents` hiç render edilmiyor (sınırsız büyür), `NeuralTelemetryBoard` import edilip basılmıyor, `AgentOrchestrator.svelte` öksüz, `/api/tasks` görev geçmişi UI'de tüketilmiyor, hata çerçevesi "OPERASYON TAMAMLANDI" diye INFO yazılıyor. | `App.svelte:4,8,22-45,100,115,236` |

**Raporun dışı ama kritik — CI lint kapısı `main`'de KIRMIZI:** `ruff check .` (CI adımı
`.github/workflows/ci.yml:31-32`) **6 hata** veriyor ve hepsi `HEAD`'de, benim dosyalarımdan
bağımsız: `agent_core/agents/{passion_mapper,friction_detector,cognitive_profiler}.py` içinde
kullanılmayan `typing.Optional` ve `LLMGateway` importları (`F401`). Yani "yeşil test paketi"
tablosu eksik: testler geçiyor, **lint kapısı geçmiyor**. (Doğrulandı: `scripts/generate_routing_shadows.py`
sonrası `git diff` temiz → "routing shadows committed fresh" adımı geçer.)

---

## 1. SORU 1 — Olay akışı ve veri el sıkışmaları: tip/format uyuşmazlığı var mı?

**Cevap: Evet. Zincirin "boru" kısmı sağlam, "el sıkışma" kısmı delikli — ve en pahalı delik `user_profile`.**

### 1.1 Ölçülen akış (gerçek HTTP + gerçek WS, stub LLM)

```
POST /api/initiate → 200 {"status":"started","task_id":"op_20260921013650_50e415e0"}
WS: log×10 → snapshot(processing) → TaskStarted → snapshot → log → snapshot
    → TaskStarted → snapshot → log → result(partially_completed)
```

Planlanan: `mirror_truth, autonomous_verifier, human_behavior, passion_mapper, friction_detector,
cognitive_profiler, resonance_calc, pattern_interrupt, resonance_synthesizer`
Koşan (13): `osint_investigator, pineal_7pillar, mirror_truth, autonomous_verifier, human_behavior,
passion_mapper, friction_detector, cognitive_profiler, resonance_calc, pattern_interrupt,
resonance_synthesizer, depth_analyst, shadow_executor`

`status=partially_completed`; 2 ajan halt: `autonomous_verifier`, `resonance_synthesizer`
(ikisi de aynı kapıdan: `reason="Kaynak verisi kullanılamıyor; fallback sonuç kabul edilmedi."`,
`uncertainty_engine.py:248-255`).

### 1.2 ★ En pahalı el sıkışma: `user_profile` anahtar sözleşmesi (B3)

Üretici — `backend/api.py:1746-1755`:

```python
"user_profile": {"private_rituals": [...], "late_night_playlist": [...], "secret_envies": [...]}
```

Tüketiciler:

| Tüketici | Okuduğu anahtarlar | Sonuç |
|---|---|---|
| `mirror_truth.py:29-45` | `private_rituals` / `late_night_playlist` / `secret_envies` (+ `user_context` yedeği) | ✅ uyumlu |
| `resonance_calculator.py:270-284` | şemadan bağımsız terim toplayıcı | ✅ uyumlu |
| `cognitive_router.py:63-78` | `bio`/`posts` **veya** ritüel anahtarları | ✅ uyumlu |
| **`resonance_synthesizer.py:20,33-34`** | **`user_profile["bio"]`, `user_profile["posts"]`** | ❌ **üretimde asla dolu değil** |

Sonuç: `not user_bio and not user_posts` → `AuthenticBridge(confidence=0.0, data_confidence=False,
fallback_reason="user_context_unavailable")` → uncertainty kapısı reddediyor → `halted`.
Ölçüm bunu doğruluyor: **synthesizer için tek bir LLM çağrısı yok** ve upstream bloğu
(`:43`) hiç çalışmıyor. Yani ürünün nihai çıktısı olan **`suggested_opening_message`
(ilk temas mesajı) hiç üretilmiyor**; UI'de "AUTHENTIC BRIDGE" alanı boş kalır.

Testler bunu görmez çünkü sözleşmeyi ters kuruyor:
`tests/unit/test_resonance_synthesizer.py:14` → `"user_profile": {"bio": "tasarımcı"}`,
`:39` → `{"bio": ..., "posts": [...]}`. Üretim asla bu şekli göndermiyor.

> **Düzeltmenin yönü (karar sizin):** ya üretici `bio`/`posts` da taşımalı (kullanıcı profili
> gerçekten varsa), ya tüketici ritüel/playlist/envies anahtarlarını kabul etmeli. İkisi aynı
> anda yapılırsa iki sözleşme daha doğar — **tek bir sözleşme** seçilmeli ve sözleşme testi
> üreticinin gerçek payload'ıyla yazılmalı.

### 1.3 Ölü el sıkışma: `verifications`

`autonomous_verifier` sonucu `input_data["verifications"]`'a yazılıyor; **hiçbir tüketici yok**
(repo genelinde grep: 0 okuma). Doğrulama sonucu ne promptlara ne UI'ye ne mühre giriyor —
yalnız `agent_runs`/`evidence_chain` içinde duruyor. (B4 ile birleşince: jüri hem yok hem de
olsa çıktısı kullanılmayacak.)

### 1.4 7-Pillar: hesaplanıyor, özetleniyor, ham veri kayboluyor (B5)

`task_executor.py:583-588` 8 alanı (`frequency_map, seismos_events, void_map, strata_map,
gravity_map, pulse_map, key_matrix, pillar_bundle`) `status`'a yazıyor; `:590-600` zincire
**7 anahtarlık özet** (`frequency.status`, `event_count`, `void_top`, `dominant_attractor`,
`rhythm_signature`, `key_confidence`, `elapsed_ms`) giriyor. Ham çıktı yalnız süreç belleğinde:

- `_send_snapshot` payload'ında bu 8 alan **yok** (`api.py:1624-1630`),
- `broadcast_result` payload'ında **yok** (`api.py:1937-1942`),
- `CanonicalMemory._serialize` yalnız `evidence_chain` yazdığı için mühürde de **yok**.

Ölçüm: `[YOK] frequency_map … pillar_bundle` (snapshot=False, result=False).
Tek tüketici `frontend/src/components/PillarFeed.svelte` ve o da hiçbir yerden import edilmiyor.

`psychodynamic_depth` aynı kaderde (4 sütunlu derinlik motoru ne WS'de ne mühürde).

### 1.5 Mühür kapsamı README ile uyuşmuyor

`README.md:125`: "Her görevin **tüm girdileri, motor çıktısı, çağrılan modeller ve jüri onayları**
`memory/<task_id>.json` dosyasında … saklanır."
Gerçek: `canonical_memory._serialize` (`:145-153`) yalnız
`{task_id, last_updated, evidence[], confidence}` yazıyor.

| README iddiası | Kodda |
|---|---|
| tüm girdiler | ❌ yok (input_data mühre girmez) |
| motor çıktısı | ⚠️ kısmi (7-pillar **özeti** var, ham haritalar yok) |
| çağrılan modeller | ⚠️ `evidence_chain[].llm_calls` içinde var; ama `_calculate_authentic_vector` çağrıları **yok** (B6) |
| jüri onayları | ❌ jüri yok (B4) |

### 1.6 İki farklı `agent_runs` yazım yolu

`depth_analyst` ve `shadow_executor` `status.agent_runs`'a yazılıyor ama **kanıt zincirine
girmiyor**; `psychodynamic_depth`/`pineal_7pillar` zincire girip `agent_runs`'a kısmen giriyor.
Mühür yalnız zinciri taşıdığı için **derinlik raporu ve gölge profili mühürlenmiyor** —
"adli mühür" iddiası ile kapsam arasında fark var.

### 1.7 Doğrulanmış tip/format kusurları

1. **`reso.compatibility_score = 1.0000000000000002`** (ölçüldü). Alan 0.0–1.0 sözleşmesinde;
   `resonance_calculator.py:186` ham kosinüsü kırpmadan yazıyor (yalnız
   `frequency_match.vector_cosine` `round(...,3)`'ten geçiyor).
2. **`followers` / `following` asimetrisi** (`platform_registry.py:158-159`):
   `"following": ig_data.following_count` (None = ölçülmedi, korunur) ama
   `"followers": ig_data.follower_count or 0` → ölçülmemiş takipçi **ölçülmüş 0** olarak
   yazılıyor. `follower_audit` bunu "VERİ YETERSİZ"e çevirdiği için felaket değil, ama
   [024] düzeltmesi `followers` için uygulanmamış.
3. **`username` `@` ile taşınıyor** (`platform_registry.py:146`); `AutonomousVerifier`
   `lstrip('@')` ile sıyırıyor (`:104`), `HolisticProfile` düz kullanıyor → aynı alan üç yerde
   üç farklı normalizasyon varsayımıyla okunuyor.
4. **JSON sözleşmesi ikiliği (B11):** `_evidence_record` `result.model_dump()`
   (**python modu**, `task_executor.py:324`) → `broadcast_result` → `redact_structure`
   (bilinmeyen tipleri **olduğu gibi geçirir**, `security.py:397-403`) → `_send_result`
   `json.dumps(data)` (`api.py:1952`, **`default=` yok**). Mühür yolu ise
   `default=str` kullanıyor (`task_executor.py:1117`, `canonical_memory.py:153`).
   Tarih/Enum sızarsa `_room_sender` istisnayı yutup yalnız `print` ediyor (`api.py:1319`)
   → **result çerçevesi hiç gönderilmez**, UI `isProcessing`'de asılı kalır.
   (Ölçüm: `datetime` → `TypeError: Object of type datetime is not JSON serializable`.)
   Not: `_send_snapshot` tarafı güvenli çünkü alanları `model_dump(mode="json")` ile
   dönüştürüyor (`api.py:1604-1610`) — yani **iki farklı kural** zaten kodda.

### 1.8 Sağlam çıkan yerler (adil kayıt)

- `_new_task_id()` (`op_YYYYMMDDHHMMSS_<hex8>`) ↔ `CanonicalMemory._validate_task_id` uyumlu;
  `safe_child_path` ile path traversal kapalı; bozulma → `MemoryCorruptedError` + karantina.
- `_hash_evidence_result` kanonik SHA-256 (`sort_keys`, `ensure_ascii=False`, `default=str`).
- `InsufficientEvidenceError` exception olarak yükseliyor → `halted_evidence` terminal durumu.
- `memory_state` (EMPTY/READY/CORRUPTED) hem snapshot telemetrisine hem `/api/tasks`'a gidiyor.
- Upstream bulgu bloğu **gerçekten çalışıyor** (bkz. §1.9) — bu mimari ölü değil.

### 1.9 Düzeltme notu: "upstream bulgu kablolaması ölü" **yanlış** olurdu

İlk taramada "tüketici yok" sanmıştım; ölçüm aksini gösterdi. Gerçek durum **kısmi kablolama**:

| Yazan | Okuma noktası | Ölçüm |
|---|---|---|
| `task_executor._append_upstream_finding` (`:60-71`) | `target_psyche_profiler._extract_target_context` (`:34`) → `passion_mapper`, `friction_detector`, `cognitive_profiler` | **3 çağrı, üçünde de dolu** (415 karakter; `mirror_truth` + `osint_investigator` bulguları) |
| aynı | `resonance_synthesizer.py:43` | **0 çağrı** — erken dönüş (B3) yüzünden satıra hiç gelinmiyor |
| aynı | `mirror_truth`, `human_behavior`, `pattern_interrupt`, `depth_analyst`, `shadow_executor`, `autonomous_verifier`, `authenticity_auditor`, `osint_investigator`, `_calculate_authentic_vector` | **kör** (import yok) |

---

## 2. SORU 2 — `SearchEngine` doğrudan mı gidiyor, 9Router'a mı bağlanmalı?

**Cevap: Doğrudan gidiyor. Repoda `pineal-web-search` diye bir hat YOK — ne istemci, ne katalog
kaydı, ne preflight satırı. Üstelik "yerel 9Router" iddiası yapılandırma sözleşmesinde kırık.**

### 2.1 Ölçülen durum

- `search_engine.py:99,123,147` → `https://api.tavily.com/search`, `https://serpapi.com/search`,
  `https://api.exa.ai/search` (**doğrudan HTTPS**); anahtar yoksa `_search_duckduckgo`
  (HTML kazıma, `:171-192`). 9Router'a giden tek bir çağrı yok.
- `grep -rn "pineal-web-search"` → **0 sonuç**. `pineal-web-search`, `pineal-verifier-panel`,
  `pineal-osint-pipeline`, `local-numpy` yalnız `README.md`, `RUNBOOK.md`,
  `UnifiedCompactPanel.svelte`, `scripts/generate_routing_shadows.py`,
  `tests/unit/test_frontend_agent_model_contract.py` içinde geçiyor — **doküman + UI etiketi +
  test**, çalışan kod değil.
- `scripts/preflight_9router.py:38-46` yalnız 7 sohbet rotasını prob ediyor; web-search probu yok.

### 2.2 9Router gerçekten kullanılıyor mu? (B1 — P0)

```
llm_gateway.py:694  self.api_key = os.getenv("NINEROUTER_API_KEY") or os.getenv("OPENROUTER_API_KEY")
llm_gateway.py:696  self.openrouter_base_url = os.getenv("NINEROUTER_BASE_URL", os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
```

| Kaynak | Ne diyor | Kod uyumu |
|---|---|---|
| `README.md:67` | "tüm LLM iletişimini … 9Router hub'ı (`http://127.0.0.1:20128/v1`) üzerinden yürütür" | ❌ adres okunmuyor |
| `README.md:176-177` | `PINEAL_LLM_BASE_URL` / `PINEAL_LLM_API_KEY` | ❌ **0 Python referansı** |
| `.env.example:10,25` | `OPENROUTER_API_KEY`, `OPENROUTER_BASE_URL=https://openrouter.ai/api/v1` | ✅ kodla uyumlu, **bulut** |
| `.env.example` | `NINEROUTER_*` | ❌ **hiç yok** |

**Sonuç:** README'yi uygulayan operatör farkında olmadan bulut OpenRouter'a bağlanır (kişisel
veri + ücret dışarı). `OPENROUTER_API_KEY` de yoksa istekler 401 döner. Yerel hub yalnız
belgelenmemiş `NINEROUTER_BASE_URL` değişkeniyle devreye girer.

Üstelik UI'de **VIA etiketi yalan söylüyor**: `llm_gateway.py:1908-1919` üç yollu bir ayrım
yapıyor (`local` / `route.provider_id` / `openrouter`) ve ajan çağrıları hep routesuz olduğu
için `provider="openrouter"` yazılıyor; `_run_display_fields` (`api.py:1372-1373`) bunu
`via` olarak UI'ye taşıyor. Yani trafik yerel hub'a çevrilse bile ekran "openrouter" der.

**Preflight yanılgısı:** `preflight_9router.py:36` anahtarı
`PINEAL_LLM_API_KEY → NINEROUTER_API_KEY → OPENROUTER_API_KEY` sırasıyla okuyor; gateway ise
`PINEAL_LLM_API_KEY`'i hiç okumuyor. Preflight yeşil (`all_ok: true`, 2026-09-21 00:53) olabilir
ve runtime yine farklı kanaldan koşar.

### 2.3 9Router rotaları runtime'da fiilen ölü

`MODEL_REGISTRY`'de 10 `pineal_*` anahtarı tanımlı (`llm_gateway.py:349-359`), kod referansı:

| Anahtar | Kod referansı | Durum |
|---|---|---|
| `pineal_deep_reasoning`, `pineal_general_reasoning`, `pineal_fast_extract` | 1 (yalnız tanım) | hiçbir zincirde yok |
| `pineal_juror_google/claude/open` (`:354-356`) | 1 (yalnız tanım) | jüri yok (B4) |
| `pineal_truth_lane`, `pineal_intelligence_lane` | 1 (yalnız tanım) | hiç kullanılmıyor |
| `pineal_vision_lane` | 2 | yalnız `VISION_MODELS` kümesinde |

Gerçek trafik `AGENT_CHAINS` üzerinden OpenRouter model kimlikleriyle akıyor. Preflight bu
rotaları **canlı ölçüyor** (deep 1.13s, general 0.83s, fast-extract 0.34s, vision 1.01s,
juror-google 0.86s, juror-claude 1.44s, juror-open 0.12s, multimodal 2.74s, `all_ok: true`) ama
Pineal onları **çağırmıyor**. Yani "7 canlı hat" bir altyapı raporu, ürünün çalışma yolu değil.

### 2.4 Karar gerekiyor (A/B/C)

| Seçenek | Ne yapar | Risk |
|---|---|---|
| **A. 9Router'ı tek kanal yap** | `NINEROUTER_*`'ı `.env.example`'a yaz, `PINEAL_LLM_*` uyumluluk takma adı, README düzelt, provider etiketini gerçek kaynaktan türet | Model kimlikleri (`anthropic/claude-sonnet-5`, `deepseek/deepseek-v4-flash`) 9Router'da karşılanmazsa her çağrı düşer → önce eşleme tablosu |
| **B. 9Router'ı yalnız web-search için ekle** | `SearchEngine`'e `PINEAL_WEB_SEARCH_ROUTE` (varsayılan boş) ekle; doluysa Tavily/SerpAPI/Exa yerine 9Router `/v1/chat/completions` üzerinden `pineal-web-search` çağır, yanıtı aynı `SearchOutcome`'a çevir; boşsa bugünkü davranış birebir korunur | `SearchResult.source_url` attribution'ı LLM yanıtından çıkarılacak → atıf/quote disiplini zayıflar (kanıt zinciri "şu URL'den geldi" diyemez) |
| **C. İkisi de** | Önce B (izole, geri alınabilir), sonra A (eşleme tablosuyla) | — |

**Öneri: C, B ile başlanarak.** Bu bir mimari karar; onayınızı bekliyorum.

---

## 3. SORU 3 — Zaman aşımı ve kilitler gecikmeleri kaldırıyor mu?

**Cevap: `task_executor` içinde ne ajan başına zaman aşımı ne kuyruk var. Tek timeout görev
sarmalayıcısı (300s) ve bütçe matematiği tutmuyor; timeout sonrası odada kalıcı kilit oluşuyor.**

### 3.1 Ölçülen katmanlar

| Katman | Değer | Kaynak |
|---|---|---|
| Görev (tüm `execute_task`) | `PINEAL_TASK_TIMEOUT_SECONDS`, varsayılan **300s**, sınır 1–1800 | `api.py:1851,1859` |
| Görev denemesi | `PINEAL_TASK_MAX_ATTEMPTS`, varsayılan **3**, sınır 1–3 | `api.py:1850` |
| Kazıma denemesi | `PINEAL_SCRAPE_MAX_ATTEMPTS`, varsayılan 3, üstel bekleme | `api.py:1812` |
| Tek LLM isteği | `LLM_REQUEST_TIMEOUT_SECONDS`, **≤45s zorunlu tavan** | `llm_gateway.py:702-703` |
| LLM denemesi (model başına) | rota yoksa **3**, rota varsa **1** | `llm_gateway.py:2088,2483` |
| Zincir uzunluğu | 2–3 model | `llm_gateway.py:414-475` |
| WS gönderimi | 5s, sonra soket kopuyor | `api.py:1550,1557` |
| Görsel indirme | httpx 15s / görsel | `vision_analyzer.py:90,183` |
| **Ajan / adım başına** | **YOK** (`grep -n wait_for agent_core/task_executor.py` → boş) | `task_executor.py` |

**Kullanıcının sorduğu gecikmeler tek çağrı ölçeğinde rahat sığar:** Groq ~0.3s < 45s,
Claude 1.44s < 45s, multimodal 2.74s < 45s (+15s indirme). Sorun tek çağrıda değil, **kümülatif
bütçede**: 13 ajan × (1–3 model) seri koşar ve hiçbir ajan için üst sınır yoktur; bir ajan
`3 × 3 × 45s = 405s` harcayabilir, bu da 300s'lik görev sınırını tek başına aşar.
Ek olarak `_calculate_authentic_vector` (B6) ajan döngüsünün **içinde** serileşir ve 3 denemeli
`query_json` yolundan geçer — yani görünmez ek yük.

### 3.2 Timeout → tüm görevi baştan koşma (B8)

`api.py:1859-1861` `asyncio.wait_for(...)` ile görevi sarıyor; `TimeoutError` özel olarak
yakalanmadığı için genel `except Exception` yoluna düşüyor ve `run_mission` **tüm görevi**
yeniden deniyor: kazıma, görsel indirme, OSINT taraması, 10+ LLM çağrısı yeniden ödenir.
Kullanıcıya yalnız "SİSTEM PANİĞİ: MAKSİMUM DENEME AŞILDI" dışında timeout bilgisi gösterilmez.
Teorik üst sınır 3 × 300s = 900s ve 3× maliyet.

### 3.3 ★ Timeout sonrası kalıcı 503 kilidi (B2 — **kanıtlandı**)

`active_tasks` **yalnız** `_send_snapshot` tarafından yazılır (`api.py:1639`). Hiçbir kod yolu —
timeout, iptal, beklenmeyen istisna — bu kaydı terminal duruma geçirmiyor.
`_prune_room_stale_state` (`api.py:1414-1470`) yalnız **terminal** kayıtları düşürür ve bunu
yorumda bilinçli olarak yapıyor ("[AUDIT N1] … Aktif (processing) snapshot'lar ASLA sessizce
silinmez"). Kaçak kayıt `_active_tasks_full` (`:1483`) tarafından aktif sayıldığı için oda
tavana (`_ROOM_ACTIVE_TASKS_CAP`, `:1333`) ulaşınca **kalıcı 503** verir.

Ölçüm (`--mode ghost`, tavan 2'ye çekilmiş, 3 askıda görev, gerçek executor + gerçek timeout):

```
initiate #1: HTTP 200 op_…4708e177
initiate #2: HTTP 200 op_…7b61b588
initiate #3: HTTP 200 op_…0496cbb3
active_tasks (tavan 2):   3 kayıt, hepsi "processing"
retention sweep sonrası:  3 kayıt, hepsi "processing"      ← değişmedi
hayalet görevler:         [3 kayıt]
oda 'dolu' mu: sweep öncesi=True  sonrası=True             ← kalıcı 503
elle temizlik (DELETE tek görev): 200 → 2 kayıt kalır
```

Not: 3. `initiate` hâlâ 200 dönüyor çünkü doluluk kontrolü komut yolu için `_active_tasks_full`
değil ayrı bir eşik kullanıyor (`api.py:1970`); WS/snapshot yolu ise dolu görüyor — yani kilit
**tutarsız** biçimde davranıyor. Mevcut testler (`tests/audit/test_auditor_round2_findings.py:110`,
`tests/audit/test_round3_residue_findings.py:40,66,118`) hep **terminal** snapshot kurduğu için
bu yol kapsanmıyor.

### 3.4 Sağlam çıkan kilit hijyeni

- `CanonicalMemory._task_lock` bekleyen sayısı biterken girdiyi bırakıyor (`canonical_memory.py:64-79`).
- İptalde `execute_task` `finally` bloğu geçici görselleri siliyor (`task_executor.py:377-379`).
- `_close_room` sender + mission task'lerini birlikte iptal ediyor (lifespan çıkışı).
- WS kuyruğu: FIFO, 2000 kapasite, drop-oldest + `dropped_by_kind` sayacı,
  `telemetry.delivery.state="DEGRADED_QUEUE_OVERFLOW"` (testlerle kilitli).

---

## 4. SORU 4 — Çapraz jüri kuralı kod seviyesinde eksiksiz mi?

**Cevap: HAYIR. Kural kodda hiç yok — ne 3'lü panel, ne "üreten Claude jürilikten düşer" mantığı.**

### 4.1 Kanıt

1. `autonomous_verifier.py` yalnız iki zincir çağrısı yapıyor: `:82` iddia çıkarma,
   `:144` tek yargı. Fan-out, oylama, panel yok.
2. `llm_gateway.py:445` → `"autonomous_verifier": [claude_sonnet_5, grok_4_6]`. Birincil model
   **Claude**; kural "üreten Claude ise Claude jüriden çıkar" → kodda karşılığı yok.
3. `llm_gateway.py:354-356` → `pineal_juror_google/claude/open` **yalnız sözlükte**; hiçbir
   `AGENT_CHAINS`, `task_routing.json` veya `agent_tiers.json` girdisi bu rotalara değmiyor.
4. `config/agent_tiers.json` → 4 katman (heavy/vision/simple/verify), **jüri katmanı yok**;
   `autonomous_verifier` = `verify` (notu: "Search-gated (tavily/serpapi/exa keys required)").
5. `README.md:91` ("3 farklı model ailesinden … Temel Kural … Claude jüriden otomatik çıkarılır.
   Hiçbir model kendi yazdığı çıktıyı denetleyip onaylayamaz") ve `README.md:116`
   (`pineal-verifier-panel` / "(3 jüri)") → **doküman vaadi**, kod yok.
6. `UnifiedCompactPanel.svelte:136` aynı kurguyu **UI'ye** taşıyor;
   `scripts/generate_routing_shadows.py:81-88` bunu üretiyor, `ci.yml:35-38`
   ("Verify routing shadows committed fresh") tazeliğini zorluyor ve
   `tests/unit/test_frontend_agent_model_contract.py:81-90` kurguyu **testle kilitliyor**.
   Yani uydurma isim, CI tarafından korunuyor.
7. `aspasia/interface.py:730` dürüst: çağrı yoksa satırı `ROUTING-ADAY` yazıp
   "(henüz çağrı yok; bu satır plan, gerçekleşmiş karar değil)" ekliyor. Halüsinasyon
   Aspasia'da değil, **UI kartında ve README'de**.

### 4.2 Somut ölçüm

Stub koşusunda 10 LLM çağrısı: `MirrorReflection×1, AuthenticVectorResult×2,
DigitalColdReading×1, PassionProfile×1, FrictionProfile×1, CognitiveStyle×1,
GeneratedMessage×2, DepthReport×1`. **Jüri/panel adına çağrı: 0.**
`autonomous_verifier` bu koşuda arama sağlayıcısı olmadığı için `halted`; gerçek koşuda tek
zincir çağrısı yapar (3 değil).

### 4.3 Düzeltmenin şekli (öneri)

1. `AutonomousVerifier._verify_with_panel(...)`: `pineal-juror-google|claude|open` rotalarına
   `asyncio.gather` ile **paralel** sor.
2. `family_of(model)` eşlemesi + kural: üreten ajanın ailesi panelde varsa düşürülür;
   2 üyeyle de karar verilir, karar kuralı kanıta yazılır.
3. `VerifierReport`'a `jurors[]`, `dropped_juror`, `decision_rule` alanları ekle — yoksa yine
   "görünmez kural" olur.
4. Jüri rotaları `agent_tiers.json`'a **katman olarak** girmeli; UI etiketi
   `ROUTER_9_CANONICAL_MAP`'ten **türetilmeli**, elle yazılmamalı (ve test, kodla eşleşmeyi
   kontrol etmeli — bugün kurguyu kilitliyor).

---

## 5. SORU 5 — WebSocket & UI: kopukluk / boş kalan alan var mı?

**Cevap: Taşıma katmanı sağlam; içerik tarafında hem kopukluk hem boş alan hem kurgu var.**

### 5.1 WS taşıma katmanı (kopukluk yok)

FIFO oda kuyruğu (tek gönderici → sıra garantisi), 2000 kapasite + drop-oldest + `dropped_by_kind`,
soket başına 5s gönderim timeout'u (`api.py:1550,1557`), oda izolasyonu, retention sweep,
`test_ws_ordering` ile kilitli. **Kopukluk içerikte.**

### 5.2 Taşınmayan alanlar (gerçek "boş kalan alan")

| Alan | snapshot | result | Sonuç |
|---|---|---|---|
| `frequency_map`, `seismos_events`, `void_map`, `strata_map`, `gravity_map`, `pulse_map`, `key_matrix`, `pillar_bundle` | ❌ | ❌ | 7-Pillar UI'ye hiç ulaşmıyor (B5) |
| `psychodynamic_depth` | ❌ | ❌ | 4 sütunlu derinlik motoru görünmüyor |
| `holistic_profile` | ✅ | ❌ | yalnız snapshot'ta (kabul edilebilir) |
| `evidence_chain` | ❌ | ✅ | yalnız result'ta (kabul edilebilir) |

`backend/api.py` içinde `frequency_map` / `key_matrix` / `psychodynamic_depth` araması **0 sonuç**
veriyor. Buna karşılık `frontend/src/components/PillarFeed.svelte` hiçbir yerden import edilmiyor
→ kopukluk **iki taraflı**.

### 5.3 Model etiketi: statik kurgu vs. runtime gerçek

`UnifiedCompactPanel.svelte:664-669`:

```svelte
{@const run = runs[agent.id] || (agent.id === 'depth_analyst' ? runs['depth_forensics'] : null)}
{@const liveModel = run?.model || agent.primaryModel}
{@const liveVia   = run?.via   || agent.via}
```

- `run` varsa gerçek provenance gösterilir — **ama** provider etiketi `openrouter` sabit
  (B1/§2.2) ve `runs['depth_forensics']` **ölü anahtar** (backend `depth_analyst` yazıyor).
- `run` yoksa (görev öncesi, halt, sıra bekleyen ajan, `depth_analyst` için her hâlükârda)
  ekranda `pineal-verifier-panel` (`:136`), `local-numpy` (`:141`), `pineal-osint-pipeline`
  (`:145`) gibi **kodda çağrılmayan** adlar görünür.
- `:577-578` (aktif ajan çubuğu) aynı fallback'i `'auto'` / `'unified-router'` ile yapıyor.

### 5.4 Dürüstlük sorunu: başarısızlığı "başarı" gibi yazan alanlar

`UnifiedCompactPanel.svelte:808-825` — modallar `{:else}` dalında doğru metni ("henüz analiz
çalıştırılmadı") **zaten** içeriyor; sorun alan düzeyindeki fallback'lerde:

| Satır | Fallback | Gerçek |
|---|---|---|
| `:808` | `'Kanıtlar incelendi.'` | `depth_analyst` hata yolunda `{"available": false, "reason": "DEPTH_ANALYSIS_UNAVAILABLE"}` döndürüyor |
| `:813` | `aesthetic_style \|\| 'Klasik'` | vision çalışmadıysa `visual_evidence` None |
| `:814` | `'Fotoğraf analiz edildi.'` | görsel indirme (15s) hata verdiğinde de aynı metin |
| `:820` | `strategy \|\| 'Doğal profil'` | shadow `data_confidence=false` olabilir |
| `:825` | `associated_platforms \|\| 'Temiz'` | OSINT `data_confidence=false` → "veri yok" ≠ "olumsuz bulgu yok" |

Ek olarak `:253-256` ASPASIA sohbeti 4 **kurgu mesajla** açılıyor (uydurma "Aegean shell
entities" senaryosu) — reponun "sahte veri üretme" doktriniyle çelişiyor.

### 5.5 Ölü UI parçaları (B12)

| Parça | Durum |
|---|---|
| `App.svelte:100` `telemetryEvents.update(...)` | dizi **hiç render edilmiyor** → sınırsız büyüme |
| `App.svelte:8` `NeuralTelemetryBoard` | import edilmiş, şablonda **hiç basılmıyor** |
| `components/visualizers/AgentOrchestrator.svelte` | hiçbir yerden import edilmiyor |
| `App.svelte:22-45` `fetchTelemetry` / `fetchTasks` / `deleteTask` | tanımlı, **hiç çağrılmıyor**; `/api/tasks` görev geçmişi UI'de yok |
| Altbilgi "6 ADLİ DAMGA" | düğme sayısı **7** (follower, timing, depth, visual, shadow, osint, resonance) |
| `App.svelte:115` | hata çerçevesi geldiğinde "OPERASYON TAMAMLANDI: failed" **INFO** seviyesinde yazılıyor |
| `telemetry.delivery/lifecycle` | gönderiliyor ama UI'de **okuyucu yok** → kuyruk düşmesi görünmez |

### 5.6 Kopukluk YOK (doğrulananlar)

`follower_audit` (`verdict_code`, `data_completeness`), `timing_forensics` (`night_share`,
`peak_hour`, `median_drift_hours`), `resonance_calc` (`compatibility_score`, `red_flags`),
`depth_report`, `visual_evidence`, `shadow_profile`, `osint_footprint` alan adları backend
şemalarıyla **birebir** eşleşiyor; 7 adli damga düğmesi de bu alanlara bağlı.

---

## 6. ÖNERİLEN İŞ SIRASI

| Sıra | İş | Neden şimdi | Etki |
|---|---|---|---|
| 1 | **B3 `user_profile` sözleşmesi** — tek sözleşme seç, üretici/tüketici hizala, testi üretim payload'ıyla yaz | Ürünün ana çıktısı (ilk temas mesajı) hiç üretilmiyor | Küçük kod, büyük ürün etkisi |
| 2 | **B2 hayalet görev kilidi** — timeout/iptal/istisna yolunda `active_tasks` kaydını terminal yap (veya doluluk kontrolünü yaş sayaçlı yap) | Odayı kalıcı 503'e kilitliyor | Üretim kesintisi |
| 3 | **B1 yapılandırma sözleşmesi** — `NINEROUTER_*`'ı `.env.example`'a ekle, `PINEAL_LLM_*` takma adı, README düzelt, provider etiketini gerçek kaynaktan türet | Gizlilik + maliyet iddiası şu an yanlış | Güven + denetlenebilirlik |
| 4 | **B4 jüri paneli + çapraz jüri kuralı** (§2.4 kararına bağlı) | Ürünün anti-halüsinasyon çekirdeği | Orta kod, yüksek itibar |
| 5 | **B5 7-Pillar + `psychodynamic_depth` taşıma** (`_send_snapshot` + `broadcast_result` alanları, `PillarFeed` montajı) | Hesaplanan kanıt kullanıcıya ulaşmıyor | Görünür değer |
| 6 | **B6 `_calculate_authentic_vector` izlenebilirliği** (kayıt + kanıt zinciri) | Mühürde iz yok, harcama var | Denetim bütünlüğü |
| 7 | **B9 upstream bloğunu kör ajanlara da ver** + **B7 pattern çift çağrısını kaldır** | Ajanlar arası körlük ve 2× maliyet | Kalite + maliyet |
| 8 | **B8 ajan başına timeout + timeout'u ayrı terminal durum olarak raporla** | Retry fırtınası ve 3× maliyet | Kararlılık |
| 9 | **B10/B11/B12** UI dürüstlüğü, JSON sözleşmesini birleştir, ölü bileşenleri temizle | Görünen yalanlar, sessiz çerçeve kaybı | Güven |

> **Test uyarısı:** Bu işlerin çoğu mevcut yeşil testleri bozmadan yapılabilir ama **hiçbiri
> mevcut testlerle kanıtlanmıyor**. B4 için tersine, kurguyu kilitleyen bir test var
> (`test_frontend_agent_model_contract.py:81-90`); B3 için yanlış sözleşmeyi kilitleyen testler
> var (`test_resonance_synthesizer.py:14,39`). Her düzeltme kendi **sözleşme testiyle** ve
> üretim payload'ıyla gelmeli.

---

## 7. RAPORUN SINIRLARI (ne ölçüldü, ne ölçülmedi)

- **Ölçüldü:** gerçek FastAPI uygulaması, gerçek `/api/initiate`, gerçek WS akışı, gerçek
  executor, gerçek timeout, gerçek `active_tasks` durumu; LLM yanıtları stub'landı (canlı
  çağrı yok, maliyet 0). Şema dolgusu `_fill_schema` ile üretildi → **confidence değerleri
  sahte**, akış/tip davranışı gerçek.
- **Ölçülmedi:** canlı LLM ile uçtan uca koşu (Groq/Claude/9Router gecikmeleri rapordaki
  preflight ölçümlerinden alıntı), Playwright kazıma, Tauri/Android istemcileri, gerçek
  üretim `.env` değerleri.
- **Değiştirilmedi:** hiçbir üretim dosyası. Eklenen iki dosya: bu rapor +
  `scripts/flow_roentgen.py` (teşhis aracı, üretim kodundan bağımsız çalışır).

## 8. KANIT KOMUTLARI (yeniden üretilebilir)

```bash
# Ortam (PEP 668: sistem Python'a kurulum yasak)
.venv/bin/python -m pytest tests/unit tests/integration -q      # 1037 passed, 4 skipped
.venv/bin/python -m ruff check .                                 # 6 hata (main'de mevcut) → CI lint KIRMIZI
python scripts/generate_routing_shadows.py && git diff --exit-code  # temiz

# Ölçüm (canlı LLM yok, üretim belleğine yazmaz)
python scripts/flow_roentgen.py --mode all --out /tmp/rontgen.json

# Bu raporun başlıca statik izleri
grep -rn "pineal-web-search\|pineal-verifier-panel\|pineal-osint-pipeline\|local-numpy" --include=*.py .
grep -rn "PINEAL_LLM_BASE_URL" --include=*.py .                 # boş: README koda uymuyor
grep -rn "upstream_findings_block" --include=*.py .             # 2 tüketici (1'i ölü yolda)
grep -rn "wait_for" agent_core/task_executor.py                 # boş: ajan timeout'u yok
grep -rn "frequency_map\|psychodynamic_depth" backend/api.py     # boş: WS'ye taşınmıyor
grep -rn "user_profile" --include=*.py agent_core/ backend/ | grep -v tests
```
