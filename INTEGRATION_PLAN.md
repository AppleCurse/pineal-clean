# INTEGRATION PLAN — OSINT/Stealth/AI Araç Listesi Uzlaşması

**Tarih:** 2026-08-29 · **Kapsam:** Kullanıcının ilettiği "doğrudan entegre edilecek araçlar" listesinin bağımsız kanıt denetimi + uygulama sırası
**Yöntem:** Her araç için (1) varlık/lisans/bakım durumu doğrulandı, (2) pineal-clean mimarisiyle (Playwright tek browser stack, exact-key cache sözleşmesi, "hiçbir platforma otomatik işlem yapılmaz" ilkesi, dürüst-sonuç modeli) oturma analizi yapıldı.

---

## 1. Liste denetimi — düzeltilen iddialar

| Liste iddiası | Kanıt sonucu | Hüküm |
|---|---|---|
| Blackbird "socid-extractor ile aynı ekosistemde" | Blackbird = p1ngul1n0 (WhatsMyName tabanı); socid-extractor = soxoj. **Farklı ekosistemler** | DÜZELTİLDİ |
| Snoop "5300+ site, aktif geliştirme" | Gerçek; ancak lisans **demo/full ayrımlı özel lisans** (full DB bağış karşılığı — repo issue #37). Ürün koduna gömme için lisans incelemesi şart | KOŞULLU |
| GHunt "Email girdisi alır → ayak izi çıkarır" | Gizlenen ön koşul: **operatörün kendi Google oturum cookie/OAuth'u** (GHunt Companion). Hassas kimlik bilgisinin vault'a girmesi gerekir | KOŞULLU (ön koşul belgelendi) |
| GPTCache "SOTA semantic caching" | Proje bakım modunda (v0.1.42 sonrası düşük aktivite, topluluk fork'u öne çıktı). Ayrıca pineal'ın cache'i **bilinçli exact-key** (model+sıcaklık dahil); anlamsal önbellek "benzer soru → başka yanıt" karışması üretebilir = halüsinasyon sözleşmesiyle gerilim | RED (şimdilik) |
| undetected-chromedriver "Hemen entegre" | **Selenium/CDP tabanlı**; pineal tamamen Playwright mimarisinde. İkinci browser stack = bakım yükü ×2. Stealth ihtiyacı için Playwright-native çözümler var | RED (mimari) |
| Stagehand/browser-use "PatternInterrupt ve ShadowExecutor'a browser kontrolü" | İkisi de **eylem üreten** ajanlar. README §9: *"sistem hiçbir platforma otomatik/gizli mesaj göndermez"*. Browser-otomasyon ajanı web'de TIKLAR/FORM DOLDURUR → çekirdek ürün vaadiyle **doğrudan çelişir** | RED (etik sözleşme) |
| CloakBrowser / invisible_playwright | İkisi de gerçek ve Playwright-native: CloakBrowser MIT Chromium fork; invisible_playwright MIT Firefox (238MB indirme, platform kısıtlı) | KABUL (env kapılı, ileri faz) |

## 2. Uzlaşılmış entegrasyon sırası

| Faz | Araç | Gerekçe |
|---|---|---|
| **FAZ 1 (bu commit — uygulandı)** | `socid-extractor` (MIT, hafif, tarayıcı gerektirmez) | Profil URL'sinden kararlı kimlik kaydı; `is_safe_url` SSRF guard'ı arkasında; kütüphane yoksa **dürüst `available:false`**. Kanıt zinciri sözleşmesine birebir oturur |
| FAZ 2 | `Maigret` (MIT) — username taraması | socid-extractor'ın doğal üst katmanı (aynı yazar); `osint_footprint`'i genişletir; env kapılı + timeout |
| FAZ 3 | `blackbird` çekirdeği (yalnız tarama, `--ai` DIŞI) + `holehe` | Email pivotu; **yalnız `/api/experimental/*`** (hassas veri sınıfı) |
| FAZ 4 | `Crawl4AI` (Apache-2.0) | Public-web araştırma sonuçlarını LLM-dostu metne çevirir; quote_guard kaynak kalitesi artar |
| FAZ 5 | `invisible_playwright` / `CloakBrowser` | `STEALTH_PROVIDER=playwright_stealth\|invisible\|cloak` env seçimi; default mevcut davranış; ağır binary indirmeleri opsiyonelde |
| FAZ 6 (koşullu) | `GHunt` + `GitFive` | Yalnız deneysel uç + operatör-kimliği ön koşulları UI'da açıkça belgelenerek |
| İZLEMEDE | Obscura, Stagehand (yalnız extract-okuma modu) | Genç projeler; etik sözleşme gözden geçirilmeden eylem yeteneği eklenmez |

## 3. FAZ 1 uygulaması (bu commit)

- `agent_core/services/socid_enricher.py` — URL/HTML → yapılandırılmış kimlik kaydı; SSRF guard'lı; ImportError/ağ/parse hatalarında dürüst `available:false`
- `POST /api/experimental/socid/extract` — kullanıcı bir profil URL'si yapıştırır, yapılandırılmış kayıt alır
- `_run_public_web_research` zenginleştirmesi — eşleşen arama sonuçlarına (ilk 3) `socid` alanı eklenir (yalnız kayıt bulunduğunda)
- Testler: `tests/unit/test_socid_enricher.py`
