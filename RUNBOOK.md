# RUNBOOK — Kurulum, Çalıştırma, Sorun Giderme

## Başlatma
| Yöntem | Komut | Not |
|---|---|---|
| Windows | `baslat.bat` | venv + pip + frontend build (dist yoksa) + uvicorn:8000 |
| Docker | `docker compose up --build` | Playwright/Chromium dahil; `pineal_memory` volume |
| Manuel | `pip install -r requirements.txt` → `cd frontend && npm ci && npm run build` → `uvicorn backend.api:app --port 8000` | |
| Dev (vite) | `frontend/.env`: `VITE_API_BASE=http://127.0.0.1:8000` → `npm run dev` | :5173 → :8000 |

## Anahtarlar (`.env` veya UI Kasası)
- `OPENROUTER_API_KEY` + `LIVE_LLM_E2E=1` → canlı bulut LLM.
- Yerel: `USE_LOCAL_LLM=true`, `LOCAL_LLM_URL=http://localhost:11434/v1`, `LOCAL_LLM_MODEL=...` (anahtar gerekmez).
- `TAVILY_API_KEY`, `SERPAPI_API_KEY`, `EXA_API_KEY` → AutonomousVerifier web doğrulaması (yoksa DuckDuckGo yedeği).
- Vision: `OPENROUTER_VISION_MODEL` — varsayılan `google/gemini-3.7-flash`; VisionAnalyzer (profil fotoğrafları) ve görselli Aspasia isteklerinde kullanılır.
- Model varsayılanları (P2 ekonomik set; fiyatlar OpenRouter promosyonlarına tabi):
  Tier-1 `upstage/solar-pro4` (`OPENROUTER_TIER_1_MODEL`, promo 2026-09-10'a kadar),
  Tier-2 `inclusionai/ling-3.0-flash` (`OPENROUTER_TIER_2_MODEL`).
  Zincirler: depth `solar-pro4 → glm-5.2 → deepseek-v4-pro` · dialogue
  `solar-pro4 → deepseek-v4-flash` · fast `ling-3.0-flash →
  qwen3-235b-a22b-2507` (env: `OPENROUTER_CHAIN_<TASK>`).
- Token kipi: `PINEAL_TOKEN=x` (API/WS korunur) + `frontend/.env` → `VITE_PINEAL_TOKEN=x`.
- Harcama tavanı: `OPENROUTER_MAX_SPEND_USD` (0=kapalı). Aşılırsa `SpendCapExceeded`.

## Sık sorunlar
| Belirti | Neden → Çözüm |
|---|---|
| `Görev durumu: failed`, 0 kanıt | LLM yok: anahtar + `LIVE_LLM_E2E=1` veya yerel model ayarla |
| Aspasia "bağlantıda kırılma" yanıtı | Aynı — zarif fallback; anahtar girilince gerçek yanıt |
| Tarayıcı boş | `frontend/dist` yok → build et; `/src/main.ts` 404 çıkarsa dist eski demektir |
| 429 (initiate/aspasia) | Rate limit — 1 dk bekle (bilinçli koruma) |
| 401 tüm API çağrıları | `PINEAL_TOKEN` tanımlı ama UI/istemci göndermiyor → `VITE_PINEAL_TOKEN` eşle veya token'ı kaldır |
| Scrape 429/403 (Instagram) | Platform limit/cookie: Kasaya güncel cookie gir |
| X (Twitter) hedefi | Kazıma devre dışı (B4): `XScraperUnsupportedError`; WS logunda "DESTEKLENMİYOR" görünür, analiz boş hedefle sürer |
| WS bağlanmıyor | Token kipinde `?token=` gerekli; port 8000 dışındaysa `VITE_API_BASE` tanımla |

## Görev verisi
- Liste: `GET /api/tasks?client_id=...`
- Kalıcı silme (retention): `DELETE /api/tasks/{task_id}?client_id=...` (json kanıt dosyası + aktif snapshot)

## Test / Kalite kapıları
```
ruff check .          # gerçek hata kapısı (E9+F)
pytest -q             # 223 test (bu revizyon itibarıyla): unit+integration+e2e+ws sıra+güvenlik+protokol
                      # güncel sayı: pytest --collect-only -q | tail -1
cd frontend && npm run check && npm run build   # 0 hata + gerçek-app kilidi
```
CI: `.github/workflows/ci.yml` — her push'ta otomatik çalışır: backend (ruff + pytest),
frontend (check + build + dist doğrulama), smoke (uvicorn + curl).

Canlı LLM gate (manuel, gerçek anahtar gerektirir):
```
OPENROUTER_API_KEY=sk-or-v1-... LIVE_LLM_E2E=1 python live_llm_gate.py
```
Kriterler: `completed` + dolu evidence + kritik ajanlarda sıfır UNAVAILABLE
fallback + dolu HolisticProfile + hakem onayı (varsayılan hakem:
`openai/gpt-5.6-sol-pro`; `OPENROUTER_JUDGE_MODEL` ile ezilebilir).
Bu script 360° zincirinin gerçek LLM ile uçtan uca doğrulamasıdır.

## Bilinçli sınırlar
- Veritabanı yok (JSON bellek) — çoklu kullanıcı/geçmiş sorgulama gerekirse Store soyutlaması eklenecek.
- Tauri yok (Masaüstü paket istenirse ayrı faz olarak planlanmalı, `rust_core/` mevcuttur — derlenmeyen/bağlantısız deneysel kod).
- Deneysel API'ler (`/api/experimental/*`) ürün sözleşmesi dışıdır.
- X (Twitter) kazıması devre dışıdır (B4). Instagram kazıması tarayıcı kurulumuna bağlıdır: manuel kurulumda `python -m playwright install chromium` ayrı adımdır (Docker imajı otomatik kurar).
