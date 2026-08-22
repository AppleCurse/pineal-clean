<script lang="ts">
  import { onMount } from 'svelte';
  import { clientId, WS_BASE, logs, taskStatus, isProcessing, telemetryEvents } from './store';

  import UnifiedCompactPanel from './components/UnifiedCompactPanel.svelte';
  let ws: WebSocket;

  onMount(() => {
    ws = new WebSocket(`${WS_BASE}/ws/${$clientId}`);

    ws.onopen = () => {
      logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "INFO", msg: "UPLINK KURULDU (FastAPI WebSocket)"}]);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "log") {
          logs.update(l => {
            const newLogs = [...l, data];
            if (newLogs.length > 50) newLogs.shift();
            return newLogs;
          });
        } else if (data.event && data.event.event_type) {
          telemetryEvents.update(arr => [...arr, data]);
          logs.update(l => {
            const evt = data.event;
            const msg = `[${evt.event_type}] ${evt.agent_name} - ${evt.input_summary || evt.step_name || evt.error_message || ''}`;
            const newLogs = [...l, { ts: new Date(data.timestamp).toLocaleTimeString(), level: evt.severity || "INFO", msg: msg }];
            if (newLogs.length > 50) newLogs.shift();
            return newLogs;
          });
        } else if (data.type === "snapshot_update") {
          taskStatus.update(s => ({ ...s, ...data }));
        } else if (data.type === "result") {
          taskStatus.set(data);
          isProcessing.set(false);
          logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "INFO", msg: "OPERASYON DURUMU DEĞİŞTİ: " + data.status}]);
        }
      } catch(e) {
        console.error("WS parse error", e);
      }
    };

    ws.onclose = () => {
      logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "ERROR", msg: "UPLINK KOPTU (WebSocket Kapandı)"}]);
    };

    return () => {
      if (ws) ws.close();
    };
  });
</script>

<main class="app-container p-4 w-full">
  <div class="walnut rounded p-4 app-box mx-auto" style="max-width: 1680px;">
    
    <!-- HEADER -->
    <div class="flex justify-center mb-4">
      <div class="brass px-4 py-2 text-center" style="border-radius: 4px;">
        <div class="font-cinzel font-bold" style="font-size: 20px; letter-spacing: 0.25em;">PINEAL-HERETIC v2.0</div>
        <div class="font-cinzel" style="font-size: 11px; letter-spacing: 0.5em; opacity: 0.8;">VINTAGE STATION • UNIFIED • COMPLETE • AGENT DECK ACTIVE</div>
      </div>
    </div>

    <!-- UNIFIED COMPACT MODEL -->
    <UnifiedCompactPanel />

    <div class="mt-4 text-center font-cinzel" style="font-size: 8px; letter-spacing: 0.4em; opacity: 0.6;">
      PINEAL-HERETIC VINTAGE STATION • FAZ 3 TAMAMLANDI • EKSİKSİZ • AJANLARLA KONUŞMA AKTİF • KURŞUN GEÇİRMEZ
    </div>
  </div>
</main>

<style>
  .app-container {
    width: 100%;
    box-sizing: border-box;
  }
  .flex-col {
    display: flex;
    flex-direction: column;
  }
  .mx-auto {
    margin-left: auto;
    margin-right: auto;
  }
</style>
