<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { get } from 'svelte/store';
  import {
    apiToken, currentApiToken, apiFetch, clientId, wsUrl, logs, taskStatus,
    isProcessing, powerEngaged, recordEngaged
  } from './store';
  import { uplinkState } from './lib/telemetry';
  import AtlasPinealCockpit from './components/AtlasPinealCockpit.svelte';
  import NeuralTelemetryBoard from './components/visualizers/NeuralTelemetryBoard.svelte';

  let ws: WebSocket | null = null;
  let reconnectAttempts = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let disposed = false;
  let lastToken = currentApiToken();
  let telemetryData: any = null;
  let telemetryPoll: any = null;

  async function fetchTelemetry() {
    try {
      const res = await apiFetch('/api/telemetry');
      if (res.ok) telemetryData = await res.json();
    } catch (_e) {}
  }

  function recording(): boolean {
    return get(recordEngaged);
  }

  function logLine(level: string, msg: string) {
    if (!recording()) return;
    logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level, msg }]);
  }

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
          logs.update(l => [...l, data].slice(-80));
        } else if (data.event && data.event.event_type) {
          if (recording()) {
            const evt = data.event;
            const msg = `[${evt.event_type}] ${evt.agent_name || ''} - ${evt.input_summary || evt.step_name || evt.error_message || ''}`;
            logs.update(l => [...l, { ts: new Date(data.timestamp).toLocaleTimeString(), level: evt.severity || "INFO", msg }].slice(-80));
          }
        } else if (data.type === "snapshot_update") {
          taskStatus.update(s => ({ ...s, ...data }));
        } else if (data.type === "result") {
          taskStatus.update(s => ({ ...s, ...data }));
          isProcessing.set(false);
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
      if (!get(powerEngaged)) return;
      scheduleReconnect();
    };

    ws.onerror = () => {};
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

    const unsubPower = powerEngaged.subscribe((on) => {
      if (disposed) return;
      if (!on) {
        if (reconnectTimer) clearTimeout(reconnectTimer);
        if (ws) {
          try { ws.close(); } catch (_e) {}
          ws = null;
        }
        uplinkState.set('OFFLINE');
      } else {
        reconnectAttempts = 0;
        connect();
      }
    });

    const unsubToken = apiToken.subscribe((value) => {
      if (value === lastToken) return;
      lastToken = value;
      reconnectAttempts = 0;
      if (ws) {
        try { ws.close(); } catch (_e) {}
        ws = null;
      }
      connect();
    });

    return () => {
      disposed = true;
      if (telemetryPoll) clearInterval(telemetryPoll);
      unsubToken();
      unsubPower();
      if (reconnectTimer) clearTimeout(reconnectTimer);
      if (ws) {
        try { ws.close(); } catch (_e) {}
        ws = null;
      }
    };
  });
</script>

<main class="fullscreen-cockpit-viewport">
  <AtlasPinealCockpit />

  <!-- Adli Telemetri & Sözleşme Köprüsü -->
  <div style="display: none;" aria-hidden="true">
    <NeuralTelemetryBoard telemetry={telemetryData} />
  </div>
</main>

<style>
  .fullscreen-cockpit-viewport {
    width: 100vw;
    height: 100vh;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #000;
    overflow: hidden;
  }
</style>
