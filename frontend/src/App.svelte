<script lang="ts">
  import { onMount } from 'svelte';
  import { get } from 'svelte/store';
  import { onDestroy } from 'svelte';
  // [BOSS-12] `telemetryEvents` kaldırıldı: hiç render edilmiyordu ve sınırsız büyüyordu.
  import { apiToken, currentApiToken, apiFetch, clientId, wsUrl, logs, taskStatus, isProcessing, powerEngaged, recordEngaged } from './store';
  import { uplinkState } from './lib/telemetry';
  import { currentLang, t, type Language } from './i18n';
  import UnifiedCompactPanel from './components/UnifiedCompactPanel.svelte';
  import CockpitEntry from './components/CockpitEntry.svelte';
  import NeuralTelemetryBoard from './components/visualizers/NeuralTelemetryBoard.svelte';

  let ws: WebSocket | null = null;
  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let disposed = false;
  let lastToken = currentApiToken();

  // Kokpit girişi: tam ortada göz + izometrik süzülen sahne. Her açılışta
  // gösterilir; başlıktaki GÖZ düğmesiyle tekrar açılabilir.
  let showEntry = true;
  function handleCockpitEnter() {
    showEntry = false;
  }
  function reopenCockpitEntry() {
    showEntry = true;
  }

  // [BOSS-12] Ölü kod temizlendi: fetchTelemetry/fetchTasks/deleteTask ve
  // tasksData hiçbir yerden çağrılmıyordu (görev geçmişi UI'de yoktu) — ölü
  // yüzey bırakmak yerine kaldırıldı. Telemetri panosu artık CANLI beslenir.
  type TelemetryPayload = Record<string, unknown>;

  let telemetryData: TelemetryPayload | null = null;
  let telemetryPoll: ReturnType<typeof setInterval> | null = null;

  async function fetchTelemetry() {
    try {
      const res = await apiFetch(`/api/telemetry?client_id=${$clientId}`);
      if (!res.ok) return;
      telemetryData = await res.json();
    } catch (_e) {
      /* ağ hatası: pano son bilinen değeri gösterir, veri uydurulmaz */
    }
  }

  onDestroy(() => {
    if (telemetryPoll) clearInterval(telemetryPoll);
  });


  function switchLang(lang: Language) {
    currentLang.set(lang);
  }

  // RECORD kapalıysa uplink akışı KAYDEDİLMEZ (odometre de durur);
  // görev durumu güncellemeleri kontrol düzlemidir, kayıttan bağımsız akar.
  function recording(): boolean {
    return get(recordEngaged);
  }

  function logLine(level: string, msg: string) {
    if (!recording()) return;
    logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level, msg }]);
  }

  // UPLINK (WebSocket) — otomatik yeniden bağlantı + gerçek kapanma nedenini loglama.
  // Eskiden: tek bağlantı, kopunca bir daha bağlanmaz ve 1008 (yetki) kapanması bile
  // "UPLINK KOPTU" diye gösterilirdi; 401/http hataları da "ağ hatası" sanılırdı.
  function connect() {
    if (disposed) return;
    if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) return;
    try {
      ws = new WebSocket(wsUrl($clientId));
    } catch (_e) {
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      reconnectAttempts = 0;
      uplinkState.set('ONLINE');
      const token = currentApiToken();
      if (token && ws) ws.send(JSON.stringify({ type: 'auth', token }));
      logLine("INFO", "UPLINK KURULDU (FastAPI WebSocket)");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "log") {
          if (!recording()) return;
          logs.update(l => {
            const newLogs = [...l, data];
            if (newLogs.length > 60) newLogs.shift();
            return newLogs;
          });
        } else if (data.event && data.event.event_type) {
          if (recording()) {
            logs.update(l => {
              const evt = data.event;
              const msg = `[${evt.event_type}] ${evt.agent_name || ''} - ${evt.input_summary || evt.step_name || evt.error_message || ''}`;
              const newLogs = [...l, { ts: new Date(data.timestamp).toLocaleTimeString(), level: evt.severity || "INFO", msg: msg }];
              if (newLogs.length > 60) newLogs.shift();
              return newLogs;
            });
          }
        } else if (data.type === "snapshot_update") {
          taskStatus.update(s => ({ ...s, ...data }));
        } else if (data.type === "result") {
          // W4: snapshot bilgisini (runs/planned_agents/damgalar) ezme; birleştir.
          taskStatus.update(s => ({ ...s, ...data }));
          isProcessing.set(false);
          // [BOSS-12] Terminal durum INFO diye yazılamaz: başarısızlık
          // başarı gibi görünüyordu.
          const terminal = String(data.status || "").toLowerCase();
          const okStates = ["completed", "partially_completed"];
          logLine(okStates.includes(terminal) ? "INFO" : "ERROR", "OPERASYON SONUÇLANDI: " + data.status);
        }
      } catch(e) {
        console.error("WS parse error", e);
      }
    };

    ws.onclose = (event) => {
      if (disposed) return;
      uplinkState.set('OFFLINE');
      // POWER kapalıysa kapanış bilinçlidir: log kirliliği ve yeniden bağlanma yok.
      if (!get(powerEngaged)) return;
      // 1008 (policy/auth) ve 1013: sunucu token bekleyip alamadı/doğrulayamadı.
      if (event.code === 1008 || event.code === 1013) {
        logLine("ERROR", "UPLINK YETKİ HATASI: PINEAL_TOKEN eksik/uyuşmuyor — Kasa'dan token girin veya eşleştirin (kod " + event.code + ")");
      } else {
        logLine("ERROR", "UPLINK KOPTU (WebSocket Kapandı) — yeniden bağlanılacak");
      }
      scheduleReconnect();
    };

    ws.onerror = () => {
      /* onclose arkasından gelecek; ayrı log gerekmiyor */
    };
  }

  function scheduleReconnect() {
    if (disposed) return;
    if (reconnectTimer) clearTimeout(reconnectTimer);
    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 15000);
    reconnectAttempts += 1;
    reconnectTimer = setTimeout(connect, delay);
  }

  onMount(() => {
    connect();

    // [BOSS-12] Telemetri panosu canlı beslenir (yoksa pano kurgu moduna düşer).
    fetchTelemetry();
    telemetryPoll = setInterval(fetchTelemetry, 4000);

    // POWER şalteri: kapalı → soketi kapat + yeniden bağlanmayı durdur;
    // açık → sıfırdan bağlan. (İlk abonelikteki true değeri no-op'tur:
    // connect() zaten CONNECTING/OPEN soketi yeniden açmaz.)
    const unsubPower = powerEngaged.subscribe((on) => {
      if (disposed) return;
      if (!on) {
        if (reconnectTimer) clearTimeout(reconnectTimer);
        if (ws) {
          try { ws.close(); } catch (_e) { /* ignore */ }
          ws = null;
        }
        uplinkState.set('OFFLINE');
      } else {
        reconnectAttempts = 0;
        connect();
      }
    });

    // Token değişince (Kasa'dan girildi/temizlendi) soketi yeni kimlikle yeniden bağla.
    const unsub = apiToken.subscribe((value) => {
      if (value === lastToken) return;
      lastToken = value;
      reconnectAttempts = 0;
      if (ws) {
        try { ws.close(); } catch (_e) { /* ignore */ }
        ws = null;
      }
      connect();
    });

    return () => {
      disposed = true;
      unsub();
      unsubPower();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) {
        try { ws.close(); } catch (_e) { /* ignore */ }
        ws = null;
      }
    };
  });
</script>

{#if showEntry}
  <CockpitEntry onEnter={handleCockpitEnter} />
{/if}

<div class="walnut-frame">
  <!-- HEADER & CONTROLS -->
  <header style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid var(--brass-border); padding-bottom: 14px;">
    <div>
      <h1 class="font-cinzel" style="font-size: 22px; font-weight: 800; color: var(--gold); letter-spacing: 0.15em; line-height: 1.2;">
        {t[$currentLang].appTitle}
      </h1>
      <p class="font-cinzel" style="font-size: 11px; color: var(--text-dim); letter-spacing: 0.25em; margin-top: 4px;">
        {t[$currentLang].appSubtitle}
      </p>
    </div>

    <!-- LANGUAGE SWITCHER & BADGE -->
    <div style="display: flex; align-items: center; gap: 12px;">
      <div class="brass-header" style="font-size: 11px; font-weight: 800; letter-spacing: 0.1em; display: flex; align-items: center; gap: 6px;">
        <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; {$uplinkState === 'ONLINE' ? 'background: #10b981; box-shadow: 0 0 6px #10b981;' : 'background: #ef4444; box-shadow: 0 0 6px #ef4444;'}"></span>
        <span>{$uplinkState === 'ONLINE' ? 'ONLINE (ÇEVRİMİÇİ)' : 'OFFLINE (ÇEVRİMDIŞI)'}</span>
      </div>

      <button
        class="btn-dark"
        style="padding: 4px 10px; font-size: 11px; font-weight: 700;"
        on:click={reopenCockpitEntry}
        title="Kokpit girişini (göz) tekrar aç"
      >
        👁 GÖZ
      </button>

      <!-- TR / EN Toggle -->
      <div style="display: flex; background: #0a0705; border: 1px solid var(--brass-border); border-radius: 6px; overflow: hidden; padding: 2px;">
        <button 
          class="btn-dark" 
          style="padding: 4px 10px; font-size: 11px; font-weight: 700; border-radius: 4px; border: none; {$currentLang === 'tr' ? 'background: var(--gold); color: #120b04;' : 'background: transparent; color: var(--text-dim);'}" 
          on:click={() => switchLang('tr')}
        >
          🇹🇷 TR
        </button>
        <button 
          class="btn-dark" 
          style="padding: 4px 10px; font-size: 11px; font-weight: 700; border-radius: 4px; border: none; {$currentLang === 'en' ? 'background: var(--gold); color: #120b04;' : 'background: transparent; color: var(--text-dim);'}" 
          on:click={() => switchLang('en')}
        >
          🇬🇧 EN
        </button>
      </div>
    </div>
  </header>

  <!-- MAIN COCKPIT BODY -->
  <main>
    <UnifiedCompactPanel />
  </main>

  <!-- [BOSS-12] NeuralTelemetryBoard import ediliyordu ama hiç basılmıyordu:
       ölü import + görünmeyen pano. Artık gerçek telemetriyle render edilir. -->
  <section class="telemetry-section">
    <NeuralTelemetryBoard telemetry={telemetryData} />
  </section>


  <!-- FOOTER -->
  <footer style="margin-top: 20px; text-align: center; border-top: 1px solid var(--brass-border); padding-top: 12px;">
    <p class="font-cinzel" style="font-size: 10px; color: var(--text-muted); letter-spacing: 0.25em;">
      {t[$currentLang].footerText}
    </p>
  </footer>
</div>
