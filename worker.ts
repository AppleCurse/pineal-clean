// Cloudflare Worker (static assets) — Pages Functions ile AYNI sözleşme.
//
// NEDEN BU DOSYA VAR (ölçüldü, 2026-09-23):
// Depoya bağlı iki Cloudflare projesi (`pineal-clean`, `pineal-gland`)
// WORKERS-tipi servis: PR check'lerinin `details_url`'i
// `dash.cloudflare.com/<acct>/workers/services/view/<name>/production/builds/<id>`
// gösteriyor (Pages değil). Buna karşılık `wrangler.toml` yalnızca Pages
// yapılandırmasıydı (`pages_build_output_dir`, `main`/`[assets]` YOK). Yerelde
// ölçülen sonuç:
//
//   $ npx wrangler deploy --dry-run
//   ✘ [ERROR] There is no JavaScript/TypeScript to deploy ...
//     add `main = "src/index.ts"` veya `[assets] directory = "./dist"`
//
// Yani Workers Builds daha frontend derlemesine geçemeden YAPILANDIRMA
// doğrulamasında ölüyordu. Bu dosya + wrangler.toml'daki `main`/`[assets]`
// o boşluğu kapatır: statik çıktı `frontend/dist`, `/api/*` ve `/ws/*` proxy.
//
// DÜRÜSTLÜK SÖZLEŞMESİ DEĞİŞMEDİ: /api ve /ws davranışı `functions/` altındaki
// Pages handler'larının AYNISIDIR — buraya KOPYALANMADI, import edildi (tek
// sözleşme, iki dağıtım yolu). BACKEND_ORIGIN secret'ı yoksa uydurma yanıt
// verilmez: 502 + `BACKEND_ORIGIN_NOT_CONFIGURED`. Upgrade değilse 426. Uzak uç
// bağlanamazsa istemci soketi KAPATILIR (asılı bağlantı bırakılmaz).

import { onRequest as apiProxy } from "./functions/api/[[path]]";
import { onRequest as wsProxy } from "./functions/ws/[[path]]";

const API_PREFIX = "/api";
const WS_PREFIX = "/ws";

/** `/api/foo/bar` -> ["foo","bar"] (Pages catch-all `params.path` eşleniği). */
function subpath(pathname: string, prefix: string): string[] {
  return pathname
    .slice(prefix.length)
    .split("/")
    .filter((part) => part.length > 0);
}

/** Pages `context` eşleniği: handler'lar yalnız request/env/params kullanıyor. */
function pagesContext(request: Request, env: any, sub: string[]): any {
  return {
    request,
    env,
    params: { path: sub },
    // Worker tarafında karşılığı yoksa dürüst no-op (handler'lar çağırmıyor).
    waitUntil: () => {},
    passThroughOnException: () => {},
  };
}

export default {
  async fetch(request: Request, env: any): Promise<Response> {
    const { pathname } = new URL(request.url);

    if (pathname === API_PREFIX || pathname.startsWith(API_PREFIX + "/")) {
      return apiProxy(pagesContext(request, env, subpath(pathname, API_PREFIX)));
    }

    if (pathname === WS_PREFIX || pathname.startsWith(WS_PREFIX + "/")) {
      return wsProxy(pagesContext(request, env, subpath(pathname, WS_PREFIX)));
    }

    // Geri kalan her şey statik çıktı (frontend/dist) — ASSETS binding'i.
    return env.ASSETS.fetch(request);
  },
};
