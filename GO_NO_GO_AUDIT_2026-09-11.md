# GO / NO-GO DENETİMİ — 2026-09-11 (Sıfır-Güven Turu)

**Önceki FAZ mühürleri, README ve eski raporlar kaynak olarak KULLANILMADI.**
Kaynak sırası: çalışan kod → CI/GitHub kayıtları → bağımsız CVE kayıtları → ampirik PoC.

| Alan | Değer |
|---|---|
| Denetlenen HEAD | `e3ea76b1000db0fdc1a8e27575429b0642d414ba` (8 Eyl 2026, "fix(scripts): UTF-8 stdout encoding…") |
| Branch | `arena/01a08e47-pineal-clean` (origin/main ile birebir aynı, ahead 0 / behind 0) |
| Working tree | Temiz; untracked/ignored `.env`, secret veya token dosyası YOK |
| Nihai hüküm | 🔴 **NO-GO** — 2 ampirik olarak doğrulanmış P0 blocker + deployment failure |

---

## A — Repository Gerçekliği: 🟢 PASS (tek şerhle)

- Yerel HEAD `e3ea76b…` = `origin/main` = denetim talebindeki hedef hash. Tekil prod commit olarak doğrulandı.
- `git status --porcelain --ignored=matching`: dirty dosya yok, `.env`/secret sızıntısı yok.
- ⚠️ Şerh: checkout **shallow (depth 1)**. Commit geçmişi yerelden denetlenemiyor; tarihçe iddiaları bu turda kapsam dışı bırakıldı (zaten sıfır-güven prensibi gereği tarihçe kanıt sayılmıyor).

## B — CI Bütünlüğü: 🟡 KISMİ — CI yeşil, ama "deployable" değil

CI workflow (push @ `e3ea76b`): run `34252493534` + `34252492283` → **success**.
Job matrisi (her iki run'da da): `frontend ✅ · rust-core ✅ · android ✅ · backend ✅ · smoke ✅`.

Ancak aynı HEAD'in **commit status**'u:

| Context | State |
|---|---|
| `Vercel` | ❌ failure — "Deployment has failed" (`dpl_J3DkBytUszh84FHrTy1jKzXcqynK`) |
| `optimistic-generosity - pineal-clean` (Railway) | ❌ failure — "Deployment failed" |

**Release Gates** (`release-gates.yml`, yalnız `workflow_dispatch`):
tarihte **tek koşu** (3 Eyl 2026, run `33806455513`, mevcut HEAD'den 5 gün önce):
**Gate A (canlı LLM) FAILURE**, Gate B (Docker+Chromium) success.
Koşu logları artık erişilemiyor (retention); başarısızlık kökü yeniden koşu olmadan bilinemez.
Mevcut HEAD için Gate A/B kanıtı **sıfır**.

Sonuç: "CI yeşil → canlı hazır" denklemi bu HEAD'de kurulamaz. B maddesi kendi
kriteryasına göre (deployment + gate kanıtı dahil) **FAIL**'dir; yalnız GitHub Actions
job'ları baz alınırsa PASS.

## 🔴 P0-1 — BadHost auth bypass: KODDA DOĞRULANDI + AMPİRİK OLARAK İSPATLANDI

**Kod kanıtı** — `backend/api.py:212-213` (auth middleware'inin tamamı `request.url.path` üzerinde):

```python
is_api = request.url.path.startswith("/api/")
is_openai = request.url.path.startswith("/v1/")
```

Dosyada `request.url.path` güvenlik kararı için 8 yerde kullanılıyor (212, 213, 254, 292, 300, 320, 665, 668).
Raw ASGI scope (`request.scope["path"]`) güvenlik mantığında **hiçbir yerde** kullanılmıyor.

**CVE kanıtı** — GHSA-86qp-5c8j-p5mr / CVE-2026-48710 ("BadHost") gerçek ve birebir bu deseni anlatıyor:
Starlette ≤1.0.0'da Host header doğrulanmadan `request.url` yeniden kuruluyor; Host içine `/`, `?`, `#`
enjekte edilince `request.url.path` gerçek request path'inden sapıyor ve `request.url` tabanlı güvenlik
kontrolü atlatılıyor; router yine gerçek path'e dispatch ediyor. Düzeltme: Starlette **1.0.1** [1](https://github.com/advisories/GHSA-86qp-5c8j-p5mr) [2](https://dbugs.ptsecurity.com/vulnerability/CVE-2026-48710) [3](https://www.resolvedsecurity.com/vulnerability-catalog/GHSA-86qp-5c8j-p5mr).

**Bağımlılık kapanı kanıtı** — `open-interpreter==0.4.3` wheel metadata'sından (PyPI):

```
Requires-Dist: starlette (>=0.37.2,<0.38.0)
```

Bu pin, yamalı Starlette'e (≥1.0.1) yükseltmeyi imkânsız kılıyor. `requirements.txt` açıkça
`open-interpreter>=0.4.0` içeriyor → prod imajın güvenlik hattı, `ENABLE_INTERPRETER`
(default **false**, yalnız lazy import: `agent_core/agents/interpreter_agent.py:25`) ile kapalı
tutulan opsiyonel bir aracın pin'ine rehin.

**Ampirik PoC** (bu denetimde koşuldu — CI ile aynı stack: `starlette==0.37.2`, `fastapi==0.115.2`;
middleware mantığı `backend/api.py`'den birebir kopya):

```text
GET /api/secret  Host: legit.local          (token yok)  →  HTTP/1.1 401  ✓ doğru
GET /api/secret  Host: x/zzz?y=             (token yok)  →  HTTP/1.1 200
                                                             body: {"secret":"VAULT_CONTENTS_LEAKED"}
```

Yani: zehirlenmiş Host header ile **tokensiz istek korumalı endpoint'e 200 aldı**.
Bu teorik bir bulgu değil; tek raw HTTP isteğiyle yeniden üretilebilir auth bypass'tır.
İnternete açık deployment'ta `/api/*` ve `/v1/*` tamamen savunmasızdır.

## 🔴 P0-2 — PINEAL_TOKEN frontend bundle'ına gömülüyor: KODDA DOĞRULANDI

Üç ayrı yerde zincir teyit edildi:

1. `Dockerfile:15-16` — `ARG VITE_PINEAL_TOKEN` + `ENV VITE_PINEAL_TOKEN`; yorum bloğu açıkça
   "PINEAL_TOKEN tanımlıysa AYNI değer VITE_PINEAL_TOKEN olarak verilmeli" diyor.
2. `docker-compose.yml:12` — build arg olarak `VITE_PINEAL_TOKEN: ${VITE_PINEAL_TOKEN:-}` aktarımı.
3. `frontend/src/store.ts:19` — `bakedToken = import.meta.env.VITE_PINEAL_TOKEN`; `currentApiToken()`
   bunu fallback olarak her `apiFetch` çağrısında `X-API-Key` yapıyor.

`VITE_` önekli her değer Vite build'inde bundle'a **plaintext** gömülür → master token
tarayıcıdan indirilebilir statik bir asset haline gelir. RUNBOOK'un önerdiği akış
(`PINEAL_TOKEN=x` + `VITE_PINEAL_TOKEN=x`) bunu resmen tarif ediyor.

Not: `store.ts`'de runtime token girişi (Kasa → localStorage) zaten var ve yeterli;
build-time bake yolu gereksiz olduğu gibi tek başına bir P0 sızıntı vektörü.

## 🟠 P1 — Python bağımlılıkları kilitli değil

- Python tarafında **hiçbir lock file yok** (yalnız `rust_core/Cargo.lock` ve `frontend/package-lock.json` var).
- `requirements.txt` tamamen `>=` aralıkları (`fastapi>=0.115.0`, `httpx>=0.27.0`, …).
- Bugünkü imaj ile bir hafta sonraki imaj aynı ağacı kurmayı garanti etmiyor; BadHost
  zinciri (open-interpreter → starlette) gibi sürprizlere açık.

## 🟡 P2 — `/api/initiate` payload limitleri

`backend/api.py:1605` — `InitiatePayload`: `client_id`, `url`, `rituals`, `playlist`, `envies`
alanları çıplak `str`, `max_length` yok. (Karşıt örnek aynı dosyada mevcut: `/v1` chat
payload'ı alan limitli + 1 MiB toplam sınırı, `api.py:845-875`.) Rate limit kovası
(`initiate: 5/60sn`) istismarı yavaşlatır ama kaldırmaz.

## 🟢 Bu turda yeniden teyit edilen pozitif noktalar (spot kontrol)

- Auth fail-closed posture, rate-limit kimliğinin sunucudan türetilmesi (`rate_identity`, `api.py:250-253`) kodda mevcut.
- `docker-compose.yml`'de `PINEAL_ENV` production sabitlemesi ve tek-replica uyarısı yerinde.
- Routing/spend-cap iddiaları bu HEAD'de CI tarafından yeşil; bu turda çelişen kanıt bulunmadı
  (ancak runtime D–I maddeleri bu turun kapsamında yeniden koşturulmadı — sıradaki adım).

---

## HÜKÜM: 🔴 NO-GO

Gerekçe özeti:

| # | Bulgu | Statü |
|---|---|---|
| 1 | BadHost auth bypass (`request.url.path` + starlette 0.37.2) | 🔴 AMPİRİK İSPAT — tek istekle tokensiz 200 |
| 2 | Master token'ın frontend bundle'ına gömülmesi | 🔴 KODDA TEYİT — Dockerfile+compose+store.ts |
| 3 | Vercel + Railway deployment status | 🔴 failure @ hedef HEAD |
| 4 | Gate A canlı LLM kanıtı | 🟠 son koşu FAILURE (3 Eyl, HEAD öncesi), log yok |
| 5 | Gate B mevcut HEAD kanıtı | 🟠 hiç koşulmadı |
| 6 | Python dependency lock | 🟠 yok |
| 7 | InitiatePayload limitleri | 🟡 zayıf |

## Mühür Yolundaki Zorunlu Sıra (kanıta dayalı)

1. **Auth'u raw scope'a taşı**: `request.url.path` → `request.scope["path"]` (tüm güvenlik
   kararları; `root_path` eklenmeden, çünkü reverse-proxy strip senaryosunda scope["path"]
   zaten route'un gördüğü path'tir). Bu tek başına BadHost vektörünü kapatır.
2. **`open-interpreter`'ı core `requirements.txt`'ten çıkar** → `requirements-interpreter.txt`
   / opsiyonel extra (zaten `ENABLE_INTERPRETER=false` default ve lazy import).
3. **Starlette'i ≥1.0.1'e, FastAPI'yi uyumlu sürüme çek** (mevcut en güncel fastapi 0.141.1,
   `starlette>=0.46.0` istiyor; açık yol mevcut).
4. **`VITE_PINEAL_TOKEN`'ı Dockerfile, compose ve build zincirinden kazı**; yalnız runtime
   token girişi (mevcut Kasa akışı) kalsın. README/RUNBOOK'taki "aynı değeri verin" talimatı silinsin.
5. **`requirements.lock` üret** (pip-compile/uv), Dockerfile'ı lock'a bağla.
6. Railway + Vercel build hatalarını çöz → commit status yeşil.
7. Release Gate A + B'yi **mevcut HEAD** üzerinde yeniden koştur → kanıt dosyaya işle.
8. Temiz HEAD'de tam CI → SON MÜHÜR değerlendirmesi.

Runtime protokol maddeleri (C–I: restart/persistence, paralel yük, failure injection,
provenance) bu turun A/B/P0 kapsamından sonra sıradaki denetim adımıdır.

---

## EK (aynı gün): UYGULANAN DÜZELTMELER VE KANITLARI

Yukarıdaki NO-GO hükmünden sonra düzeltmeler aynı branch'te (`arena/01a08e47-pineal-clean`) uygulandı:

| # | Düzeltme | Dosyalar |
|---|---|---|
| 1 | Auth/rate-limit/exception kararları `request.url.path` → ham ASGI `scope["path"]` (`_secure_path`); tüm `request.url.path` güvenlik kullanımları kaldırıldı | `backend/api.py` |
| 2 | `open-interpreter` core'dan çıkarıldı → opsiyonel dosya | `requirements.txt`, yeni `requirements-interpreter.txt` |
| 3 | `starlette>=1.0.1,<2.0.0` + `fastapi>=0.141.0` (BadHost düzeltmesi; kurulan: starlette 1.6.0 + fastapi 0.141.1) | `requirements.txt`, `requirements.lock` |
| 4 | `VITE_PINEAL_TOKEN` build-time gömme tamamen kaldırıldı (runtime Kasa girişi tek yol) | `Dockerfile`, `docker-compose.yml`, `frontend/src/store.ts`, `.env.example`, `frontend/.env.example`, `README.md`, `RUNBOOK.md` |
| 5 | Deterministik production lock (163 pin; Dockerfile + Gate A lock'tan kurar) | yeni `requirements.lock`, `Dockerfile`, `release/release-gates.yml` + `.github/workflows/release-gates.yml` (birebir ayna sözleşmesi korundu) |
| 6 | `/api/initiate` alan tavanları (`client_id` ≤ PINEAL_MAX_CLIENT_ID_LENGTH, `url` ≤ 8192, metinler ≤ 32000, `scraper_type` ≤ 64, goals ≤ 64) | `backend/api.py` |
| 7 | BadHost regresyon sözleşmesi (6 test) + opsiyonel katman testlerinde dürüst skip | yeni `tests/integration/test_badhost_auth_bypass.py`, `tests/unit/test_no_mock_in_production.py` |

### Doğrulama kanıtları (bu denetimde koşuldu)

- **Tam süit**: `pytest --cov-fail-under=80` → **1152 passed, 4 skipped, coverage %85.77** (yeni stack: fastapi 0.141.1 + starlette 1.6.0; ruff temiz).
- **BadHost ampirik öncesi/sonrası**: aynı raw-socket saldırısı (`Host: x/zzz?y=`, tokensiz) — starlette 0.37.2'de **200 + veri sızıntısı** (PoC), düzeltilmiş stack + gerçek uvicorn sunucusunda **401**.
- **Yamalı Starlette savunma derinliği**: `request.url.path` artık Host zehirlenmesinde sapmıyor (1.6.0 doğrulaması); middleware yine de raw scope'a bağlı → eski stack'e dönüşte bile korunur.
- **Frontend**: `npm run build` başarılı; üretilen `dist/` bundle'ında `VITE_PINEAL_TOKEN` araması **sıfır eşleşme**.
- **Lock**: temiz venv'da `requirements.txt` + `requirements-osint.txt` kurulumu → `pip freeze`; `open-interpreter` ağaçta yok, `starlette==1.6.0` pinli.

### Hâlâ açık kalan kapılar (kod değişikliğiyle kapanamaz)

- Railway + Vercel deployment status'ları (platform tarafı; push sonrası yeniden gözlem gerek).
- Release Gate A (canlı OpenRouter) ve Gate B (Docker+Chromium) — mevcut düzeltilmiş HEAD üzerinde `workflow_dispatch` ile koşturulmalı.
- Runtime protokol maddeleri C–I (restart/persistence, paralel yük, failure injection, provenance) — ayrı denetim turu.
