# Cloudflare Pages Dağıtımı — PINEAL Frontend

## Sorun (eski durum)

Frontend Cloudflare Pages'e statik olarak dağıtılmıştı ama:

- `/api/*` istekleri **proxy'lenmiyordu** → statik edge 404 dönüyordu.
- `/ws/{client_id}` WebSocket ucu edge'de yoktu → telemetri asla bağlanamıyordu.
- Backend kökeni hiçbir yerde tanımlı değildi.

## Mimari

```
Tarayıcı
   │  /api/*  (HTTPS)         /ws/*  (WSS upgrade)
   ▼
Cloudflare Pages
   ├─ frontend/dist   → statik dosyalar (Vite/Svelte build)
   ├─ functions/api/[[path]].ts  → BACKEND_ORIGIN/api/*  (HTTP proxy)
   └─ functions/ws/[[path]].ts   → wss://BACKEND_ORIGIN/ws/*  (WS proxy)
                                       │
                                       ▼
                              FastAPI backend (Railway / özel sunucu)
```

- **HTTP proxy** (`functions/api/[[path]].ts`): metod, body, header'lar
  (hop-by-hop hariç) ve durum kodu birebir taşınır; backend'in
  yönlendirmeleri (3xx) müdahalesiz geçirilir.
- **WS proxy** (`functions/ws/[[path]].ts`): upgrade el sıkışması yapılır,
  iki uç `WebSocketPair` + çift yönlü pompa ile birleştirilir. Kimlik
  doğrulama **yol üzerinden** yapılır (`/ws/{client_id}`) — Cloudflare'ın
  istemci WebSocket API'si özel header iletmediği için tasarım header
  tabanlı auth gerektirmez (bilinçli seçim).
- **Dürüstlük sözleşmesi**: `BACKEND_ORIGIN` secret'ı ayarlı değilse her iki
  uç da 502 + `BACKEND_ORIGIN_NOT_CONFIGURED` döndürür (uydurma davranış
  yok). Upgrade olmayan istek 426 alır.

## Yerleşim (önemli)

Cloudflare konvansiyonu gereği `functions/` dizini **`wrangler.toml` ile
aynı kökte** (repo kökü) olmalıdır. `frontend/` içine konursa deploy'da
tanınmaz.

```
<repo-root>
├── wrangler.toml                 # name, compatibility_date, pages_build_output_dir
├── functions/
│   ├── api/[[path]].ts
│   └── ws/[[path]].ts
├── frontend/                     # Vite projesi
│   └── dist/                     # build çıktısı (build edilmiş hali)
└── ...
```

## Adımlar

### 1. Backend'i hazırla

FastAPI backendi bir kökende çalışsın (Railway, Fly, kendi sunucunuz).
Köken URL'i not edin, ör. `https://api.pineal.example.com`.

CORS: backend `backend/api.py` içinde `CORSMiddleware` kullanır;
Cloudflare origin'i (`https://<subdomain>.pages.dev`) `allowed_origins`
listesinde olmalıdır. Aynı şekilde WS handshake'i CORS'a tabi değildir
(farklı origin) — proxy aynı edge üzerinden ilerlediği için tarayıcı
açısından origin zaten Pages origin'idir.

### 2. Frontend'i build et

```bash
npm --prefix frontend install
npm --prefix frontend run build     # → frontend/dist
```

### 3. Backend kökenini secret olarak ata

```bash
npx wrangler pages secret put BACKEND_ORIGIN
# > Enter value: https://api.pineal.example.com
```

Secret olarak atanır — `wrangler.toml`'a ya da repo'ya yazılmaz.

### 4. Deploy

```bash
npx wrangler pages deploy frontend/dist
```

Dashboard tabanlı (GitHub integration) kurulumda da aynı sonuç alınır:
root dizin = repo kökü, build output = `frontend/dist`; `functions/`
dizini root'ta olduğu için otomatik alınır.

## Doğrulama

```bash
# 1) API proxy
curl -s https://<sub>.pages.dev/api/health
# → backend'in /api/health yanıtı

# 2) API proxy — ayar yokken dürüst 502 (BACKEND_ORIGIN secret'ı
#    geçici olarak kaldırılıp yeniden deploy edilerek test edilir)
curl -s https://<sub>.pages.dev/api/health
# → {"error":{"code":"BACKEND_ORIGIN_NOT_CONFIGURED",...}}  (502)

# 3) WebSocket — tarayıcıda:
#    wss://<sub>.pages.dev/ws/<client_id> bağlantısı kurulmalı
#    (upgrade olmayan istek: 426)
curl -s -i https://<sub>.pages.dev/ws/abc
# → HTTP/2 426
```

## Operasyon notları

- **Secret rotasyonu**: `npx wrangler pages secret put BACKEND_ORIGIN`
  (yeniden) → yeni deployment ile aktif olur.
- **Backend erişilemezse**: HTTP uç `502 BACKEND_UNREACHABLE` döner;
  WS uç istemci bağlantısını kapatır (asılı bağlantı bırakmaz).
- **Rate limiting / WAF**: Cloudflare dashboard'daki WAF kuralları
  proxy'lenen uçlara da uygulanır (edge, backend'in önünde).
- **Limit**: Cloudflare'ın ücretsiz katmanında istek gövdesi 100 MB'a
  kadar; backend `Dockerfile` CMD'sinde `--limit-max-request-size
  1048576` (1 MiB) ile daha sıkı sınırlıdır.
