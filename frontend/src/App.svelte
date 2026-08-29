<script lang="ts">
  import { onMount } from 'svelte';
  import { clientId, wsUrl, logs, taskStatus, isProcessing, telemetryEvents } from './store';
  import { currentLang, t, type Language } from './i18n';
  import UnifiedCompactPanel from './components/UnifiedCompactPanel.svelte';

  let ws: WebSocket;

  let telemetryData = null;
  let tasksData = null;

  async function fetchTelemetry() {
    try {
      let res = await fetch('/api/telemetry');
      telemetryData = await res.json();
    } catch(e) {}
  }
  
  async function fetchTasks() {
    try {
      let res = await fetch(`/api/tasks?client_id=${$clientId}`);
      tasksData = await res.json();
    } catch(e) {}
  }
  
  async function deleteTask(taskId) {
    try {
      await fetch(`/api/tasks/${taskId}?client_id=${$clientId}`, {method: 'DELETE'});
      fetchTasks();
    } catch(e) {}
  }


  function switchLang(lang: Language) {
    currentLang.set(lang);
  }

  onMount(() => {
    ws = new WebSocket(wsUrl($clientId));

    ws.onopen = () => {
      logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "INFO", msg: "UPLINK KURULDU (FastAPI WebSocket)"}]);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === "log") {
          logs.update(l => {
            const newLogs = [...l, data];
            if (newLogs.length > 60) newLogs.shift();
            return newLogs;
          });
        } else if (data.event && data.event.event_type) {
          telemetryEvents.update(arr => [...arr, data]);
          logs.update(l => {
            const evt = data.event;
            const msg = `[${evt.event_type}] ${evt.agent_name || ''} - ${evt.input_summary || evt.step_name || evt.error_message || ''}`;
            const newLogs = [...l, { ts: new Date(data.timestamp).toLocaleTimeString(), level: evt.severity || "INFO", msg: msg }];
            if (newLogs.length > 60) newLogs.shift();
            return newLogs;
          });
        } else if (data.type === "snapshot_update") {
          taskStatus.update(s => ({ ...s, ...data }));
        } else if (data.type === "result") {
          // W4: snapshot bilgisini (runs/planned_agents/damgalar) ezme; birleştir.
          taskStatus.update(s => ({ ...s, ...data }));
          isProcessing.set(false);
          logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "INFO", msg: "OPERASYON TAMAMLANDI: " + data.status}]);
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
        <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #10b981; box-shadow: 0 0 6px #10b981;"></span>
        <span>ONLINE</span>
      </div>

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

  <!-- TELEMETRY & TASKS DEBUG -->
  <div style="border-top: 1px solid var(--brass-border); padding: 12px; margin-top: 10px;">
    <div style="display:flex; gap:10px; margin-bottom: 10px;">
      <button class="btn-dark" on:click={fetchTelemetry}>[ GET TELEMETRY ]</button>
      <button class="btn-dark" on:click={fetchTasks}>[ GET TASKS ]</button>
    </div>
    
    {#if telemetryData}
      <div style="background: #111; padding:10px; border-radius: 4px; border: 1px solid #333; font-size: 11px;">
        <h4 style="margin: 0 0 5px 0; color:var(--gold);">TELEMETRY:</h4>
        <pre style="margin:0; color: #ccc;">{JSON.stringify(telemetryData, null, 2)}</pre>
      </div>
    {/if}

    {#if tasksData}
      <div style="background: #111; padding:10px; border-radius: 4px; border: 1px solid #333; font-size: 11px; margin-top: 10px;">
        <h4 style="margin: 0 0 5px 0; color:var(--gold);">TASKS (RETENTION):</h4>
        {#each tasksData.tasks as task}
           <div style="display:flex; gap:10px; margin-bottom:5px; align-items:center;">
              <span>{task.task_id} ({task.evidence_count} evidence)</span>
              <button class="btn-dark" style="color:red; border: 1px solid red; padding: 2px 6px;" on:click={() => deleteTask(task.task_id)}>DELETE</button>
           </div>
        {/each}
        {#if tasksData.tasks.length === 0}
          <p style="margin:0; color:#ccc;">No tasks found.</p>
        {/if}
      </div>
    {/if}
  </div>


  <!-- FOOTER -->
  <footer style="margin-top: 20px; text-align: center; border-top: 1px solid var(--brass-border); padding-top: 12px;">
    <p class="font-cinzel" style="font-size: 10px; color: var(--text-muted); letter-spacing: 0.25em;">
      {t[$currentLang].footerText}
    </p>
  </footer>
</div>
