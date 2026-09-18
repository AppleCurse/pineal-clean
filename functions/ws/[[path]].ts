// Cloudflare Pages Function — /ws/* → ws(s)://BACKEND_ORIGIN/ws/* proxy.
//
// Neden: telemenetri/odak WebSocket bağlantısı eski deployment'da
// 404 dönüyordu (statik edge'de WS endpoint'i yok). Bu uç upgrade
// el sıkışmasını yapıp iki ucu çift yönlü pompa ile birleştirir.
//
// Kimlik doğrulama yol üzerinden yapılır (/ws/{client_id}); Cloudflare'ın
// istemci WebSocket API'si özel istek başlığı iletmediği için bu tasarım
// header tabanlı auth gerektirmez — bilinçli seçim.
//
// Dürüstlük sözleşmesi: BACKEND_ORIGIN ayarlı değilse 502; upgrade
// değilse 426. Uzak uç bağlanamazsa istemci ucunu KAPATIRIZ (asılı
// bağlantı bırakmayız).

export const onRequest = async (context: any) => {
  const origin: string | undefined = context.env.BACKEND_ORIGIN;
  if (!origin) {
    return new Response(
      JSON.stringify({
        error: {
          code: "BACKEND_ORIGIN_NOT_CONFIGURED",
          message:
            "Bu deployment için BACKEND_ORIGIN secret'ı ayarlanmamış. " +
            "npx wrangler pages secret put BACKEND_ORIGIN",
        },
      }),
      { status: 502, headers: { "Content-Type": "application/json" } },
    );
  }

  const upgrade = (context.request.headers.get("upgrade") || "").toLowerCase();
  if (!upgrade.includes("websocket")) {
    return new Response("Bu uç yalnızca WebSocket upgrade kabul eder.", { status: 426 });
  }

  const subpath: string[] = context.params.path || [];
  const url = new URL(context.request.url);
  const bare = origin.replace(/\/+$/, "");
  let wsTarget: string;
  if (bare.startsWith("https://")) {
    wsTarget = "wss://" + bare.slice("https://".length);
  } else if (bare.startsWith("http://")) {
    wsTarget = "ws://" + bare.slice("http://".length);
  } else if (bare.startsWith("wss://") || bare.startsWith("ws://")) {
    wsTarget = bare;
  } else {
    wsTarget = "wss://" + bare;
  }
  wsTarget += "/ws/" + subpath.join("/") + (url.search || "");

  const upstream: WebSocket = new WebSocket(wsTarget);

  // Pair'in BİR ucu accept edilir ve pompa ile kullanılır; DİĞER ucu
  // Response'a (istemciye) verilir. Kabul edilmiş ucu döndürmek
  // geçersizdir.
  const [pipeEnd, clientEnd] = Object.values(new WebSocketPair()) as [
    WebSocket,
    WebSocket,
  ];
  pipeEnd.accept();

  const guard = (w: WebSocket) => () => {
    if (w.readyState === WebSocket.OPEN || w.readyState === WebSocket.CONNECTING) {
      try {
        w.close();
      } catch {
        /* zaten kapalı */
      }
    }
  };

  // Çift yönlü pompa: mesajları ve kapanış olaylarını karşılıklı ilet.
  const pump = (from: WebSocket, to: WebSocket) => {
    from.addEventListener("message", (ev: any) => {
      if (to.readyState === WebSocket.OPEN) to.send(ev.data);
    });
    from.addEventListener("close", guard(to));
    from.addEventListener("error", guard(to));
  };
  pump(pipeEnd, upstream);
  pump(upstream, pipeEnd);

  // Yakın uca 101 dön; uzak uç asla bağlanamazsa guard istemciyi kapatır.
  return new Response(null, { status: 101, webSocket: clientEnd });
};
