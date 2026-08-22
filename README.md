# PINEAL-HERETIC v2.0

Sosyal medya profillerini (Instagram / X) anonim tarayıp **kanıta dayalı** psikolojik
profil analizi yapan, LLM destekli, tek kullanıcılı yerel bir analiz istasyonudur.
Kararları `PinealExecutor` + `CognitiveRouter` verir; **Aspasia** bir karar verici
değil, sistem durumunu ve telemetriyi açıklayan gözlemci/personadır.

> Bu depo 2026-08-22 tarihinde adli röntgenden geçirilmiş; sahte demo arayüz,
> canlı 500 veren Aspasia endpoint'i, ölü manipülasyon motorları ve olmayan
> Rust/Tauri katmanı (4C kararı) temizlenmiştir. Ayrıntı: commit geçmişi.

---

## Gerçek Sistem Mimarisi (koddan doğrulanmış)

```
Svelte UI  (frontend/dist — FastAPI aynı origin'de servis eder)
   │  REST (/api/*)         │  WebSocket (/ws/{client_id})
   ▼                        ▼
FastAPI (backend/api.py)
   ├─ PinealExecutor (agent_core/task_executor.py)   ← durum makinesi
   │    ├─ CognitiveRouter  (rota: hangi ajanlar çalışacak)
   │    ├─ UncertaintyEngine (güven < 0.6 → HALT)
   │    ├─ Ajanlar: mirror_truth · autonomous_verifier · human_behavior
   │    │          passion_mapper · friction_detector · cognitive_profiler
   │    │          resonance_calc · pattern_interrupt · resonance_synthesizer
   │    ├─ CanonicalMemory (memory/*.json — kanıt zinciri)
   │    └─ Telemetry events ──► FIFO kuyruk ──► WebSocket (sıralı teslim)
   ├─ AspasiaChief (gözlemci; /api/aspasia/chat)
   ├─ ShadowExecutor / DialogueManager / InterpreterAgent (deneysel API'ler)
   └─ LLMGateway ──► OpenRouter (LIVE_LLM_E2E=1 + anahtar) veya Ollama (yerel)
```

**Bileşenlerin konumu:** Frontend `frontend/` · Backend `backend/api.py` ·
Çekirdek `agent_core/` · Telemetri şeması `agent_core/schemas/telemetry.py` ·
Scraper'lar `scraper.py` (X) ve `agent_core/scraper/instagram_ghost.py` (IG) ·
Bellek `agent_core/services/canonical_memory.py` (JSON; veritabanı yoktur — bilinçli karar).

---

## Kurulum

### A) Windows (tek komut)
```bat
baslat.bat
```
venv kurar, bağımlılıkları indirir, frontend'i derler (dist yoksa) ve
`http://localhost:8000` üzerinde ayağa kaldırır.

### B) Docker
```bash
cp .env.example .env      # anahtarları doldurun (opsiyonel)
docker compose up --build
```

### C) Manuel
```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cd frontend && npm ci && npm run build && cd ..
uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

Geliştirme (vite:5173 → backend:8000): `frontend/.env` içine
`VITE_API_BASE=http://127.0.0.1:8000` yazıp `npm run dev`.

---

## Yapılandırma (`.env`)

| Değişken | Anlamı |
|---|---|
| `OPENROUTER_API_KEY` | LLM anahtarı. **Yoksa** pipeline ilk LLM'li ajanda durur (halüsinasyon önleme, tasarımdır). |
| `LIVE_LLM_E2E` | `1` değilken dış LLM çağrıları kod tarafından reddedilir. Canlı analiz için `1` yapın. |
| `USE_LOCAL_LLM`, `LOCAL_LLM_URL`, `LOCAL_LLM_MODEL` | Ollama/LM Studio gibi yerel modeller (anahtar gerekmez). |
| `TAVILY_API_KEY` | AutonomousVerifier için web araması (opsiyonel; yoksa doğrulama `UNVERIFIED` döner). |

Anahtarlar UI'daki **Kasa (Vault)** panelinden de girilebilir (`.pineal_vault.json`).

---

## Testler
```bash
pytest               # 100+ test: birim + entegrasyon + E2E smoke + WS sıralama
cd frontend && npm run check && npm run build   # 0 hata beklenir
```

## Sık Görülen Sorunlar
- **"Görev durumu: failed"** → LLM anahtarı yok veya `LIVE_LLM_E2E=1` değil (veya
  yerel model ayarlı değil). Kasaya anahtar girin.
- **Tarayıcı boş sayfa** → `frontend/dist` yok: `cd frontend && npm ci && npm run build`.
- **Scrape hatası (429/403)** → hedef platform rate-limit/cookie sorunu; Kasa'ya güncel cookie girin.

## Kullanım Sınırları
Bu yazılım araştırma ve analitik amaçlıdır; kişisel veri işler — bulunduğunuz
yargı alanındaki yasalara ve platform şartlarına uymak kullanıcının sorumluluğundadır.
Ürün kimliği "sahici iletişim köprüsü"dür; manipülasyon motorları 4C/ADIM-2
temizliğiyle kaldırılmıştır.

## Güvenlik (FAZ 3)

| Özellik | Nasıl |
|---|---|
| **Token kipi** | `.env`'de `PINEAL_TOKEN` tanımlayın → tüm `/api/*` uçları `X-API-Key` başlığı ister (401), WebSocket `?token=...` ister. Boş bırakılırsa sistem açık kipte çalışır (yerel araç). UI tarafı için `frontend/.env`'de `VITE_PINEAL_TOKEN` aynı değeri alır. |
| **CORS** | Varsayılan yalnızca localhost; `PINEAL_ALLOWED_ORIGINS` ile genişletilir. |
| **Rate limit** | `POST /api/initiate` 5/dk, `POST /api/aspasia/chat` 20/dk → `429 {"error":{...}}`. |
| **Hata modeli** | Tüm hatalar tutarlı biçimde `{"error": {"code", "message"}}` döner. |
| **Sır koruması** | API anahtarı yalnızca gateway belleğinde yaşar; loglara/telemetriye sızmaz (`test_no_secret_leak.py` kilidi). |
| **Vision** | Aspasia'ya görsel yüklenirse `OPENROUTER_VISION_MODEL` (varsayılan: llama-3.2-90b-vision) ile multimodal istek atılır. |

**Deneysel API'ler:** `/api/experimental/shadow/*`, `/api/experimental/chat/respond`, `/api/experimental/interpreter/execute` — ürün yüzeyi değildir, UI'dan çağrılmaz.

**CI:** `ruff` (gerçek hata kapısı) + `pytest` + `svelte-check` + `vite build` (sahte artifact regresyon kilidi) + uvicorn smoke testi.
