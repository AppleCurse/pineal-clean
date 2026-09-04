# PINEAL — Routing Hardening Raporu (2026-09-04)

Kapsam: routing-doğrulama turunda bulunan O-1..O-4 gap'lerinin KAPATILMASI.
Yeni özellik/soyutlama YOK; mevcut tek routing beyni (final_routing_policy
ROUTES + llm_gateway zincir motoru) korundu. OpenRouter hub değil.

## Kapanış tablosu
| Gap | Durum | Uygulama | Kanıt |
|---|---|---|---|
| O-1 firewall yapılandırılmış saha | KAPALI | `ModelSubstitutionDeniedError(requested/actual)`; `query()` ve legacy `chat_completion` redlerinde TEK, yapılandırılmış call-log kaydı (`actual_model`/`requested_model` düz field; `route_key`+pricing merge korunur); interface TelemetryReader field-first okur, regex yalnız eski kayıtlar için fallback | test_routing_hardening::test_substitution_denial_carries_structured_fields + inline legacy proof (1 kayıt, actual='baska/model') |
| O-2 provider health (bounded) | KAPALI | yalnız-geçici hata streak breaker: eşik `PINEAL_PROVIDER_FAILURE_THRESHOLD` (3), cooldown `PINEAL_PROVIDER_COOLDOWN_SECONDS` (60), monotonic; blok `agent_route_variants` içinde tüketilir; başarı/süre-dolumu reset; politika redleri ve auth 401 SAYMAZ; `provider_health()` + digest `SAĞLIK:` satırı sadece aktif blokta | test_transient_failures_cool_provider_and_recover + test_auth_errors_never_count_toward_health + digest pair testi |
| O-3 capability filtresi | KAPALI | ladder adayı, `RouteSpec.capabilities` required-caps'ı (required_capabilities ile aynı kaynak) karşılamıyorsa atlanır; OR None-variant filtresiz (katalog caps'ı ayrı değerlendirir) | test_capability_requirements_filter_the_ladder (vision+tools: cerebras düşünülmez; text-only: girer) |
| O-4 fiyat çift-sözluğu | KAPALI (muhafız) | precedence değişmedi (ROUTES üstün); test ROUTES×catalog çift-fiyatlı her rotada eşitlik demanded | test_routes_and_catalog_effective_prices_agree (groq/cerebras/nous/openrouter/deepseek çiftleri) |
| O-5 OR-liste fiyatı katalogda | KAPALI-DEĞİL (tasarım) | indirim ROUTES'ta; `gpt-oss@openrouter` fiyatı YOK → bilinmeyen fiyat fail-closed; icat yok | davranış korundu |
| O-6 cache tazelik penceresi | KAPALI-DEĞİL (tasarım) | 5 sn kota cache kabul; unknown≠unlimited; header provider'a yapışık | mevcut yeşil testler |

## Test muhasebesi (sandbox, gerçek çalıştırma)
- Hedefli: 170/170 (routing+aspasia suite'leri + 7 yeni hardening testi)
- FULL: **809 passed / 0 failed / 0 skipped** · ruff: temiz
- E2E EN ÖNEMLİ TEST (4/4) ve red-kanıtı: **fake transport dikişi** — gerçek
  API'ye tek çağrı yapılmadı, para harcanmadı. LIVE PROVIDER TEST DEĞİL.
- CI (GitHub Actions): bu session push'a kapalı → **NOT VERIFIED**; push yeni
  session'da `arena/01a0694e-pineal-clean` üzerinden.

## Not (dürüstlük)
Önceki session'daki `docs/ASPASIA_FINAL_SPEC.md`, `docs/ASPASIA_CHIEF_LAYER.md`,
`docs/SECURITY_REVIEW.md` diskte varken sandbox sweep tarafından silindi; hiç
git commit'lenmemişlerdi ve kurtarılamadı (git log --all boş). Kod/test muhtevası
kayıp değil — tamamı commit'lerde (47982a3, 3fa18c3). Bu rapor o kaydı ikame
etmez; yalnız hardening kapanışının mühürüdür.
