# PINEAL — FAZ-2 MÜHÜR RAPORU (2026-09-08)

FAZ-2 (ENFORCE free-only + canlı-ID katalog düzeltmeleri) tamamlandı. Aşağıdaki
kanıtlar mühür kriterlerinle birebir eşleşir; **mühürsüz FAZ-3 YOK** (vision /
Google direct ertelemesi dahil — bu fazda vision'a dokunulmadı).

## Commit & CI

- **SHA:** `2006f6968fdb5e8691f2918be812c34aac239289` (`2006f696`)
- **Branch:** `arena/01a07f2a-pineal-clean` (parent `f2b2c74f` = FAZ-1 mühürlü commit)
- **Mesaj:** `feat(routing): FAZ-2 ENFORCE free-only + canlı-ID katalog düzeltmeleri (Q1/Q2)`
- **Kapsam:** 12 dosya (+234/−119)
- **CI:** run `34199584703` → **success, 5/5 job** (android, rust-core, frontend, backend, smoke)
- **Unit suite:** `942 passed, 3 skipped` (FAZ-1'de 940/3; net +2 — FAZ-2 kilit testleri)
- **`aspasia/` diff vs FAZ-1:** **0** (dokunulmadı)
- **Gölgeler:** `python scripts/generate_routing_shadows.py --check` → **taze ✅**

---

## Kriter 1 — ROUTES düzeltmeleri canlı-birebir; dots SİLİNMİŞ

| Kayıt | Eski (prefix'siz) | Yeni (canlı-birebir) |
|---|---|---|
| nous free | `laguna-s-2.1:free` | `poolside/laguna-s-2.1:free` |
| nous free | `xs-2.1:free` | `poolside/laguna-xs-2.1:free` |
| nous free | `ling-3.0-flash-fin:free` | `inclusionai/ling-3.0-flash-fin:free` |
| nous free | `dots-3-note-preview:free` | **SİLİNDİ** (katalog + ROUTES + TASK_GROUPS + verify script) |

Aynalanan dosyalar: `config/provider_catalog.json`, `agent_core/services/final_routing_policy.py`
(ROUTES + TASK_GROUPS), `scripts/verify_openrouter_catalog.py` (`REQUIRED_NOUS_FREE` → 3 ID).

**git grep avı (RED varsa söyle — bulunamadı):**
```
$ git grep -ni "dots-3-note-preview" -- '*.py' '*.json' '*.js' '*.ts' '*.svelte'
(boş — yalnız CSS sınıfı route-dots ve "eski dots" yorumu kalır; model ID literal'i 0)
$ grep -rnE "(['\"])(laguna-s-2\.1:free|xs-2\.1:free|ling-3\.0-flash-fin:free)(@|\1)" ...
AV TEMIZ: prefix'siz YOK
```

Not: frontend svelte/RUNBOOK satırlarında görünen `laguna-s-2.1:free` kısa adı
`_short()`'tan üretilir (canonical ID'den türetilir; üretici `--check` yeşil).

## Kriter 2 — Zincire giren HER yeni ID izin listesinde

Simple tier bağlaması (sahip Q2) yalnız iki canlı-teyitli ID kullandı; ikisi de
katalog + ROUTES + MODEL_REGISTRY'de doğrulandı:

```
MODEL_REGISTRY["gpt_oss_120b"]    -> openai/gpt-oss-120b        (groq + cerebras direct free; ROUTES'te)
MODEL_REGISTRY["laguna_s_2_1_free"] -> poolside/laguna-s-2.1:free (nous direct free; ROUTES'te)
```

Bağlanan 4 simple zincir (hepsi `config/agent_tiers.json`'da `"tier": "simple"`):
`pattern_interrupt`, `passion_mapper`, `autonomous_verifier_extract`, `lilith_growth`
→ tek-tip `[openai/gpt-oss-120b, poolside/laguna-s-2.1:free]`.

`AGENT_CHAINS` **çıplak model-id şeması ve tüm imzalar DEĞİŞMEDİ**; yalnız dört
simple zincirin model içeriği değişti (onaylı istisna). RUNBOOK shadow tablosu
ve svelte satırları üreticiyle senkron (12 satır, deterministic).

## Kriter 3 — ENFORCE flipsi: aynı `_tier_route_decision`; diff minimal

FAZ-1'de mühürlenen saf karar kaynağı (`_tier_route_decision` / `_tier_variant_sort_key`)
**değişmedi**. FAZ-2 diff'i yalnız:

1. legacy OR bacagı: simple + `would_deny` → teklif edilmez (`legacy_denied`);
2. direct rota: simple + `would_deny` → `enforce_skip` (`continue`);
3. tüm taşımalar reddedildiyse `[]` döner — `[None]` yedeği ENFORCE'u bypass edemez;
4. heavy ailesi (heavy/vision/verify/unknown) İNDİRİMLİ direct kanala escalation
   env'siz izin (relax — Q1); liste-fiyat/frontier direct bugünkü firewall kapısında;
   OR-legacy liste engeli FAZ-3'e (yorumda açıkça yazılı).

Yeni karar mantığı YOK; denetim izi (`tier_audit_trail`) her karar için yazılmaya
devam eder (audit-only listelerde korundu).

**Davranış matrisi (kilitli):**

| Tier | Transport | FAZ-2 davranışı |
|---|---|---|
| simple | free (direct free / OR-free) | allow → teklif |
| simple | paid direct / OR-legacy (paid) | **HARD DENY** → teklif YOK; tek deny → `[]` |
| heavy/vision/verify | discounted direct (claude@nous $1.6/$8) | allow — escalation'sız (relax) |
| heavy/vision/verify | liste-fiyat direct / frontier | bugünkü paid firewall (escalation şart) |
| heavy/vision/verify | OR-legacy (liste fiyatı) | koşulsuz (FAZ-1 audit gibi; FAZ-3'te liste engeli) |
| unknown | her şey | heavy-eşdeğeri + `tier_unresolved` izi |

## Kriter 4 — Kilit testleri + MUTASYON kanıtları (kırmızı-görmeden yeşil YOK)

`tests/unit/test_tier_variant_gate.py` FAZ-2 bölümü (hepsi mevcut
`REAL_LLM_CALL_NOT_EXECUTED` kapısı altında mechanism-only — canlı çağrı yok):

| Test | Kilitlediği sözleşme |
|---|---|
| `test_t1_faz2_simple_chains_free_only_static_golden` | 4 simple zincir = golden `[gpt-oss-120b, laguna:free]` (exact equality) |
| `test_t1_faz2_simple_enforce_paid_returns_empty_ladder` | simple + claude → `[]`; escalation AÇIK olsa bile; audit izi 2×`would_deny simple_non_free` |
| `test_t1_faz2_simple_free_chain_models_yield_transports` | free zincir modelleri ENFORCE altında boş kalmaz (kırılma yok) |
| `test_t1_faz2_heavy_discounted_relax_without_escalation` | heavy + claude@nous → escalation'sız direct $1.6; OR-legacy izi `heavy_listed_gate` |

**Bu oturumda çalıştırılan mutasyonlar (kopyala-yapıştır değil):**

| Mutasyon | Kapı | Sonuç |
|---|---|---|
| M-C1-full: `passion_mapper` zincirine paid (`claude_sonnet_5`) eklendi | `test_t1_faz2_simple_chains_free_only_static_golden` | **KIRMIZI** (AssertionError) → geri alındı → YEŞİL |
| Enforce-bypass: `return []` koruması `pass`'e çevrildi (`[None]` yedeği geri geldi) | `test_t1_faz2_simple_enforce_paid_returns_empty_ladder` | **KIRMIZI** → geri alındı → YEŞİL |

Her ikisi de `/tmp/llm_gateway_faz2.bak`'ten geri alındı; restore sonrası
`git diff` temiz, 77 kilit testi yeşil.

## Kriter 5 — Mevcut test değişiklikleri (tek tek gerekçe)

| Dosya | Değişiklik | Gerekçe |
|---|---|---|
| `test_final_routing_policy.py` | free-ID pinleri prefix'li yazıma; dots kümeden düşürüldü | Kriter 1 ID düzeltmesinin aynası |
| `test_agent_model_policy.py` | `passion_mapper`/`extract` golden'ları yeni zincire | Q2 bağlama gerçeği (mühür onaylı) |
| `test_final_spec_compliance.py` | `test_paid_key_present_but_escalation_off_stays_off` → nous direct'e çevrildi | Q1 discounted-relax: heavy claude@nous artık escalation'sız çalışır (bilinçli davranış değişimi) |
| `test_routing_cost_firewall.py` | executor model ID'leri prefix'li yazıma | `ProviderCatalog.get_model` artık prefix'siz kaydı bulamaz (katalog gerçeği) |
| `test_tier_variant_gate.py` | FAZ-1 audit testleri FAZ-2 ENFORCE semantiğine güncellendi | FAZ-1 kırılma yasağı FAZ-1 ile sona erdi; hard-deny istenen davranış |
| `tests/conftest.py` | gateway contextvar izolasyon fixture'ı eklendi | (b″) kural 1 reset'siz tasarım + pytest thread-context paylaşımı → kalıntı sızıntısı (sıra-bağımlı kırılma ölçüldü: shadows sonrası paid-firewall testi kırmızı) |

Değişikliksiz kalan kilitler: `test_routing_shadows.py` (üretici `--check` ile
aynı kalıp — **değiştirilmedi**, gölge yenilendi), `test_response_cache.py`,
`test_routed_chat.py`, `test_multi_provider_routing.py`, `test_concurrent_spend_cap.py`.

## Kriter 6 — Rapor

Bu dosya. Mühür sırası 2. ajanda. Mühürsüz FAZ-3 yok.

## Bilinçli ertelemeler / notlar (FAZ-3'e)

- Vision `_tier_variant_sort_key` FAZ-1'de kilitliydi; FAZ-2'de **uygulanmadı**
  (Q3 — vision/Google direct FAZ-3'e; `vision_analyzer` zinciri değişmedi).
- Google-gemini kataloğu 0 model / cerebras suffix'siz `gpt-oss-120b` / prefix'siz
  xs+ling paid kümesindeki eski paid kayıtlar — FAZ-2 kapsamı dışı (yalnız
  görünür kırılmalar düzeltildi; rapor notu).
- `get_agent_chain` tiers.json'u cache'siz okuyor — FAZ-1'den bilinen perf notu
  (mühür engeli değildi; FAZ-2'de değişmedi).
- İkinci ajana soru: OR-legacy liste-fiyat engeli ve vision/verify indirimli
  relaksın sınırları FAZ-3 kapsam kararlarında netleştirilmeli.
