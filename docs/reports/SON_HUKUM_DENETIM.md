# Son Hüküm — Birleşik Denetim Kararı

**Tarih:** 2026-09-02  
**Repo:** `AppleCurse/pineal-clean`  
**Dal:** `arena/01a06154-pineal-clean`  
**Kaynaklar:** `INDEPENDENT_FORENSIC_AUDIT.md`, `REPORT_CROSS_VALIDATION.md`, `RELEASE_EVIDENCE.md` (rc.2 + §12), `docs/reports/CAPABILITY_ROUTING_DECISION_2026-09-02.md`, `docs/reports/CROSS_AUDIT_FIXES_2026-09-02.md`, `docs/reports/GENEL_DURUM_HARITASI_2026-09-02.md`

---

## Tek cümlelik hüküm

> Çekirdek orkestrasyon (API · executor · bellek · telemetri · güvenlik kapıları · hermetik testler) **çalışır ve dürüst-duraklamalıdır**; bu turda kapatılan çapraz-denetim boşlukları (JSON repair kapsamı, depth failure görünürlüğü, verifier/memory prompt-injection, authentic_vector epistemic damga, slug drift, G7 workflow dosyası) main adayına hazırdır. **GO LIVE** hâlâ iki operatör gate'ine bağlıdır: canlı OpenRouter E2E + Docker/Chromium smoke (Instagram bacağı manuel).

---

## Skor kartı (kanıt ağırlıklı)

| Katman | Durum | Not |
|---|---|---|
| Statik kalite (ruff + pytest + coverage≥80) | ✅ | Bu tur: **645 passed, 2 skipped** · **%83.32** coverage |
| Frontend check/build | ✅ | CI matrisi yeşil (önceki main) |
| Rust core / Android CI | ✅ | experimental / bağımsız istemci — ürün kararına etkisi yok |
| Hermetik E2E (yerel provider) | ✅ | mock'suz cross-stack path mevcut |
| Canlı OpenRouter E2E (Gate A) | 🔧 açık | `release-gates.yml` ile koşulabilir; secret + manuel dispatch |
| Docker + Chromium smoke (Gate B) | 🔧 açık | workflow deterministik kısmı otomatik; IG initiate operatörde |
| Belge ↔ kod (model slug / zincir) | ✅ | 2026-09-02 matrisi ile hizalandı (bu tur) |
| Prompt-injection yüzeyi (verifier + memory) | ✅ | fence + sanitize + reject (bu tur) |
| Depth / 7-pillar failure görünürlüğü | ✅ | pillar önceden; depth bu tur |

**Genel:** 🟡 **RELEASE CANDIDATE** — rc.2 mühür + cross-audit fixes; 2 canlı gate açık.

---

## Bu turda kapatılan bulgular

1. **JSON repair `except Exception` aşırı genişti** → parse/schema'ya daraltıldı.  
2. **depth_analyst failure sessizdi** → `agent_runs` + evidence + UNAVAILABLE metadata.  
3. **Verifier bio/search prompt injection** → `<UNTRUSTED_*>` fence.  
4. **MemoryInjector "KUTSAL OVERRIDE"** → untrusted operator rules + injection drop.  
5. **authentic_vector epistemik belirsizlik** → `model_estimate` damgası.  
6. **Slug drift** (README/RUNBOOK/.env.example/router.example/interpreter vs AGENT_CHAINS) → matris.  
7. **G7 workflow gövdesi eklendi** → `release/release-gates.yml`. (2026-09-03 notu: App token'ın `workflows` izni olmadığı için `.github/workflows/`'a kopya operatör adımı olarak bırakılmıştı — **bu adım bu turda kapandı**, bkz. aşağıdaki §2026-09-03.)

Detay: `docs/reports/CROSS_AUDIT_FIXES_2026-09-02.md`.

---

## Hâlâ açık / bilinçli sınırlar

| # | Madde | Sahip |
|---|---|---|
| G7-A | `live_llm_openrouter_e2e` yeşil koşu kaydı | Önce `cp release/release-gates.yml .github/workflows/` (workflows izni); sonra Operatör + `OPENROUTER_API_KEY` |
| G7-B | Docker/Chromium smoke yeşil + IG initiate manuel | Operatör ortamı |
| — | Android backend'e bağlı değil (bağımsız Gemini istemcisi) | Ürün kararı; blocker değil |
| — | `rust_core` ürün runtime'a bağlı değil | Bilinçli experimental |
| — | X kazıma devre dışı / yetki bekler | Politika |

---

## Merge kriteri (bu PR)

1. CI matrisi yeşil: backend · frontend · rust-core · android · smoke  
2. Coverage gate ≥ %80  
3. Ruff clean  
4. Vercel/Railway status context'leri repo-dışı servis; kod merge blocker'ı **değil** (önceki PR'larla aynı politika)  
5. Gate A/B bu PR ile **kapanmaz** — yalnız koşulabilir hale gelir

---

## Operatör sonraki adım (GO LIVE)

```text
Actions → Release Gates → Run workflow (main)
  ├─ Gate A yeşil → live_llm_openrouter_e2e kapanır (run URL'sini RELEASE_EVIDENCE'a işle)
  └─ Gate B yeşil + yerel IG initiate → docker_chromium_smoke kapanır
```

Her iki gate yeşil + kanıt işlenmeden **stable 3.0.0** ilan edilmez.

---

## 2026-09-03 ek tur — "kırmızı" hükümlerinin yeniden ölçümü + G7-A mekanizması

İki adli denetim raporunun (`INDEPENDENT_FORENSIC_AUDIT.md`, `REPORT_CROSS_VALIDATION.md`) kırmızı
satırları ve bu belgenin G7 maddeleri, `f1e4602` (main, #59) üzerinde **yeniden koşuldu** — iddia
değil, ölçüm:

| Kaynak raporda kırmızı | 2026-09-03 ölçümü | Hüküm |
|---|---|---|
| `test_human_behavior.py` 2 bayat assertion → "CI backend kırmızı" | `pytest -q` → **723 passed, 2 skipped** | ✅ BAYAT (zaten kapanmış) |
| Coverage < %80 riski | `--cov-fail-under=80` → **%84.13** | ✅ GEÇTİ |
| `ruff check .` | **All checks passed!** | ✅ GEÇTİ |
| CI android job'u kırık (`gradlew` yok) | `android/gradlew` + `gradlew.bat` repoda; main CI run `33694988566` **success** | ✅ KAPANDI |
| PyYAML / aiohttp beyan açığı | `requirements.txt`'ta açık satır | ✅ KAPANDI |
| `OPENROUTER_TIER_2_MODEL` / spend-cap / SERPAPI env | kod + `.env.example` hizalı | ✅ KAPANDI |
| G1 "rc.2 mührü main'de yok" | `VERSION=3.0.0-rc.2`, `release/3.0.0-rc.2.json` main'de | ✅ KAPANDI |
| **G7-A `live_llm_openrouter_e2e` yeşil koşu kaydı** | Workflow `.github/workflows/release-gates.yml`'a **işlendi** (bu tur), `gh run list --workflow "Release Gates"` → **0 koşu** | 🟡 **mekanizma KAPANDI / koşu AÇIK** |
| **G7-B `docker_chromium_smoke` + IG bacağı** | Bu sandbox'ta docker daemon yok, dış ağ kapalı (`openrouter.ai` → `000`) | 🔴 **AÇIK** (operatör ortamı) |

**Bu turda yapılan tek kod değişikliği:** `.github/workflows/release-gates.yml` (gövde `release/`
kaynağıyla birebir) + `tests/unit/test_release_gates_workflow.py` (7 test: dosya yeri, gövde
eşitliği, yalnız-`workflow_dispatch`, Gate A fail-closed secret + spend-cap, Gate B imaj/health/auth/
Chromium/teardown, concurrency). Böylece "operatör `cp`'lesin" adımı kalıcı olarak kaldırıldı ve
gate'ler merge sonrası **dispatch listesinde görünür** olacak.

**Kapanmayan iki şey kapı değiştirilemez:** (1) Gate A için repo **Settings → Secrets →
`OPENROUTER_API_KEY`** tanımlanıp `Actions → Release Gates → Run workflow (main)` koşusu gerekiyor —
secret'ın varlığı bu oturumdan `gh secret list` → **403** olduğu için doğrulanamadı; (2) Gate B'nin
Instagram bacağı ağ/çerez durumuna bağlı olduğu için operatörde manuel. Bunlar görülmeden **stable
3.0.0 ilan edilmez** (Bölüm 11/12 uyarısı aynen geçerli).

---

*Bu hüküm iddia değil; yukarıdaki dosya ve test sözleşmelerine referanslı bir karar kaydıdır.*
