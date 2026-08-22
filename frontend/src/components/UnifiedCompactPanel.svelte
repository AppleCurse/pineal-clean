<script lang="ts">
  import { onMount, afterUpdate } from 'svelte';
  import { clientId, apiFetch, isProcessing, logs, taskStatus, telemetryEvents } from '../store';
  import { currentLang, t } from '../i18n';
  
  // ==========================================
  // TARGET & ENGINE TELEMETRY
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
      const res = await apiFetch(`/api/vault`, {
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
      await apiFetch(`/api/vault`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ client_id: $clientId, use_local: localModelActive, local_model: selectedLocalModel })
      });
      logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "INFO", msg: `YEREL MODEL: ${selectedLocalModel}`}]);
    } catch(err: any) {
      console.error("Model güncellenemedi", err);
    }
  }

  export async function triggerAnalysis() {
    if (!targetUrl) return;
    isProcessing.set(true);
    try {
      const res = await apiFetch(`/api/initiate`, {
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
  // VAULT (KEYSTORE)
  // ==========================================
  let apiKey = "";
  let cookie = "";
  let isSealing = false;
  let vaultStatusKey = "vaultReady";

  async function sealCredentials() {
    isSealing = true;
    vaultStatusKey = "vaultSaving";
    try {
      const payload: any = { client_id: $clientId };
      if (apiKey) payload.api_key = apiKey;
      if (cookie) payload.x_cookie = cookie;
      const res = await apiFetch(`/api/vault`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Connection error");
      vaultStatusKey = "vaultActive";
      apiKey = "";
      cookie = "";
    } catch(err: any) {
      vaultStatusKey = "vaultError";
    } finally {
      isSealing = false;
    }
  }

  // ==========================================
  // ASPASIA CHAT & DIALOGUE
  // ==========================================
  let messages: {sender: string, text: string}[] = [
    { sender: 'ASPASIA', text: 'Sistem çevrimiçi. Hedef verilerini ve telemetriyi incelemeye hazırım şefim.' }
  ];
  let inputMessage = "";
  let chatContainer: HTMLElement;
  let isSending = false;
  let isListening = false;
  let attachedImage: string | null = null;
  let fileInput: HTMLInputElement;
  let activeAgentId = 'ASPASIA';

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
    inputMessage = ""; 
    attachedImage = null; 
    isSending = true;
    
    try {
      const payload: any = { client_id: $clientId, user_message: currentInput };
      if (currentImage) payload.image_data = currentImage;
      const endpoint = activeAgentId === 'ASPASIA' ? '/api/aspasia/chat' : '/api/executor/intervene';
      if (activeAgentId !== 'ASPASIA') payload.action_type = `DIRECT_CMD_${activeAgentId}`;

      const res = await apiFetch(`${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error("Ağ geçidi yanıt vermedi");
      const data = await res.json();
      messages = [...messages, { sender: activeAgentId, text: data.message || data.error?.message || "Yanıt alındı." }];
    } catch (error: any) {
      messages = [...messages, { sender: 'SİSTEM', text: `HATA: ${error.message}` }];
    } finally {
      isSending = false;
    }
  }

  function explainState() {
    activeAgentId = 'ASPASIA';
    inputMessage = $currentLang === 'tr' 
      ? 'Şu anki telemetri ve analiz durumunu özetler misin? Hangi aşamadayız?' 
      : 'Can you summarize the current telemetry and analysis state? Where are we?';
    sendMessage();
  }

  function handleKeydown(e: KeyboardEvent) { if (e.key === 'Enter') sendMessage(); }

  // ==========================================
  // TELEMETRY METRICS & AGENT CHAIN
  // ==========================================
  let ritualMatchScore = 0;
  let playlistResonance = 0;
  let envyIntensity = 0;

  const agentList = [
    { id: "mirror_truth", name: "MIRROR TRUTH", color: "#10b981" },
    { id: "autonomous_verifier", name: "AUTONOMOUS VERIFIER", color: "#a855f7" },
    { id: "human_behavior", name: "HUMAN BEHAVIOR", color: "#f59e0b" },
    { id: "passion_mapper", name: "PASSION MAPPER", color: "#f59e0b" },
    { id: "friction_detector", name: "FRICTION & BOUNDS", color: "#ef4444" },
    { id: "cognitive_profiler", name: "COGNITIVE PROFILER", color: "#06b6d4" },
    { id: "resonance_calc", name: "RESONANCE CALCULATOR", color: "#3b82f6" },
    { id: "pattern_interrupt", name: "PATTERN INTERRUPT", color: "#dc2626" },
    { id: "resonance_synthesizer", name: "AUTHENTIC BRIDGE", color: "#10b981" }
  ];

  let runs: Record<string, any> = {};
  let currentAgent = "";
  let overallConfidence = 0;
  let haltedReason: string | null = null;
  let taskState = "IDLE";
  let taskId = "";
  let holisticProfile: any = null;
  let copyFeedback = false;

  function copyMessage(text: string) {
    if (!text) return;
    navigator.clipboard.writeText(text);
    copyFeedback = true;
    setTimeout(() => { copyFeedback = false; }, 2000);
  }

  $: {
    if ($taskStatus) {
      if ($taskStatus.task_id) taskId = $taskStatus.task_id;
      if ($taskStatus.status) taskState = $taskStatus.status;
      if ($taskStatus.halted_reason !== undefined) haltedReason = $taskStatus.halted_reason;
      if ($taskStatus.holistic_profile) holisticProfile = $taskStatus.holistic_profile;

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

  let logContainer: HTMLElement;
  $: displayLogs = $logs.slice(-25);

  afterUpdate(() => {
    if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
    if (logContainer) logContainer.scrollTop = logContainer.scrollHeight;
  });
</script>

<div class="cockpit-grid">
  <!-- ==================== SOL PANEL: TELEMETRİ VE KASA ==================== -->
  <aside style="display: flex; flex-direction: column; gap: 14px;">
    
    <!-- Göstergeler (Telemetry) -->
    <div class="brass-plate">
      <div class="font-cinzel" style="font-size: 11px; font-weight: 800; color: var(--gold); margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center;">
        <span>{t[$currentLang].engineTelemetry}</span>
        <span style="font-size: 9px; color: var(--accent-green); font-family: 'JetBrains Mono', monospace;">● {t[$currentLang].active}</span>
      </div>

      <div style="display: flex; flex-direction: column; gap: 8px;">
        {#each [
          { label: t[$currentLang].ritualMatch, val: ritualMatchScore, col: '#10b981' },
          { label: t[$currentLang].playlistResonance, val: playlistResonance, col: '#06b6d4' },
          { label: t[$currentLang].envyIntensity, val: envyIntensity, col: '#f59e0b' }
        ] as g}
          <div class="screen-card" style="padding: 8px 10px;">
            <div style="display: flex; justify-content: space-between; font-size: 10px; color: var(--text-dim); margin-bottom: 4px;">
              <span>{g.label}</span>
              <strong style="color: var(--text-main); font-size: 11px;">%{g.val.toFixed(0)}</strong>
            </div>
            <div style="height: 6px; background: #1f140e; border-radius: 3px; overflow: hidden; border: 1px solid #3d2b17;">
              <div style="height: 100%; width: {Math.max(5, g.val)}%; background: {g.col}; transition: width 0.4s ease;"></div>
            </div>
          </div>
        {/each}
      </div>
    </div>

    <!-- Canlı Log Terminali -->
    <div class="screen-card" style="display: flex; flex-direction: column; height: 260px; padding: 10px;">
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2a1e12; padding-bottom: 6px; margin-bottom: 6px;">
        <span class="font-cinzel" style="font-size: 10px; color: var(--gold); font-weight: 700;">{t[$currentLang].sigintFeed}</span>
        <span style="font-size: 9px; color: var(--text-muted);">WS:8000</span>
      </div>
      <div style="flex: 1; overflow-y: auto; font-size: 10px; line-height: 1.4; color: #a3e635;" bind:this={logContainer}>
        {#each displayLogs as log}
          <div style="margin-bottom: 3px; {log.level === 'ERROR' ? 'color: #f87171;' : log.level === 'WARNING' ? 'color: #fbbf24;' : ''}">
            <span style="color: #65a30d; font-size: 9px;">[{log.ts}]</span> {log.msg}
          </div>
        {/each}
      </div>
    </div>

    <!-- Güvenli Kasa (Vault) -->
    <div class="brass-plate">
      <div class="font-cinzel" style="font-size: 11px; font-weight: 800; color: var(--gold); margin-bottom: 6px;">
        {t[$currentLang].vaultTitle}
      </div>
      <p style="font-size: 10px; color: var(--text-muted); margin-bottom: 10px;">
        {t[$currentLang].vaultDesc}
      </p>

      <div style="display: flex; flex-direction: column; gap: 8px;">
        <input 
          type="password" 
          bind:value={apiKey} 
          placeholder={t[$currentLang].apiKeyPlaceholder} 
          disabled={isSealing}
        />
        <input 
          type="password" 
          bind:value={cookie} 
          placeholder={t[$currentLang].cookiePlaceholder} 
          disabled={isSealing}
        />
        <button class="btn-brass" style="width: 100%; font-size: 11px; padding: 8px;" on:click={sealCredentials} disabled={isSealing || (!apiKey && !cookie)}>
          🔑 {t[$currentLang].sealBtn}
        </button>
      </div>
    </div>

  </aside>

  <!-- ==================== ORTA PANEL: HEDEF GİRİŞİ, ASPASIA & 360° HARİTA ==================== -->
  <section style="display: flex; flex-direction: column; gap: 14px;">
    
    <!-- Hedef Giriş Kartı -->
    <div class="brass-plate">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <span class="font-cinzel" style="font-size: 12px; font-weight: 800; color: var(--gold);">
          🎯 {t[$currentLang].targetHeader}
        </span>
        <span style="font-size: 9px; font-weight: 700; color: var(--accent-green); background: rgba(16,185,129,0.15); border: 1px solid var(--accent-green); padding: 2px 8px; border-radius: 4px;">
          ● {t[$currentLang].liveStatus}
        </span>
      </div>

      <div style="display: flex; flex-direction: column; gap: 10px;">
        <div>
          <label style="display: block; font-size: 10px; color: var(--text-dim); margin-bottom: 4px; font-weight: 600;">
            {t[$currentLang].targetUrlLabel}
          </label>
          <input 
            style="font-size: 13px; font-weight: 600; padding: 8px 12px;" 
            bind:value={targetUrl} 
            placeholder={t[$currentLang].targetUrlPlaceholder} 
            disabled={$isProcessing}
          />
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px;">
          <div>
            <label style="display: block; font-size: 9px; color: var(--text-muted); margin-bottom: 2px;">{t[$currentLang].ritualsLabel}</label>
            <input bind:value={userRituals} placeholder={t[$currentLang].ritualsPlaceholder} disabled={$isProcessing} />
          </div>
          <div>
            <label style="display: block; font-size: 9px; color: var(--text-muted); margin-bottom: 2px;">{t[$currentLang].playlistLabel}</label>
            <input bind:value={userPlaylist} placeholder={t[$currentLang].playlistPlaceholder} disabled={$isProcessing} />
          </div>
          <div>
            <label style="display: block; font-size: 9px; color: var(--text-muted); margin-bottom: 2px;">{t[$currentLang].enviesLabel}</label>
            <input bind:value={userEnvies} placeholder={t[$currentLang].enviesPlaceholder} disabled={$isProcessing} />
          </div>
        </div>

        <!-- Model ve Başlat Butonu Barı -->
        <div style="display: flex; gap: 8px; align-items: center; margin-top: 4px; flex-wrap: wrap;">
          <select style="width: auto; flex: 1; min-width: 140px;" bind:value={selectedLocalModel} on:change={updateLocalModelOnly} disabled={isSettingModel || $isProcessing || localModelActive}>
            <option value="dolphin-llama3">Dolphin Llama-3 (Abliterated)</option>
            <option value="qwen2.5-coder:latest">Qwen 2.5 7B</option>
            <option value="llama3.3:70b">Llama 3.3 70B</option>
          </select>

          <button 
            class="btn-dark" 
            style="{localModelActive ? 'background: var(--gold); color: #120b04; font-weight: 700;' : ''}" 
            on:click={toggleLocalModel} 
            disabled={isSettingModel || $isProcessing}
          >
            {t[$currentLang].localBtn}
          </button>
          
          <button 
            class="btn-dark" 
            style="{!localModelActive ? 'background: var(--gold); color: #120b04; font-weight: 700;' : ''}" 
            on:click={toggleLocalModel} 
            disabled={isSettingModel || $isProcessing}
          >
            {t[$currentLang].apiBtn}
          </button>

          <button 
            class="btn-brass" 
            style="padding: 8px 24px; font-size: 12px;" 
            on:click={triggerAnalysis} 
            disabled={$isProcessing || !targetUrl}
          >
            {$isProcessing ? t[$currentLang].runningBtn : t[$currentLang].initiateBtn}
          </button>
        </div>
      </div>
    </div>

    <!-- Aspasia Sokratik Kokpit Şefi & Sohbet -->
    <div class="brass-plate" style="display: flex; flex-direction: column; flex: 1;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
        <div>
          <span class="font-cinzel" style="font-size: 12px; font-weight: 800; color: var(--gold);">
            🏛️ {t[$currentLang].agentDeckTitle}
          </span>
          <span style="font-size: 10px; color: var(--text-dim); margin-left: 6px;">({t[$currentLang].aspasiaRole})</span>
        </div>
        <button class="btn-dark" style="font-size: 10px; padding: 4px 10px;" on:click={explainState}>
          💡 {t[$currentLang].explainStateBtn}
        </button>
      </div>

      <!-- Sohbet Akışı -->
      <div class="screen-card" style="height: 220px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; margin-bottom: 10px;" bind:this={chatContainer}>
        {#each messages as msg}
          <div style="font-size: 11px; line-height: 1.5;">
            {#if msg.sender === 'SİZ'}
              <div style="text-align: right;">
                <span style="background: #2a1e12; border: 1px solid var(--brass-border); color: var(--text-main); padding: 5px 10px; border-radius: 6px; display: inline-block; max-width: 85%;">
                  <b>{t[$currentLang].you}:</b> {msg.text}
                </span>
              </div>
            {:else if msg.sender === 'SİSTEM'}
              <div style="text-align: center;">
                <span style="background: rgba(212,175,55,0.15); border: 1px solid var(--gold); color: var(--gold-light); padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;">
                  ⚙️ {msg.text}
                </span>
              </div>
            {:else}
              <div style="text-align: left;">
                <span style="background: #17110c; border: 1px solid #4a341e; color: var(--gold-light); padding: 6px 12px; border-radius: 6px; display: inline-block; max-width: 90%;">
                  <b style="color: var(--gold);">{msg.sender}:</b> {msg.text}
                </span>
              </div>
            {/if}
          </div>
        {/each}
      </div>

      <!-- Mesaj Girişi & Araçlar -->
      <div style="display: flex; gap: 6px; align-items: center;">
        <input 
          style="flex: 1; font-size: 12px; padding: 8px 12px;" 
          bind:value={inputMessage} 
          on:keydown={handleKeydown} 
          placeholder={t[$currentLang].chatPlaceholder} 
          disabled={isSending}
        />
        <input type="file" accept="image/*" bind:this={fileInput} on:change={handleImageUpload} style="display: none;">
        <button class="btn-dark" title="Görsel Yükle" on:click={() => fileInput.click()} disabled={isSending}>
          📷
        </button>
        <button class="btn-brass" style="font-size: 11px; padding: 8px 16px;" on:click={sendMessage} disabled={isSending || (!inputMessage.trim() && !attachedImage)}>
          {t[$currentLang].sendBtn}
        </button>
      </div>
    </div>

    <!-- 360° BÜTÜNCÜL İNSAN ÇÖZÜMLEMESİ (Holistic Profile Card) -->
    {#if holisticProfile}
    <div class="brass-plate" style="border: 2px solid var(--accent-green);">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid #2a1e12; padding-bottom: 8px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <span class="font-cinzel" style="font-size: 13px; font-weight: 800; color: var(--accent-green);">
            🧠 {t[$currentLang].holisticTitle}
          </span>
          <span style="font-size: 9px; font-weight: 800; background: var(--accent-green); color: #0a0502; padding: 2px 6px; border-radius: 4px;">
            {t[$currentLang].fullMap}
          </span>
        </div>
        <span style="font-size: 11px; color: var(--gold); font-weight: 700;">
          @{holisticProfile.username || 'target'}
        </span>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 10px; margin-bottom: 12px;">
        <!-- Tutkular -->
        <div class="screen-card" style="border-color: rgba(245,158,11,0.4);">
          <div style="font-size: 10px; font-weight: 700; color: var(--accent-amber); margin-bottom: 6px;">
            {t[$currentLang].passionsTitle}
          </div>
          {#if holisticProfile.passions?.core_passions?.length}
            <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px;">
              {#each holisticProfile.passions.core_passions as p}
                <span style="background: rgba(245,158,11,0.2); color: #fde68a; font-size: 9px; padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(245,158,11,0.3);">
                  {p}
                </span>
              {/each}
            </div>
          {:else}
            <p style="font-size: 9px; color: var(--text-muted); font-style: italic;">{t[$currentLang].noPassions}</p>
          {/if}
          {#if holisticProfile.passions?.energizing_topics?.length}
            <div style="font-size: 9px; color: var(--text-dim); margin-top: 4px;">
              <b>{t[$currentLang].energizingLabel}</b> {holisticProfile.passions.energizing_topics.join(', ')}
            </div>
          {/if}
        </div>

        <!-- Sınırlar -->
        <div class="screen-card" style="border-color: rgba(239,68,68,0.4);">
          <div style="font-size: 10px; font-weight: 700; color: var(--accent-red); margin-bottom: 6px;">
            {t[$currentLang].frictionsTitle}
          </div>
          {#if holisticProfile.frictions?.sensitivities?.length}
            <div style="display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px;">
              {#each holisticProfile.frictions.sensitivities as s}
                <span style="background: rgba(239,68,68,0.2); color: #fca5a5; font-size: 9px; padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(239,68,68,0.3);">
                  {s}
                </span>
              {/each}
            </div>
          {:else}
            <p style="font-size: 9px; color: var(--text-muted); font-style: italic;">{t[$currentLang].noFrictions}</p>
          {/if}
          {#if holisticProfile.frictions?.boundary_signals?.length}
            <div style="font-size: 9px; color: #fca5a5; margin-top: 4px;">
              <b>{t[$currentLang].boundariesLabel}</b> {holisticProfile.frictions.boundary_signals.join(', ')}
            </div>
          {/if}
        </div>

        <!-- Bilişsel Ton -->
        <div class="screen-card" style="border-color: rgba(6,182,212,0.4);">
          <div style="font-size: 10px; font-weight: 700; color: var(--accent-cyan); margin-bottom: 6px;">
            {t[$currentLang].cognitiveTitle}
          </div>
          <div style="font-size: 9px; color: var(--text-main); display: flex; flex-direction: column; gap: 3px;">
            <div>{t[$currentLang].toneLabel} <b style="color: #67e8f9;">{holisticProfile.cognitive?.communication_tone || 'Dengeli'}</b></div>
            <div>{t[$currentLang].complexityLabel} <b style="color: #67e8f9;">{holisticProfile.cognitive?.complexity_level || 'Orta'}</b></div>
            <div>{t[$currentLang].socialLabel} <b style="color: #67e8f9;">{holisticProfile.cognitive?.social_orientation || 'Bağımsız'}</b></div>
          </div>
        </div>
      </div>

      <!-- Sahici Diyalog Köprüsü -->
      {#if holisticProfile.bridge}
        <div class="screen-card" style="border: 2px solid var(--accent-green); background: #0c140d;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span class="font-cinzel" style="font-size: 11px; font-weight: 800; color: var(--accent-green);">
              {t[$currentLang].bridgeTitle}
            </span>
            <span style="font-size: 10px; color: var(--gold); font-weight: 700;">
              %{ (holisticProfile.bridge.resonance_score * 100).toFixed(0) } {t[$currentLang].resonanceScore}
            </span>
          </div>

          <div style="font-size: 10px; color: var(--text-dim); margin-bottom: 6px;">
            <b>{t[$currentLang].openingTopic}</b> {holisticProfile.bridge.authentic_opening_topic}
          </div>

          <div style="background: #060907; border: 1px solid #1f3823; border-radius: 5px; padding: 10px; font-size: 12px; color: #f5f1e8; line-height: 1.5; margin-bottom: 8px; user-select: all;">
            "{holisticProfile.bridge.suggested_opening_message}"
          </div>

          <div style="display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 9px; color: var(--text-muted); font-style: italic; flex: 1; margin-right: 8px;">
              {holisticProfile.bridge.conversation_starter_rationale}
            </span>
            <button class="btn-brass" style="font-size: 10px; padding: 6px 14px;" on:click={() => copyMessage(holisticProfile.bridge.suggested_opening_message)}>
              {copyFeedback ? t[$currentLang].copiedBtn : t[$currentLang].copyBtn}
            </button>
          </div>
        </div>
      {/if}
    </div>
    {/if}

  </section>

  <!-- ==================== SAĞ PANEL: AJAN ZİNCİRİ & KARAR AĞACI ==================== -->
  <aside style="display: flex; flex-direction: column; gap: 14px;">
    
    <div class="brass-plate">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
        <span class="font-cinzel" style="font-size: 11px; font-weight: 800; color: var(--gold);">
          ⚙️ {t[$currentLang].agentChainTitle}
        </span>
        <span style="font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 4px; {taskState === 'completed' ? 'background: #10b981; color: #000;' : taskState.startsWith('halted') || taskState === 'failed' ? 'background: #ef4444; color: #fff;' : taskState === 'processing' ? 'background: #f59e0b; color: #000;' : 'background: #2a1e12; color: var(--text-dim);'}">
          {taskState.toUpperCase()}
        </span>
      </div>

      {#if taskId}
        <div style="font-size: 9px; color: var(--text-muted); margin-bottom: 10px;">
          <b>{t[$currentLang].taskLabel}</b> {taskId}
        </div>
      {/if}

      <!-- Ajan İlerleme Listesi -->
      <div style="display: flex; flex-direction: column; gap: 6px;">
        {#each agentList as agent, i}
          {@const run = runs[agent.id]}
          {@const isCompleted = run?.status === 'completed'}
          {@const isRunning = currentAgent === agent.id && taskState === 'processing'}
          {@const isHalted = run?.status === 'halted' || run?.status === 'failed'}

          <div class="screen-card" style="padding: 6px 8px; display: flex; align-items: center; gap: 8px;">
            <div style="width: 20px; height: 20px; border-radius: 50%; background: {agent.color}; display: flex; align-items: center; justify-content: center; font-size: 9px; font-weight: 800; color: #000;">
              {#if isCompleted}✓{:else if isRunning}▶{:else if isHalted}✗{:else}{i + 1}{/if}
            </div>

            <div style="flex: 1;">
              <div style="display: flex; justify-content: space-between; font-size: 9px; font-weight: 700; color: var(--text-dim);">
                <span>{agent.name}</span>
                {#if run?.confidence !== undefined && run?.confidence !== null}
                  <span style="color: var(--text-main); font-size: 9px;">{run.confidence.toFixed(2)}</span>
                {/if}
              </div>
              <div style="height: 4px; background: #1a120b; border-radius: 2px; overflow: hidden; margin-top: 3px;">
                <div style="height: 100%; width: {isCompleted ? '100%' : isRunning ? '50%' : isHalted ? '100%' : '0%'}; background: {isCompleted ? '#10b981' : isHalted ? '#ef4444' : isRunning ? '#f59e0b' : 'transparent'}; transition: width 0.3s ease;"></div>
              </div>
            </div>

            <span style="font-size: 8px; font-weight: 700; width: 45px; text-align: right; {isCompleted ? 'color: #10b981;' : isHalted ? 'color: #ef4444;' : isRunning ? 'color: #f59e0b;' : 'color: var(--text-muted);'}">
              {#if isCompleted}{t[$currentLang].statusDone}
              {:else if isHalted}{t[$currentLang].statusHalt}
              {:else if isRunning}{t[$currentLang].statusRunning}
              {:else}{t[$currentLang].statusWait}{/if}
            </span>
          </div>
        {/each}
      </div>

      {#if haltedReason}
        <div style="margin-top: 10px; background: rgba(239,68,68,0.15); border: 1px solid var(--accent-red); padding: 8px; border-radius: 5px; font-size: 9px; color: #fca5a5; line-height: 1.4;">
          <b>{t[$currentLang].haltedReasonTitle}</b> {haltedReason}
        </div>
      {/if}

      <!-- Toplam Sistem Güveni -->
      <div class="screen-card" style="margin-top: 12px; padding: 10px;">
        <div style="display: flex; justify-content: space-between; font-size: 10px; color: var(--gold); font-weight: 700; margin-bottom: 4px;">
          <span>{t[$currentLang].overallConfidence}</span>
          <span style="color: var(--text-main); font-size: 11px;">{overallConfidence.toFixed(2)}</span>
        </div>
        <div style="height: 6px; background: #1a120b; border-radius: 3px; overflow: hidden; border: 1px solid #3d2b17;">
          <div style="height: 100%; width: {overallConfidence * 100}%; background: linear-gradient(90deg, #ef4444 0%, #f59e0b 50%, #10b981 100%); transition: width 0.3s;"></div>
        </div>
      </div>

    </div>

  </aside>
</div>
