# PINEAL-HERETIC v3.0 — Release Evidence Record

**Versiyon:** v3.0.0-rc.2  
**Tarih:** 2026-09-01  
**Branch tip (arena):** `8e3b2918`  
**Main tip:** `c4437def`  
**Genel karar:** 🟡 **RELEASE CANDIDATE — 2 canlı gate açık**

Bu belge, deployment kararı için gereken kanıtları mühürler.
Satır satır referans alınabilir; yorum veya iddia içermez.

---

## 1. Statik Kalite Kapıları

| Kontrol | Komut | Sonuç | Kanıt |
|---|---|---|---|
| Ruff lint | `ruff check .` | ✅ PASS | `All checks passed!` |
| Test suite | `pytest -q` | ✅ PASS | `591 passed, 2 skipped, 0 failed` |
| Coverage gate | `pytest --cov-fail-under=80` | ✅ PASS | `81.13% ≥ 80%` |
| Svelte type check | `npm run check` | ✅ PASS | `0 errors, 0 warnings` |
| Frontend build | `npm run build` | ✅ PASS | `113 KB JS bundle` |
| Frontend bundle verify | `grep -q "PINEAL-HERETIC" dist/assets/*.js` | ✅ PASS | CI `frontend` job |

---

## 2. Runtime Güvenlik Kontrolleri (negatif test — bu ortamda çalıştırıldı)

| Kontrol | Test | Beklenen | Gerçekleşen | Durum |
|---|---|---|---|---|
| LLM live gate | Anahtarsız `LLMGateway().query()` | RuntimeError | `REAL_LLM_CALL_NOT_EXECUTED` | ✅ |
| Production auth | `PINEAL_ENV=production`, token yok | SecurityConfigurationError | `PRODUCTION_AUTH_REQUIRED` | ✅ |
| SSRF | `http://169.254.169.254/` → socid endpoint | UnsafeURLError | `NON_PUBLIC_ADDRESS` | ✅ |
| Path traversal | `safe_child_path('/app/memory', '../etc/passwd')` | ValueError | `PATH_TRAVERSAL_BLOCKED` | ✅ |
| Secret redaction | `redact_text('sk-or-v1-abc123...')` | `[REDACTED]` | `[REDACTED]` | ✅ |
| 7-Pillar fail-closed | `PillarOrchestrator().run({})` (boş input) | `INSUFFICIENT_DATA` | `INSUFFICIENT_DATA` | ✅ |

---

## 3. Veri Bütünlüğü ve Disaster Recovery

| Test | Protokol | Sonuç |
|---|---|---|
| Atomic memory write | `CanonicalMemory.merge_evidence()` → tempfile + fsync + os.replace | ✅ VERIFIED |
| Memory persistence | `memory/` dizinine JSON yaz, oku, doğrula | ✅ VERIFIED |
| **Disaster recovery** | **63 görev → memory sil → restore → 63 görev** | ✅ **63 = 63 PASS** |
| SHA-256 bütünlük | `backup_restore.sh verify` → sha256sum --check | ✅ PASS |
| Pre-restore backup | Restore öncesi otomatik yedek alınıyor | ✅ CONFIRMED |

```
# Çalıştırılan komutlar:
bash scripts/backup_restore.sh backup
# → 63 görev, SHA-256: 532c30b9...

rm -rf memory && mkdir memory  # felaket simülasyonu

bash scripts/backup_restore.sh restore backups/pineal_20260901_114807.tar.gz
# → 63 görev geri yüklendi

ls memory/ | wc -l   # → 63
```

---

## 4. Deployment Konfigürasyonu

| Bileşen | Dosya | Değer | Durum |
|---|---|---|---|
| memory volume | `docker-compose.yml` | `pineal_memory:/app/memory` | ✅ |
| cache volume | `docker-compose.yml` | `pineal_cache:/app/cache` | ✅ |
| replica sınırı | `docker-compose.yml` | `replicas: 1` | ✅ |
| VOLUME direktifi | `Dockerfile` | `VOLUME ["/app/memory", "/app/cache"]` | ✅ |
| HEALTHCHECK | `Dockerfile` | `status in (ready, degraded) → exit 0` | ✅ |
| Railway replicas | `railway.toml` | `numReplicas = 1` | ✅ |
| Railway health | `railway.toml` | `healthcheckPath = "/health"` | ✅ |

---

## 5. Health Endpoint Durum Makinesi

| HTTP Status | Tetikleyici | Davranış |
|---|---|---|
| `200` | `status: ready` | Servis tam operational |
| `200` | `status: degraded` | Servis çalışıyor, kısıtlı (load-balancer geçirir, monitoring uyarır) |
| `503` | `status: failed` | Bağımlılık eksik veya security gate açılmamış |
| `503` | `status: starting` / diğer | Henüz hazır değil |

Degraded nedenleri (machine-readable):
- `UNIFIED_ROUTER_CONFIG_MISSING`: `PINEAL_LLM_BACKEND=unified` ama config yok
- `SPEND_CAP_UNLIMITED`: Production'da `OPENROUTER_MAX_SPEND_USD=0`

---

## 6. Güvenlik Özeti

| Alan | Mekanizma | Durum |
|---|---|---|
| API key transport (backend) | Memory-only, never logged, `redact_*` ile korunuyor | ✅ |
| API key transport (Android) | `@Header("x-goog-api-key")` — URL query param değil | ✅ |
| Production auth | `PINEAL_TOKEN` zorunlu, `secrets.compare_digest` | ✅ |
| CORS | Explicit `PINEAL_ALLOWED_ORIGINS` — wildcard yok | ✅ |
| Rate limiting | 5/dk initiate, 20/dk Aspasia (process-local, single instance) | ✅ |
| SSRF | DNS resolution + private IP block + redirect follow guard | ✅ |
| Path traversal | `validate_identifier` + `safe_child_path` + resolve check | ✅ |

---

## 7. Bilinen Sınırlar (Release Blocker Değil)

| Sınır | Açıklama | Etki |
|---|---|---|
| Multi-replica | process-local state — 2+ instance desteklenmiyor | `replicas:1` zorunlu, belgelenmiş |
| Multi-user auth isolation | SaaS senaryosu değil, single-user local tool | Kapsam dışı |
| DarkTriad TR-only markers | İngilizce profiller `0.0 → unavailable` döner | Halüsinasyon yok, fonksiyon null |
| CI smoke frontend linkage | Smoke job frontend job artifact'ını kullanmıyor | Low risk — frontend job ayrıca build+verify yapıyor |
| Python dep lock | `requirements.txt` versioned ama `pip-compile` lock yok | Yeniden üretilebilirlik riski küçük |

---

## 8. Açık Kalan 2 Gate (Canlı Ortam Gerektirir)

### Gate A — Real OpenRouter LLM E2E

```bash
OPENROUTER_API_KEY=sk-or-v1-...  LIVE_LLM_E2E=1  python live_llm_gate.py
```

Geçiş kriterleri (`live_llm_gate.py` içinde kodlu):
- Pipeline durumu: `completed` veya `partially_completed`
- `evidence_chain` dolu (mock değil)
- Kritik ajanlarda (`mirror_truth`, `passion_mapper`, `cognitive_profiler`, `resonance_synthesizer` vb.) sıfır `UNAVAILABLE` fallback
- `HolisticProfile.passions / frictions / cognitive / bridge` dolu ve schema-valid
- Hakem model (varsayılan `openai/gpt-5.6-sol-pro`) `APPROVED` döndürüyor

**Bu gate çalıştırılmadan:** LLM pipeline'ının production'da gerçek bir OpenRouter yanıtı işleyip işleyemediği `UNKNOWN`.

### Gate B — Docker + Chromium + Instagram Smoke

```bash
docker compose up --build
# container içinde:
python scripts/smoke_test_browser.py   # Playwright headless → example.com PASS
# veya:
POST /api/initiate url=https://www.instagram.com/<public_profile>/
# → WebSocket'te scrape log'ları görünmeli, task_id alınmalı
```

**Bu gate çalıştırılmadan:** Production Docker imajında Chromium'un gerçekten başlatılabildiği `UNKNOWN`.

---

## 9. Release Skoru

| Kategori | Puan | Max |
|---|---|---|
| Source quality (lint, type check, tests, coverage) | 20 | 20 |
| Security (SSRF, path, redaction, auth, CORS) | 18 | 18 |
| Data integrity (atomic write, corruption detection) | 10 | 10 |
| Disaster recovery (63→0→63 kanıtlandı) | 10 | 10 |
| Deployment config (volumes, replicas, healthcheck) | 10 | 10 |
| LLM gateway (gate, spend cap, chain, fallback) | 10 | 10 |
| Real OpenRouter E2E | 0 | 8 |
| Real Chromium/Instagram smoke | 0 | 7 |
| Multi-replica | 0 | 4 |
| Python dep lock | 3 | 3 |
| **TOPLAM** | **81** | **100** |

> Not: Skorun 91/100 görünmesinin sebebi multi-replica ve dep lock'un bu scope için 0 değil kısmi sayılmasıdır.
> Bu tabloda "çalıştırılamayan gate = 0" politikası uygulanmıştır.

---

## 10. İmza

Bu release evidence belgesi aşağıdaki araçlarla üretilmiştir:

- **Bağımsız adli denetim** (2026-09-01, sıfırdan): `INDEPENDENT_FORENSIC_AUDIT_2026-09-01.md`  
- **Go/No-Go raporu** (2026-09-01): 31 maddelik production readiness değerlendirmesi  
- **Son kontrol** (2026-09-01): 14 kategoride runtime + statik doğrulama  

Tüm kanıtlar kaynak koddan, çalıştırılan komutlardan ve HTTP yanıtlarından türetilmiştir.
Varsayım veya iddialara dayanmamaktadır.

**Bu belge bir sonraki versiyon çıkana kadar geçerlidir.**  
Değişiklik yapılırsa `VERSION` dosyası ve bu belge birlikte güncellenmelidir.

---

## 11. Post-seal Yeniden Doğrulama (2026-09-02)

> Bu bölüm, mühür **sonrasında** eklenmiştir. Orijinal kayıt (Bölüm 1–10) değiştirilmemiştir.

| Alan | Değer |
|---|---|
| Orijinal mühür | 2026-09-01 · branch `8e3b2918` · main tip `c4437def` |
| Main'e giriş | 2026-09-02 · main tip `b14a8e16` |
| Mühür sonrası main'e giren işler | #50 websocket/token + router gap · #52 UnifiedRouter → `/v1` + capability routing · #53 2026-09-02 karar matrisi |

**Yeniden doğrulama (`b14a8e16` / PR #53 head `d8162c9`):**

| Kontrol | Sonuç | Kanıt |
|---|---|---|
| `ruff check .` | ✅ PASS | `All checks passed!` |
| Backend tam suite | ✅ PASS | `634 passed, 2 skipped, 0 failed` |
| Coverage gate | ✅ PASS | `83.31% ≥ 80%` |
| Main CI matrisi | ✅ PASS | run `33590408702`: backend · frontend · rust-core · android · smoke |

**Değişmeyen açık gate'ler (GO LIVE için hâlâ zorunlu):**
- `live_llm_openrouter_e2e` — `python live_llm_gate.py` (Bölüm 8'deki kriterler)
- `docker_chromium_smoke` — Docker + Chromium smoke (Bölüm 9'daki kriterler)

> Bu iki canlı gate kapanmadan yayın kararı verilmemelidir (scoped skor: 81/100; gate kapanınca 100/100 hedefi).

---

## 12. Gate Çalıştırma Mekanizması — `release-gates.yml` (2026-09-02, post-seal)

> Bu bölüm mühür **sonrasında** eklenmiştir (Bölüm 11 gibi); orijinal kayıt (Bölüm 1–10) değiştirilmemiştir.
> Bu bölüm bir gate'in **koşulduğunu** değil, **koşulabileceğini** belgeler: açık kapılar ancak
> yeşil bir workflow koşusuyla kapanır (aşağıdaki kapsam notuna bakınız).

### Mekanizma

`.github/workflows/release-gates.yml` (kanonik kaynak gövde: `release/release-gates.yml`; ikisi birebir aynıdır ve bu eşitlik `tests/unit/test_release_gates_workflow.py` ile kilitlendi) — yalnızca `workflow_dispatch` (manuel) tetiklenir;
push/PR'da **asla** koşmaz (Gate A paralı canlı LLM çağrısı içerir). Aynı anda tek koşu
(concurrency; iptal etme yok — paralı koşu yarım kesilmez).

#### Güncelleme — 2026-09-03: G7-A'nın "mekanizma" yarısı kapandı

2026-09-02 kaydında workflow dosyası yalnızca `release/` altında duruyordu ve "operatör `cp`'lemeli"
notu düşülmüştü. **Bu adım artık kod tarafında tamamlandı**: `.github/workflows/release-gates.yml`
repoya işlendi; gövde-kaynak eşitliği + dispatch-güvenliği birim teste bağlandı; **PR #60 ile main'e alındı** (`68fa552`).

| Madde | 2026-09-02 | 2026-09-03 (bu tur, merge sonrası) |
|---|---|---|
| Workflow `.github/workflows/`'da | ❌ (yalnız `release/`) | ✅ **main'de** — PR #60 squash merge, `68fa552` |
| Workflow GitHub'da KAYITLI | ❌ (`gh workflow list` → yalnız `CI`) | ✅ `gh workflow list` → `Release Gates active` (id `349137796`) |
| Dispatch edilebilirlik | ❌ (dispatch listesinde görünmezdi) | ✅ **artık listede**; `gh workflow run release-gates.yml --ref main` → `403 Resource not accessible by integration` (agent token'ının Actions-write yetkisi yok) → **dispatch operatör adımı olarak kaldı** |
| Gate A **yeşil koşu kaydı** | ❌ | 🔴 **AÇIK · NOT_EXECUTED** — `OPENROUTER_API_KEY` secret'ı + dispatch gerekli. Secret varlığı doğrulanamadı (`gh secret list` → 403); sandbox dış ağı kapalı (`openrouter.ai` → connect fail) |
| Gate B **yeşil koşu kaydı** | ❌ | 🔴 **AÇIK · NOT_EXECUTED** — bu ortamda docker daemon yok; IG `initiate` bacağı operatör ortamında manuel |

**Kanıt discipline notu:** "gate koşuldu" yazılmadı çünkü koşum yok. Yeşil koşu üretemediğimiz yerde
sahte-yeşil veya "muhtemelen geçer" hükmü bırakmamak, bu belgenin Bölüm 8–9 kriterlerinin parçasıdır.
Gate A'nın dispatch'ini takiben düşmesi **beklenen ve doğru** davranıştır eğer secret tanımlı değilse
(fail-closed `::error::`) — bu bir başarısızlık değil, kapının çalıştığının kanıtıdır; kapanış için
yeşil job gerekir.

> Dürüstlük kaydı: bu satırlar bir gate'in **kapandığını** değil, gate'in **koşulabilir hale geldiğini** belgeler.
> Dispatch sonrası `Actions → Release Gates` run URL'si buraya işlenmeden `live_llm_openrouter_e2e` ve
> `docker_chromium_smoke` KAPATILMIŞ sayılmaz.

| Job | Gate | Ne yapar | Fail-closed garantisi |
|---|---|---|---|
| `live-llm-e2e` | `live_llm_openrouter_e2e` | `secrets.OPENROUTER_API_KEY` + `LIVE_LLM_E2E=1` ile `python live_llm_gate.py` → Bölüm 8 / Gate A kriterlerinin tamamı script içinde kodludur (durum, mock'suz kanıt, sıfır UNAVAILABLE, HolisticProfile, hakem onayı) | Secret tanımlı değilse job başında `::error::` ile **reddedilir**; `OPENROUTER_MAX_SPEND_USD=5` harcama tavanı |
| `docker-chromium-smoke` | `docker_chromium_smoke` | Gerçek imaj: `docker compose up --build` → `/health` (ready\|degraded → 200) → UI servis (`id="app"`) → production auth (token'sız 401, `X-API-Key` ile 200) → **konteyner içinde** `scripts/smoke_test_browser.py` (Chromium launch + `page.goto`) | İmaj `PINEAL_ENV=production` ile mühürlü: token'sız **başlamaz** (`PRODUCTION_AUTH_REQUIRED`); job kendi token'ını `.env`'e yazar; health 200 gelmezse düşer |

### Kapsam notu (dürüstlük kaydı)

- **Gate B'nin 3. alt kriteri bilinçli olarak otomatize edilmedi:** `POST /api/initiate` →
  Instagram `task_id` + WS scrape logu. GitHub runner IP'leri Instagram nezdinde platform
  limitine takılır (RUNBOOK: 429/403) ve bu bacağın koşulabilirliği çerez/platform durumuna
  bağlıdır. Workflow yalnız **deterministik** kısımları kanıtlar (build, health, auth,
  konteyner içi Chromium). Instagram bacağı operatörün kendi ortamında manuel koşulmalıdır:
  `docker compose up --build` → `POST /api/initiate url=https://www.instagram.com/<public_profile>/`
  → WS'te scrape logları.
- **Gate A koşusu yeşil dönerse** `live_llm_openrouter_e2e` gate'i kapanmış sayılır (tüm
  kriterler script içinde denetlenir; run URL'si kanıt olarak bu belgeye/reference'e işlenir).
- Gate B için workflow yeşili **tek başına yeterli değildir** (3. alt kriter manuel kalır);
  kapanış kararı Bölüm 8–9'daki tüm kriterler yerine getirilmeden verilmez.
- Bu iki gate kapanmadan GO LIVE kararı verilmez (Bölüm 11 uyarısı aynen geçerli).

### Koşu talimatı (operatör)

> 2026-09-03 doğrulaması: workflow artık main'de kayıtlı (`gh workflow list` → `Release Gates active`,
> id `349137796`), yani aşağıdaki 2. adım **elle yapılabilir** hale geldi. Agent token'ının kendisi
> dispatch edemez (`gh workflow run` → 403) — bu yüzden 1–4. adımların sahibi operatördür.

1. Repo **Settings → Secrets and variables → Actions** → `OPENROUTER_API_KEY` tanımlı olmalı
   (yoksa Gate A bilinçli olarak reddedilir; Gate B anahtarsız da koşar).
2. **Actions → Release Gates → Run workflow** (main üzerinde).
3. İki job'un yeşil dönmesi beklenir; run URL'si release kanıtı olarak kaydedilir.
4. Kalan Instagram bacağı (Gate B madde 3) operatör ortamında manuel doğrulanır.
