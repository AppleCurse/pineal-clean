# RUNBOOK — Kurulum, Çalıştırma, Sorun Giderme

## Başlatma
| Yöntem | Komut | Not |
|---|---|---|
| Windows | `baslat.bat` | venv + temel/OSINT pip paketleri + Playwright Chromium + frontend build (dist yoksa) + uvicorn:8000 |
| Docker | `docker compose up --build` | Playwright/Chromium dahil; `pineal_memory` volume |
| Manuel | `pip install -r requirements.txt && pip install -r requirements-osint.txt` → `cd frontend && npm ci && npm run build` → `uvicorn backend.api:app --port 8000` | İkinci dosya crawl4ai içindir (psutil meta-çatışması nedeniyle iki adım) |
| Dev (vite) | `frontend/.env`: `VITE_API_BASE=http://127.0.0.1:8000` → `npm run dev` | :5173 → :8000 |

## Anahtarlar (`.env` veya UI Kasası)
- `OPENROUTER_API_KEY` + `LIVE_LLM_E2E=1` → canlı bulut LLM.
- Yerel: `USE_LOCAL_LLM=true`, `LOCAL_LLM_URL=http://localhost:11434/v1`, `LOCAL_LLM_MODEL=...` (anahtar gerekmez).
  Not: API sunucusunda Kasa'daki "yerel model" seçimi (`use_local`) bu env'i ezer; env varsayılanı yalnız Kasa seçimi yapılmamışsa geçerlidir.
- `TAVILY_API_KEY`, `SERPAPI_API_KEY`, `EXA_API_KEY` → AutonomousVerifier web doğrulaması (yoksa DuckDuckGo yedeği).
- Vision: `OPENROUTER_VISION_MODEL` — varsayılan `google/gemini-3.7-flash`; VisionAnalyzer (profil fotoğrafları) ve görselli Aspasia isteklerinde kullanılır.
- Model varsayılanları (P2 ekonomik set; fiyatlar OpenRouter promosyonlarına tabi):
  Tier-1 `upstage/solar-pro4` (`OPENROUTER_TIER_1_MODEL`, promo 2026-09-10'a kadar),
  Tier-2 `inclusionai/ling-3.0-flash` (`OPENROUTER_TIER_2_MODEL`).
  Koddaki gerçek zincirler: depth `solar-pro4 → glm-5.2 → deepseek-v4-pro` ·
  dialogue `solar-pro4 → deepseek-v4-flash` · fast `ling-3.0-flash →
  deepseek-v4-flash` (env: `OPENROUTER_CHAIN_<TASK>`).
- Token kipi: `PINEAL_TOKEN=x` (HTTP `X-API-Key`; WS ilk auth mesajı) + `frontend/.env` → `VITE_PINEAL_TOKEN=x`. `PINEAL_ENV=production` tokensız başlatılamaz; Docker varsayılanı production'dır.
- Harcama tavanı: `OPENROUTER_MAX_SPEND_USD` (0=kapalı; env tanımsızsa da 0). Aşılırsa `SpendCapExceeded`.

## Sık sorunlar
| Belirti | Neden → Çözüm |
|---|---|
| `Görev durumu: failed`, 0 kanıt | LLM yok: anahtar + `LIVE_LLM_E2E=1` veya yerel model ayarla |
| Aspasia "bağlantıda kırılma" yanıtı | Aynı — zarif fallback; anahtar girilince gerçek yanıt |
| Tarayıcı boş | `frontend/dist` yok → build et; `/src/main.ts` 404 çıkarsa dist eski demektir |
| 429 (initiate/aspasia) | Rate limit — 1 dk bekle (bilinçli koruma) |
| 401 tüm API çağrıları | `PINEAL_TOKEN` tanımlı ama UI/istemci göndermiyor → `VITE_PINEAL_TOKEN` eşle veya token'ı kaldır |
| Scrape 429/403 (Instagram) | Platform limit/cookie: Kasaya güncel cookie gir |
| X (Twitter) hedefi | Kazıma devre dışı (B4): `XScraperUnsupportedError`; WS logunda "DESTEKLENMİYOR" görünür, analiz BAŞLATILMAZ — public-web alternatifi için yetki beklenir (`awaiting_authorization`) |
| WS bağlanmıyor | Token kipinde istemci bağlantıdan sonra ilk JSON mesajında `{type:"auth",token:"..."}` göndermeli; token URL/query'ye yazılmaz. Port 8000 dışındaysa `VITE_API_BASE` tanımla |

## Görev verisi
- Başlatma: `POST /api/initiate` immutable `task_id` döndürür.
- Çalışan görevi iptal/durdurma: `POST /api/tasks/{task_id}/cancel?client_id=...` veya `/halt` (terminal ve idempotent).
- Liste: `GET /api/tasks?client_id=...`
- Kalıcı silme (retention): `DELETE /api/tasks/{task_id}?client_id=...` (json kanıt dosyası + aktif snapshot)

## Test / Kalite kapıları
```
ruff check .          # gerçek hata kapısı (E9+F)
pytest -q             # unit+integration+e2e+ws sıra+güvenlik+protokol
                      # güncel sayı: pytest --collect-only -q | tail -1
cd frontend && npm run check && npm run build   # 0 hata + gerçek-app kilidi
```
CI: `.github/workflows/ci.yml` — her push'ta otomatik çalışır: backend (ruff + pytest + coverage), frontend (check + build + dist doğrulama), Rust (`cargo check` + `cargo test`), Android (lint + unit + assemble) ve smoke (uvicorn + curl).

Süitte kalıcı korumalar: `test_no_mock_in_production.py` (production'da mock yasağı,
AST-bazlı; dedektör canlılık kanıtı içerir), `test_consolidation_faz1_5.py`
(default-kapı sözleşmesi + beyan→kurulu zinciri).

## Deneysel OSINT kapıları (FAZ 1-5)
- `ENABLE_MAIGRET` / `ENABLE_HOLEHE` / `ENABLE_CRAWL4AI` — **default KAPALI**;
  kapalıyken davranış değişmez (uçlar dürüst `disabled` döner). Ayrıntılı alt
  değişkenler `.env.example`'da; kurulum ikinci adım dosyası:
  `pip install -r requirements-osint.txt` (crawl4ai; psutil meta-çatışması).
- `STEALTH_PROVIDER=playwright_stealth|invisible|cloak|none` — seçici kapı DEĞİL:
  default bugünkü davranış. invisible/cloak binary İNDİRMEZ; `INVISIBLE_BROWSER_BINARY`
  / `CLOAK_BROWSER_EXECUTABLE` yolu gösterilmezse dürüst `binary_missing` döner
  (`GET /api/experimental/stealth` ile sorgulanır).
- Dürüstlük sözleşmesi: tarama kullanılamazsa `available:false` + makine-okunur
  sebep; "iz/kayıt yok" iddiası yalnız sıfır-hata taramada; mock/uydurma yasak
  (testle korunur).

Canlı LLM gate (manuel, gerçek anahtar gerektirir):
```
OPENROUTER_API_KEY=sk-or-v1-... LIVE_LLM_E2E=1 python live_llm_gate.py
```
Kriterler: `completed` + dolu evidence + kritik ajanlarda sıfır UNAVAILABLE
fallback + dolu HolisticProfile + hakem onayı (varsayılan hakem:
`openai/gpt-5.6-sol-pro`; `OPENROUTER_JUDGE_MODEL` ile ezilebilir).
Bu script 360° zincirinin gerçek LLM ile uçtan uca doğrulamasıdır.

## Yedekleme ve Geri Yükleme
```bash
# Yedek oluştur (memory/ + cache/ → tar.gz + SHA-256)
bash scripts/backup_restore.sh backup

# Yedekleri listele (SHA-256 bütünlük kontrolüyle)
bash scripts/backup_restore.sh list

# Geri yükle (restore öncesi mevcut memory/ otomatik pre-backup alınır)
bash scripts/backup_restore.sh restore backups/pineal_20260901_120000.tar.gz

# Yedek bütünlüğünü doğrula
bash scripts/backup_restore.sh verify backups/pineal_20260901_120000.tar.gz
```
Docker volume ortamında:
```bash
docker run --rm \
  -v pineal_memory:/app/memory \
  -v pineal_cache:/app/cache \
  -v "$(pwd)/backups:/app/backups" \
  pineal bash scripts/backup_restore.sh backup
```
`memory/` — görev kanıt zinciri. **Kayıp geri alınamaz.**
`cache/` — SQLite response cache. Kaybedilirse yeniden doldurulur.

## ⚠ Multi-Replica / Yatay Ölçekleme
`app.state.rooms` ve `_rate_buckets` **process-local** bellekte tutulur.
2+ instance aynı anda çalıştırılmamalıdır:
- Farklı replica'daki aynı `client_id` → ayrı room state → WebSocket kopukluğu
- Rate-limit sayaçları replica başına bağımsız → gerçek limitin N katı istek geçebilir

**İlk production release için `replicas: 1` zorunludur.**
Yatay ölçekleme: paylaşımlı session store (Redis vb.) + sticky session gerektirir.

## Production Kontrol Listesi
| # | Kontrol | Nasıl Doğrulanır |
|---|---|---|
| 1 | `/app/memory` kalıcı volume'a bağlı | Container yeniden başlatma sonrası `GET /api/tasks` aynı görevleri döndürüyor |
| 2 | `PINEAL_TOKEN` tanımlı | `PINEAL_ENV=production` ile tokensız start etmez (`PRODUCTION_AUTH_REQUIRED`) |
| 3 | `OPENROUTER_MAX_SPEND_USD` > 0 | `/health → spend_cap_unlimited: false` |
| 4 | `LIVE_LLM_E2E=1` | Aspasia gerçek yanıt veriyor; telemetride `gateway: true` |
| 5 | `PINEAL_ALLOWED_ORIGINS` explicit | Localhost dışı origin için açıkça belirt |
| 6 | Tek instance | `railway.toml → numReplicas=1` / `docker-compose → replicas: 1` |
| 7 | Yedek alındı ve doğrulandı | `bash scripts/backup_restore.sh backup && verify` |
| 8 | Chromium kurulu | `python -c "from playwright.async_api import async_playwright; print('ok')"` |
| 9 | `/health` HTTP 200 `status: ready` | `curl -sf http://localhost:8000/health \| python3 -m json.tool` |
| 10 | Canlı LLM gate geçti | `OPENROUTER_API_KEY=... LIVE_LLM_E2E=1 python live_llm_gate.py` |

## Bilinçli sınırlar
- Veritabanı yok (JSON bellek) — çoklu kullanıcı/geçmiş sorgulama gerekirse Store soyutlaması eklenecek.
- **FAZ 9 Karar B:** `rust_core/` experimental/optional'dır. CI'da bağımsız derlenip test edilir; Python ürün yoluna bağlı değildir, Docker'a paketlenmez, aktivasyon bayrağı ve ürün karar etkisi yoktur. `/health` ile `/api/telemetry` bu statüyü raporlar. Tauri masaüstü taslağı release ürünü değildir.
- Deneysel API'ler (`/api/experimental/*`) ürün sözleşmesi dışıdır.
- X (Twitter) kazıması devre dışıdır (B4). Instagram kazıması tarayıcı kurulumuna bağlıdır: manuel kurulumda ZORUNLU adım: `python -m playwright install chromium` (Docker imajı otomatik kurar).
