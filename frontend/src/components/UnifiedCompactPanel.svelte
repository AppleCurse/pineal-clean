<script lang="ts">
  import { onMount, afterUpdate } from 'svelte';
  import { clientId, API_BASE, WS_BASE, isProcessing, logs, taskStatus, telemetryEvents } from '../store';
  
  // ==========================================
  // TARGET & ENGINE TELEMETRY (TargetPanel)
  // ==========================================
  export let targetUrl = "";
  export let userRituals = "";
  export let userPlaylist = "";
  export let userEnvies = "";
  let localModelActive = false;
  let isSettingModel = false;
  let selectedLocalModel = "dolphin-llama3";

  async function toggleLocalModel() {
    isSettingModel = true;
    localModelActive = !localModelActive;
    try {
      const res = await fetch(`${API_BASE}/api/vault`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: $clientId, use_local: localModelActive, local_model: selectedLocalModel })
      });
      if (!res.ok) throw new Error("Ağ hatası");
      logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "INFO", msg: `LOKAL MODEL: ${localModelActive ? 'AKTİF ('+selectedLocalModel+')' : 'PASİF'}`}]);
    } catch(err: any) {
      localModelActive = !localModelActive;
      logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "ERROR", msg: `MODEL SEÇİM HATASI: ${err.message}`}]);
    } finally {
      isSettingModel = false;
    }
  }

  async function updateLocalModelOnly() {
    try {
      await fetch(`${API_BASE}/api/vault`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: $clientId, use_local: localModelActive, local_model: selectedLocalModel })
      });
      logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "INFO", msg: `ASPASIA YEREL MODELİ: ${selectedLocalModel}`}]);
    } catch(err: any) {
      console.error("Model güncellenemedi", err);
    }
  }

  export async function triggerAnalysis() {
    if (!targetUrl) return;
    isProcessing.set(true);
    try {
      const res = await fetch(`${API_BASE}/api/initiate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          client_id: $clientId,
          url: targetUrl,
          scraper_type: "cross",
          rituals: userRituals,
          playlist: userPlaylist,
          envies: userEnvies,
          aggressiveness: 1.0,
          evidence_th: 3
        })
      });
      if (!res.ok) throw new Error("API hatası: " + res.statusText);
      logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "INFO", msg: `ANALİZ EMRİ GÖNDERİLDİ: ${targetUrl}`}]);
    } catch (e: any) {
      logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "ERROR", msg: `HATA: ${e.message}`}]);
      isProcessing.set(false);
    }
  }

  // ==========================================
  // VAULT (VaultPanel)
  // ==========================================
  let apiKey = "";
  let cookie = "";
  let vaultStatusText = "KEYSTORE • READY";
  let isSealing = false;

  async function sealCredentials() {
    isSealing = true;
    vaultStatusText = "SAVING...";
    try {
      const payload: any = { client_id: $clientId };
      if (apiKey) payload.api_key = apiKey;
      if (cookie) payload.x_cookie = cookie;
      const res = await fetch(`${API_BASE}/api/vault`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Connection error");
      vaultStatusText = "KEYSTORE • ACTIVE";
      apiKey = "";
      cookie = "";
    } catch(err: any) {
      vaultStatusText = "ERROR";
    } finally {
      isSealing = false;
    }
  }

  // ==========================================
  // ASPASIA CHAT & COMMAND (AspasiaPanel)
  // ==========================================
  let messages: {sender: string, text: string}[] = [
    { sender: 'ASPASIA', text: 'Sistem çevrimiçi. Emirlerinizi bekliyorum şefim.' }
  ];
  let inputMessage = "";
  let chatContainer: HTMLElement;
  let isSending = false;
  let isListening = false;
  let attachedImage: string | null = null;
  let fileInput: HTMLInputElement;
  let activeAgentId = 'ASPASIA';

  function speak(text: string) {
    if (!('speechSynthesis' in window)) return;
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = 'tr-TR';
    utterance.rate = 1.1;
    const femaleVoice = window.speechSynthesis.getVoices().find(v => v.lang.includes('tr') && v.name.includes('Female'));
    if (femaleVoice) utterance.voice = femaleVoice;
    window.speechSynthesis.speak(utterance);
  }

  function toggleListen() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) return alert("Ses tanıma desteklenmiyor.");
    const SpeechRecognition = (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognition();
    recognition.lang = 'tr-TR';
    recognition.onstart = () => { isListening = true; };
    recognition.onresult = (e: any) => { inputMessage = e.results[0][0].transcript; sendMessage(); };
    recognition.onerror = () => { isListening = false; };
    recognition.onend = () => { isListening = false; };
    recognition.start();
  }

  function handleImageUpload(e: Event) {
    const target = e.target as HTMLInputElement;
    if (target.files && target.files[0]) {
      const reader = new FileReader();
      reader.onload = (ev) => { attachedImage = ev.target?.result as string; };
      reader.readAsDataURL(target.files[0]);
    }
  }

  async function sendMessage() {
    if ((!inputMessage.trim() && !attachedImage) || isSending) return;
    const displayMsg = attachedImage ? `[GÖRSEL] ${inputMessage}` : inputMessage;
    messages = [...messages, { sender: 'SİZ', text: displayMsg }];
    
    let currentInput = inputMessage;
    let currentImage = attachedImage;
    inputMessage = ""; attachedImage = null; isSending = true;
    
    try {
      const payload: any = { client_id: $clientId, user_message: currentInput };
      if (currentImage) payload.image_data = currentImage;
      const endpoint = activeAgentId === 'ASPASIA' ? '/api/aspasia/chat' : '/api/executor/intervene';
      // Aspasia is an observer, no direct commands. Only executor commands handled on backend (if any)
      if (activeAgentId !== 'ASPASIA') payload.action_type = `DIRECT_CMD_${activeAgentId}`;

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Ağ geçidi kapalı");
      const data = await res.json();
      messages = [...messages, { sender: activeAgentId, text: data.message }];
      speak(data.message);
      
      // MÜDAHALE (INTERVENTION) KONTROLÜ
      if (data.action && data.action.action_type) {
          try {
              await fetch(`${API_BASE}/api/executor/intervene`, {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({
                      client_id: $clientId,
                      action_type: data.action.action_type,
                      target_agent: data.action.target_agent || null,
                      parameters: data.action.parameters || {}
                  })
              });
              messages = [...messages, {
                  sender: 'SİSTEM',
                  text: `KOMUT İCRA EDİLDİ: ${data.action.action_type}${data.action.target_agent ? ' → ' + data.action.target_agent : ''}`
              }];
          } catch (e) {
              console.error("Müdahale komutu gönderilemedi:", e);
          }
      }
      
    } catch (error: any) {
      messages = [...messages, { sender: 'SİSTEM', text: `HATA: ${error.message}` }];
    } finally {
      isSending = false;
    }
  }

  async function sendCommand(actionType: string) {
    // Disabled in Observer mode.
  }

  function explainState() {
    activeAgentId = 'ASPASIA';
    inputMessage = 'Şu anki durumu bana özetler misin? Telemetri ne söylüyor? Neden bu aşamadayız?';
    sendMessage();
  }

  function handleKeydown(e: KeyboardEvent) { if (e.key === 'Enter') sendMessage(); }

  // ==========================================
  // FREQUENCY (FrequencyPanel)
  // ==========================================
  let ritualMatchScore = 0;
  let playlistResonance = 0;
  let envyIntensity = 0;

  // ==========================================
  // AGENT FLOW (AgentFlowPanel)
  // ==========================================
  const agentList = [
    { id: "mirror_truth", name: "MIRROR TRUTH", colorHex: "#16a34a" },
    { id: "autonomous_verifier", name: "VERIFIER", colorHex: "#9333ea" },
    { id: "human_behavior", name: "HUMAN BEHAVIOR", colorHex: "#d97706" },
    { id: "resonance_calc", name: "RESONANCE CALC", colorHex: "#2563eb" },
    { id: "pattern_interrupt", name: "PATTERN INTERRUPT", colorHex: "#dc2626" }
  ];
  let runs: Record<string, any> = {};
  let currentAgent = "";
  let overallConfidence = 0;
  let plannedAgents: string[] = [];
  let completedAgents: string[] = [];
  let haltedReason: string | null = null;
  let taskState = "IDLE";
  let taskId = "";

  $: {
    if ($taskStatus) {
      if ($taskStatus.task_id) taskId = $taskStatus.task_id;
      if ($taskStatus.status) taskState = $taskStatus.status;
      if ($taskStatus.planned_agents) plannedAgents = $taskStatus.planned_agents;
      if ($taskStatus.completed_agents) completedAgents = $taskStatus.completed_agents;
      if ($taskStatus.halted_reason !== undefined) haltedReason = $taskStatus.halted_reason;

      if ($taskStatus.reso) {
        ritualMatchScore = ($taskStatus.reso.ritual_match_score || 0) * 100;
        playlistResonance = ($taskStatus.reso.playlist_resonance || 0) * 100;
        envyIntensity = ($taskStatus.reso.envy_intensity || 0) * 100;
      }
      if ($taskStatus.runs) {
        runs = $taskStatus.runs;
        let lastConf = 0;
        Object.values(runs).forEach(r => { if (r.confidence !== undefined && r.confidence !== null) lastConf = r.confidence; });
        overallConfidence = lastConf;
      }
      if ($taskStatus.current_agent) currentAgent = $taskStatus.current_agent;
    }
  }

  // ==========================================
  // RADAR (RadarPanel)
  // ==========================================
  let recCounter = 217;
  let logContainer: HTMLElement;
  $: displayLogs = $logs.slice(-20);

  onMount(() => {
    const interval = setInterval(() => { recCounter++; }, 1000);
    return () => clearInterval(interval);
  });
  
  afterUpdate(() => {
    if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
    if (logContainer) logContainer.scrollTop = logContainer.scrollHeight;
  });

  function getRotation(percent: number) { return (percent / 100) * 180 - 90; }
</script>

<div class="grid grid-cols-12 gap-4">
  <!-- ==================== LEFT: TELEMETRY & VAULT ==================== -->
  <div class="col-span-12 lg:col-span-3 space-y-3 flex-col flex gap-3">
    <!-- Telemetry Gauges -->
    <div class="brass rounded p-3">
      <div class="font-cinzel text-xs font-bold text-dark mb-2">ENGINE TELEMETRY</div>
      <div class="space-y-3">
        {#each [
          { label: 'RITUAL MATCH', val: ritualMatchScore },
          { label: 'PLAYLIST RES', val: playlistResonance },
          { label: 'ENVY INTENSITY', val: envyIntensity }
        ] as gauge}
        <div class="bg-black rounded p-2 border border-yellow-600/30">
          <div class="flex justify-between text-[9px] text-[#c9a86a]">
            <span>{gauge.label}</span>
            <span class="text-white">{gauge.val.toFixed(0)}%</span>
          </div>
          <div class="mt-1 h-14 gauge-glass rounded-full border-4 border-[#8c6a3a] relative">
            <div class="absolute inset-2 rounded-full bg-[#fefefe] flex items-center justify-center">
              <div class="w-1 h-5 bg-black origin-bottom absolute bottom-1/2 transition-all duration-500" style="transform:rotate({getRotation(gauge.val)}deg)"></div>
              <div class="w-2 h-2 bg-black rounded-full z-10"></div>
            </div>
          </div>
        </div>
        {/each}
      </div>
    </div>
    
    <!-- Radar Feed -->
    <div class="bg-black rounded border-2 border-[#c9a86a] p-2 flex-1 min-h-[200px] flex flex-col">
      <div class="flex justify-between">
        <div class="text-[9px] text-[#c9a86a] tracking-widest">SIGINT FEED REC: <span class="text-white">{String(recCounter).padStart(4,'0')}</span></div>
        <div class="text-[9px] text-green-400 animate-pulse">● ACTIVE</div>
      </div>
      <div class="mt-2 flex-1 overflow-y-auto font-mono text-[10px] text-[#8fbc8f] leading-[1.2]" bind:this={logContainer}>
        {#each displayLogs as log}
          <div class="mb-1 {log.level === 'ERROR' ? 'text-red-500' : ''}">[{log.ts}] {log.msg}</div>
        {/each}
      </div>
    </div>
    
    <!-- Vault -->
    <div class="brass rounded p-2">
      <div class="font-cinzel text-[9px] font-bold text-dark mb-1">KEYSTORE • SESSION VAULT</div>
      <div class="flex items-center gap-2 mt-1 mb-2">
        <button class="w-8 h-8 rounded-full brass border-2 border-black flex items-center justify-center cursor-pointer hover:brightness-110 disabled:opacity-50 {vaultStatusText === 'ERROR' ? 'border-red-500 animate-pulse' : ''}" on:click={sealCredentials} disabled={isSealing}>
          🔑
        </button>
        <div class="text-[8px] font-bold text-dark">
          <span class:text-red-800={vaultStatusText === 'ERROR'}>{vaultStatusText}</span><br>
          client_id tabanlı • session keystore
        </div>
      </div>
      <div class="bg-black border border-[#c9a86a]/40 p-2 rounded">
        <input type="password" class="w-full bg-transparent text-[#c9a86a] text-[9px] outline-none border-b border-[#333] mb-2 focus:border-[#c9a86a]" bind:value={apiKey} placeholder="API KEY (sk-or-v1-...)" disabled={isSealing}>
        <input type="password" class="w-full bg-transparent text-[#c9a86a] text-[9px] outline-none border-b border-[#333] focus:border-[#c9a86a]" bind:value={cookie} placeholder="X/TWITTER COOKIE (auth_token=...)" disabled={isSealing}>
      </div>
    </div>
  </div>

  <!-- ==================== CENTER: TARGET & AGENT DECK ==================== -->
  <div class="col-span-12 lg:col-span-6 space-y-3 flex-col flex gap-3">
    <!-- TARGET & INITIATE -->
    <div class="brass rounded-[6px] p-4">
      <div class="flex justify-between">
        <div class="font-cinzel text-[11px] font-bold text-dark">BROADCAST MIC • TARGET INPUT</div>
        <div class="flex items-center gap-2">
          <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse"></div>
          <div class="text-[9px] font-bold">LIVE</div>
        </div>
      </div>
      <div class="flex gap-4 mt-3">
        <div class="w-24 h-32 bg-gradient-to-b from-[#ddd] to-[#777] rounded-[14px] border-4 border-[#555] flex items-center justify-center">
          <div class="w-16 h-20 bg-black rounded"></div>
        </div>
        <div class="flex-1">
          <div class="bg-black rounded p-2 border-2 border-[#c9a86a]">
            <div class="text-[9px] text-[#c9a86a]">TARGET URL + COOKIE</div>
            <input class="w-full bg-transparent text-[#f5f1e8] text-[13px] outline-none mt-1" bind:value={targetUrl} placeholder="https://x.com/target" disabled={$isProcessing}>
          </div>
          <div class="grid grid-cols-3 gap-1 mt-2">
            <div class="bg-black/80 border border-[#c9a86a]/40 p-1 rounded text-[8px] text-[#c9a86a]">RITUALS<br><input class="bg-transparent text-white w-full outline-none" bind:value={userRituals} placeholder="02:17" disabled={$isProcessing}></div>
            <div class="bg-black/80 border border-[#c9a86a]/40 p-1 rounded text-[8px] text-[#c9a86a]">PLAYLIST<br><input class="bg-transparent text-white w-full outline-none" bind:value={userPlaylist} placeholder="dark jazz" disabled={$isProcessing}></div>
            <div class="bg-black/80 border border-[#c9a86a]/40 p-1 rounded text-[8px] text-[#c9a86a]">ENVIES<br><input class="bg-transparent text-white w-full outline-none" bind:value={userEnvies} placeholder="derinlik" disabled={$isProcessing}></div>
          </div>
          <div class="mt-2 flex gap-2">
            <select class="bg-black text-[#c9a86a] border border-[#c9a86a]/40 rounded text-[9px] outline-none px-1 focus:border-[#c9a86a]" bind:value={selectedLocalModel} on:change={updateLocalModelOnly} disabled={isSettingModel || $isProcessing || localModelActive}>
              <option value="dolphin-llama3">Dolphin Llama3</option>
              <option value="gemma2:2b">Gemma 2:2b</option>
              <option value="qwen2.5-coder:latest">Qwen 2.5 Coder</option>
            </select>
            <button class="brass px-3 py-1 rounded font-cinzel font-bold text-[10px] {localModelActive ? 'opacity-100 shadow-[0_0_10px_rgba(0,0,0,0.8)]' : 'opacity-70'}" on:click={toggleLocalModel} disabled={isSettingModel || $isProcessing}>LOKAL</button>
            <button class="brass px-3 py-1 rounded font-cinzel font-bold text-[10px] {!localModelActive ? 'opacity-100 shadow-[0_0_10px_rgba(0,0,0,0.8)]' : 'opacity-70'}" on:click={toggleLocalModel} disabled={isSettingModel || $isProcessing}>API</button>
            <div class="flex-1 h-7 bg-black rounded flex items-center px-2 gap-2 border border-[#333]">
              <span class="text-[8px] text-green-400">CONFIDENCE</span>
              <div class="flex-1 h-1 bg-[#222] rounded overflow-hidden">
                <div class="h-full bg-green-400 transition-all duration-300" style="width:{overallConfidence * 100}%"></div>
              </div>
            </div>
            <button class="bg-[#c9a86a] hover:brightness-110 text-black px-5 py-1 rounded font-cinzel font-bold text-[11px] disabled:opacity-50" on:click={triggerAnalysis} disabled={$isProcessing || !targetUrl}>{$isProcessing ? 'RUNNING' : 'INITIATE ●'}</button>
          </div>
        </div>
      </div>
    </div>

    <!-- AGENT DECK -->
    <div class="brass rounded-[8px] p-3 flex-1 flex flex-col h-full">
      <div class="flex justify-between items-center mb-2">
        <div class="font-cinzel font-extrabold text-[13px] tracking-widest text-dark">★ AGENT COMMAND DECK ★</div>
        <div class="text-[9px] font-bold text-dark">MEMORY: 1 unique • hash OK</div>
      </div>
      
      <div class="grid grid-cols-4 gap-2 mb-3">
        <button class="brass rounded p-2 text-left hover:brightness-110 {activeAgentId === 'ASPASIA' ? 'ring-2 ring-black' : ''}" on:click={() => activeAgentId = 'ASPASIA'}>
          <div class="flex items-center gap-1"><div class="w-2 h-2 rounded-full bg-gray-500 {activeAgentId==='ASPASIA'?'animate-pulse':''}"></div><div class="font-cinzel font-bold text-[9px] text-dark leading-none">ASPASIA</div></div>
          <div class="text-[7px] text-[#3d2817] mt-1">Sistem Yöneticisi</div>
        </button>
        {#each agentList.slice(0,3) as agent}
        <button class="brass rounded p-2 text-left hover:brightness-110 {activeAgentId === agent.id ? 'ring-2 ring-black' : ''}" on:click={() => activeAgentId = agent.id}>
          <div class="flex items-center gap-1"><div class="w-2 h-2 rounded-full" style="background:{agent.colorHex}; {activeAgentId===agent.id?'animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;':''}"></div><div class="font-cinzel font-bold text-[9px] text-dark leading-none">{agent.name}</div></div>
        </button>
        {/each}
      </div>

      <div class="paper rounded border-2 border-[#8c6a3a] flex-1 overflow-y-auto p-3 font-type text-[12px] leading-[1.5] h-[280px]" bind:this={chatContainer}>
        {#each messages as msg}
          <div class="mb-2">
            <span class="text-[10px] text-[#8c6a3a]">[{new Date().toLocaleTimeString('tr-TR').slice(0,5)}]</span>
            {#if msg.sender === 'SİZ'}
              <b>YOU → {activeAgentId.toUpperCase()}:</b> {msg.text}
            {:else if msg.sender === 'SİSTEM'}
              <span class="bg-[#c9a86a] text-black px-1 font-bold text-[10px]">{msg.text}</span>
            {:else}
              <b>◀ {msg.sender}:</b> {msg.text}
            {/if}
          </div>
        {/each}
      </div>
      
      <div class="flex items-center mt-3 gap-2 bg-black rounded border border-[#c9a86a] p-1">
        <div class="text-[10px] text-[#c9a86a] px-2 font-bold">{activeAgentId.toUpperCase()} →</div>
        <input class="flex-1 bg-transparent text-white text-[13px] outline-none px-2" bind:value={inputMessage} on:keydown={handleKeydown} placeholder="Ajanı yönlendir..." disabled={isSending}>
        <input type="file" accept="image/*" bind:this={fileInput} on:change={handleImageUpload} class="hidden">
        <button class="text-[#c9a86a] px-2 disabled:opacity-50 {isListening?'text-red-500 animate-pulse':''}" on:click={toggleListen} disabled={isSending}>🎙️</button>
        <button class="text-[#c9a86a] px-2 disabled:opacity-50" on:click={() => fileInput.click()} disabled={isSending}>👁️</button>
        <button class="brass px-4 py-1 rounded text-[11px] font-bold text-dark disabled:opacity-50" on:click={sendMessage} disabled={isSending}>SEND</button>
      </div>

      <div class="flex items-center gap-2 mt-2">
        <button class="bg-[#2563eb] text-white px-3 py-1 rounded text-[10px] font-bold hover:brightness-110" on:click={explainState}>EXPLAIN STATE (Neden?)</button>
        <span class="text-[8px] text-gray-500 font-mono">ASPASIA Gözlemci Modu Aktif</span>
      </div>
    </div>
  </div>

  <!-- ==================== RIGHT: AGENT CHAIN ==================== -->
  <div class="col-span-12 lg:col-span-3 space-y-3">
    <div class="brass rounded p-3">
      <div class="flex justify-between items-center mb-2">
        <div class="font-cinzel text-[11px] font-bold text-dark">AGENT CHAIN • DURUM</div>
        <span class="text-[8px] font-mono px-1.5 py-0.5 rounded font-bold {taskState === 'completed' ? 'bg-green-800 text-white' : taskState.startsWith('halted') || taskState === 'failed' ? 'bg-red-800 text-white' : taskState === 'processing' ? 'bg-amber-700 text-white animate-pulse' : 'bg-black/40 text-dark'}">{taskState.toUpperCase()}</span>
      </div>

      {#if taskId}
        <div class="text-[8px] font-mono text-dark/70 mb-2">GÖREV: {taskId}</div>
      {/if}

      <div class="space-y-2">
        {#each agentList as agent, i}
          {@const run = runs[agent.id]}
          {@const isCompleted = run?.status === 'completed'}
          {@const isRunning = currentAgent === agent.id && taskState === 'processing'}
          {@const isHalted = run?.status === 'halted' || run?.status === 'failed'}
          <div class="flex items-center gap-2">
            <div class="w-6 h-6 rounded-full flex items-center justify-center text-white text-[10px] font-bold" style="background: {agent.colorHex};">
              {#if isCompleted}✓{:else if isRunning}▶{:else if isHalted}✗{:else}{i + 1}{/if}
            </div>
            <div class="flex-1">
              <div class="flex justify-between text-[9px] font-bold text-dark">
                <span>{agent.name}</span>
                {#if run?.confidence !== undefined && run?.confidence !== null}
                  <span class="font-mono text-[8px]">{run.confidence.toFixed(2)}</span>
                {/if}
              </div>
              <div class="h-1.5 bg-black/20 rounded mt-1 overflow-hidden">
                <div class="h-full transition-all duration-500 {isCompleted ? 'bg-green-600' : isHalted ? 'bg-red-600' : isRunning ? 'bg-amber-500 animate-pulse' : ''}" style="width: {isCompleted ? '100%' : isRunning ? '60%' : isHalted ? '100%' : '0%'};"></div>
              </div>
            </div>
            <div class="text-[8px] font-mono w-14 text-right">
              {#if isCompleted}
                <span class="text-green-900 font-bold">DONE</span>
              {:else if isHalted}
                <span class="text-red-700 font-bold">{run?.status === 'halted' ? 'HALT' : 'FAIL'}</span>
              {:else if isRunning}
                <span class="text-amber-900 font-bold animate-pulse">RUNNING</span>
              {:else}
                <span class="text-dark/40">WAIT</span>
              {/if}
            </div>
          </div>
          {#if i < agentList.length - 1}
            <div class="ml-3 w-0.5 h-2 bg-[#8c6a3a]/50"></div>
          {/if}
        {/each}
      </div>

      {#if haltedReason}
        <div class="mt-3 bg-red-900/20 border border-red-800/40 rounded p-2 text-[8px] text-red-900 leading-tight">
          <b>DURDURMA BİLGİSİ:</b> {haltedReason}
        </div>
      {/if}
      
      <div class="mt-3 bg-black rounded p-2 border border-[#c9a86a]/30">
        <div class="text-[9px] text-[#c9a86a]">OVERALL CONFIDENCE</div>
        <div class="flex items-center gap-2 mt-1">
          <div class="flex-1 h-2 bg-[#222] rounded overflow-hidden">
            <div class="h-full bg-gradient-to-r from-red-500 via-yellow-500 to-green-500 transition-all duration-300" style="width: {overallConfidence * 100}%;"></div>
          </div>
          <div class="text-[11px] text-white font-mono">{overallConfidence.toFixed(2)}</div>
        </div>
      </div>
    </div>
  </div>
</div>

<style>
  .text-dark { color: #1a0f02; }
  .brass {
    background: linear-gradient(145deg, #e8d5a8 0%, #c9a86a 20%, #8c6a3a 50%, #c9a86a 80%, #e8d5a8 100%);
    box-shadow: inset 0 1px 1px rgba(255,255,255,0.8), 0 2px 8px rgba(0,0,0,0.8);
    border: 1px solid #6b4e2a;
  }
  .paper {
    background: #f5f1e8;
    background-image: repeating-linear-gradient(0deg, transparent, transparent 23px, rgba(0,0,0,0.04) 24px);
    box-shadow: inset 0 0 30px rgba(139,106,58,0.2);
  }
  .gauge-glass {
    background: radial-gradient(ellipse at 30% 20%, rgba(255,255,255,0.4) 0%, transparent 50%),
                radial-gradient(ellipse at center, #fefefe 0%, #e8e0d0 100%);
  }
  .font-type {
    font-family: 'Special Elite', cursive, monospace;
  }
</style>
