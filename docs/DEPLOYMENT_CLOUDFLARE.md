# Cloudflare Dağıtımı — PINEAL Frontend (Workers static assets + Pages yolu)

## Hangi tip? (ölçüldü, 2026-09-23)

Depoya bağlı Cloudflare projeleri **Workers servisi**, Pages değil: PR/commit
check'lerinin `details_url` alanı
`dash.cloudflare.com/<hesap>/workers/services/view/pineal-clean/...` ve
`.../view/pineal-gland/...` gösteriyor. Buna karşılık `wrangler.toml` yalnız
Pages alanı (`pages_build_output_dir`) taşıyordu ve `main`/`[assets]` YOKTU;
ölçülen sonuç:

```text
$ npx wrangler deploy --dry-run
✘ [ERROR] There is no JavaScript/TypeScript to deploy ...
  add `main = "src/index.ts"` veya `[assets] directory = "./dist"`
```

Yani **Workers Builds daha frontend derlenmeden yapılandırma adımında ölüyordu**
(`Workers Builds: pineal-clean` / `pineal-gland` kırmızılarının kök nedeni).

İki tip aynı `wrangler.toml`'da **bir arada olamıyor** (ikisi de ölçüldü):

| Deneme | Sonuç |
|---|---|
| `pages_build_output_dir` üst düzeyde + `[assets] binding = "ASSETS"` | `✘ [ERROR] The name 'ASSETS' is reserved in Pages projects.` |
| `pages_build_output_dir` `[assets]` tablosundan SONRA | TOML gereği o tablonun alanı sayılıyor → `▲ WARNING Unexpected fields found in assets field` |
| Pages'e ayrı config dosyası: `wrangler pages deploy -c wrangler.pages.toml …` | `✘ [ERROR] Pages does not support custom paths for the Wrangler configuration file` |

Bu yüzden kök `wrangler.toml` **Workers-tipi** (`main = "worker.ts"` +
`[assets] directory = "frontend/dist"`, binding `ASSETS`). Pages yolu da
çalışmaya devam ediyor: `npx wrangler pages deploy frontend/dist` komutu çıktı
dizinini ARGÜMAN olarak aldığı için `pages_build_output_dir` gerektirmiyor
(ölçüldü: komut yapılandırma doğrulamasını geçiyor, yalnız `CLOUDFLARE_API_TOKEN`
yokluğunda duruyor).

`worker.ts` proxy mantığını **kopyalamaz**: `/api/*` ve `/ws/*` isteklerini
`functions/api/[[path]].ts` ve `functions/ws/[[path]].ts` handler'larına iletir
(import) — yani iki dağıtım yolu AYNI sözleşmeyi çalıştırır.

Doğrulama (yerelde ölçüldü):

```text
$ npx wrangler deploy --dry-run            → ✨ Read 9 files from the assets directory frontend/dist
                                             binding: env.ASSETS   (uyarı YOK)
$ npx wrangler pages functions build ./functions → ✨ Compiled Worker successfully
$ npm ci && npm run build (kök)            → frontend/dist üretildi, PINEAL-HERETIC işareti var
```

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
├── wrangler.toml                 # Workers: name, compatibility_date, main, [assets]
├── worker.ts                     # Worker girişi; /api,/ws -> functions/ handler'ları
├── functions/
│   ├── api/[[path]].ts
│   └── ws/[[path]].ts
├── package.json                  # kök derleme kabuğu: npm ci --prefix frontend && build
├── package-lock.json             # kök `npm ci` çalışsın diye (CF Workers Builds)
├── .nvmrc                        # 22 — CI ile aynı Node
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
npm ci                              # kök (package-lock.json var; deterministik)
npm run build                       # = npm ci --prefix frontend && vite build → frontend/dist
```

Node sürümü `.nvmrc` (22) ve `package.json > engines.node` (>=20.19 <23) ile
sabittir — CI ile aynı ağaç.

### 3. Backend kökenini secret olarak ata

```bash
# Workers-tipi servis (bu depodaki CF projeleri):
npx wrangler secret put BACKEND_ORIGIN
# > Enter value: https://api.pineal.example.com

# Pages-tipi dağıtım kullanılıyorsa:
npx wrangler pages secret put BACKEND_ORIGIN
```

Secret olarak atanır — `wrangler.toml`'a ya da repo'ya yazılmaz.

### 4. Deploy

```bash
# Workers (statik varlıklar + worker.ts) — CF projelerinin gerçek tipi:
npx wrangler deploy

# veya Pages yolu (çıktı dizini argümanla verilir, functions/ otomatik alınır):
npx wrangler pages deploy frontend/dist
```

Dashboard tabanlı (GitHub integration / Workers Builds) kurulumda: root dizin =
repo kökü, build command = `npm ci && npm run build`, build output =
`frontend/dist`. `wrangler.toml` Workers-tipi olduğu için `wrangler deploy`
yapılandırma doğrulamasından geçer (önceden geçmiyordu — yukarıdaki ölçüm).

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
  kadar; backend uygulama katmanında (`BodySizeLimitMiddleware`)
  1 MiB (1048576 bayt) ile daha sıkı sınırlıdır.
