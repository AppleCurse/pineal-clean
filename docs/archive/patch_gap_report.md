# Yama vs HEAD (`9df180a`) — gerçek fark ve yapılan entegrasyon

Yama dosyası (`01a0344c-…patch`) **doğrudan uygulanmadı** (çakışma). Karşılaştırma belgesindeki 6 maddenin çoğu bu checkout’ta **zaten vardı**.

| Madde | Belgedeki iddia | Gerçek HEAD | Aksiyon |
|---|---|---|---|
| 1 Spend Cap | yamada var | **yoktu** (yamada da yoktu; belge ekstra) | **Eklendi** `SpendCapExceeded` + `OPENROUTER_MAX_SPEND_USD` (0=kapalı) |
| 2 fallback_reason | ajanlarda eksik | friction/cognitive/auth/depth/vision vardı; OSINT/passion/resonance eksikti | **Tamamlandı** standart etiketler |
| 3 Uncertainty uzunluk skoru | semantic_richness var | **zaten P1-B2** (sihirli sayılar yok) | dokunulmadı |
| 4 X scraper | eski browser_oxide | **zaten B4** `XScraperUnsupportedError` | dokunulmadı |
| 5 i18n verdict | yalnız TR | `verdict_code` vardı, rozet TR hardcoded | **i18n anahtarları** |
| 6 live_llm_gate.py | yok | **zaten var** | dokunulmadı |

## Yeni sözleşmeler

- `OPENROUTER_MAX_SPEND_USD>0` ve `total_cost >= cap` → canlı `query` `SpendCapExceeded` (cache/local sayılmaz).
- `fallback_reason`: `llm_unavailable` | `no_target_data` | `provider_credentials_unavailable` | `api_error` | vision: `no_urls` / `download_failed`.
- UI: `verdictHealthy` / `Inflated` / `Suspicious` / `Insufficient`.

Test: `test_spend_cap` + ilgili unit’ler yeşil (21).
