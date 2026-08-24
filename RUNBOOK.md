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
- Vision: `OPENROUTER_VISION_MODEL` (görselli Aspasia istekleri; varsayılan `google/gemini-3.7-flash`).
- Token kipi: `PINEAL_TOKEN=x` (API/WS korunur) + `frontend/.env` → `VITE_PINEAL_TOKEN=x`.

## Sık sorunlar
| Belirti | Neden → Çözüm |
|---|---|
| `Görev durumu: failed`, 0 kanıt | LLM yok: anahtar + `LIVE_LLM_E2E=1` veya yerel model ayarla |
| Aspasia "bağlantıda kırılma" yanıtı | Aynı — zarif fallback; anahtar girilince gerçek yanıt |
| Tarayıcı boş | `frontend/dist` yok → build et; `/src/main.ts` 404 çıkarsa dist eski demektir |
| 429 (initiate/aspasia) | Rate limit — 1 dk bekle (bilinçli koruma) |
| 401 tüm API çağrıları | `PINEAL_TOKEN` tanımlı ama UI/istemci göndermiyor → `VITE_PINEAL_TOKEN` eşle veya token'ı kaldır |
| Scrape 429/403 | Platform limit/cookie: Kasaya güncel cookie gir |
| WS bağlanmıyor | Token kipinde `?token=` gerekli; port 8000 dışındaysa `VITE_API_BASE` tanımla |

## Görev verisi
- Liste: `GET /api/tasks?client_id=...`
- Kalıcı silme (retention): `DELETE /api/tasks/{task_id}?client_id=...` (json kanıt dosyası + aktif snapshot)

## Test / Kalite kapıları
```
ruff check .          # gerçek hata kapısı (E9+F)
pytest -q             # 189 test: unit+integration+e2e+ws sıra+güvenlik+protokol
cd frontend && npm run check && npm run build   # 0 hata + gerçek-app kilidi
```
CI: `.github/workflows/ci.yml` (token izinleri nedeniyle manuel eklenmelidir — içerik RUNBOOK ekinde/repo geçmişinde).

## Bilinçli sınırlar
- Veritabanı yok (JSON bellek) — çoklu kullanıcı/geçmiş sorgulama gerekirse Store soyutlaması eklenecek.
- Tauri yok (Masaüstü paket istenirse ayrı faz olarak planlanmalı, `rust_core/` mevcuttur).
- Deneysel API'ler (`/api/experimental/*`) ürün sözleşmesi dışıdır.
