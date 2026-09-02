<script lang="ts">
  import { onMount, afterUpdate } from 'svelte';
  import { clientId, apiFetch, isProcessing, logs, taskStatus, telemetryEvents } from '../store';
  import { currentLang, t } from '../i18n';
  import PillarFeed from './PillarFeed.svelte';
  
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

        })
      });
      if (!res.ok) throw new Error("API hatası: " + res.statusText);
      const started = await res.json();
      if (started.task_id) taskStatus.update(s => ({ ...s, task_id: started.task_id, status: 'processing' }));
      logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "INFO", msg: `ANALİZ EMRİ GÖNDERİLDİ: ${targetUrl}`}]);
    } catch (e: any) {
      logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "ERROR", msg: `HATA: ${e.message}`}]);
      isProcessing.set(false);
    }
  }

  async function cancelAnalysis() {
    const activeTaskId = $taskStatus?.task_id;
    if (!activeTaskId) return;
    const res = await apiFetch(`/api/tasks/${activeTaskId}/cancel?client_id=${$clientId}`, {
      method: 'POST'
    });
    if (!res.ok) {
      logs.update(l => [...l, {ts: new Date().toLocaleTimeString(), level: "ERROR", msg: `İPTAL HATASI: ${res.status}`}]);
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
    { sender: 'ASPASIA', text: 'Sistem çevrimiçi. Hedef verilerini ve telemetriyi incelemeye hazırım.' }
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
  let resonanceScore = 0;
  let resonanceApproach = '';
  let redFlags: string[] = [];

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
  let followerAudit: any = null;
  let timingForensics: any = null;
  let depthReport: any = null;
  let visualEvidence: any = null;
  let shadowProfile: any = null;
  let osintFootprint: any = null;
  let telemetry: any = null;
  let frequencyMap: any = null;
  let seismosEvents: any = null;
  let voidMap: any = null;
  let strataMap: any = null;
  let gravityMap: any = null;
  let pulseMap: any = null;
  let keyMatrix: any = null;
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
      if ($taskStatus.follower_audit) followerAudit = $taskStatus.follower_audit;
      if ($taskStatus.timing_forensics) timingForensics = $taskStatus.timing_forensics;
      if ($taskStatus.depth_report) depthReport = $taskStatus.depth_report;
      if ($taskStatus.visual_evidence) visualEvidence = $taskStatus.visual_evidence;
      if ($taskStatus.shadow_profile) shadowProfile = $taskStatus.shadow_profile;
      if ($taskStatus.osint_footprint) osintFootprint = $taskStatus.osint_footprint;
      if ($taskStatus.telemetry) telemetry = $taskStatus.telemetry;
      frequencyMap = $taskStatus.frequency_map ?? null;
      seismosEvents = $taskStatus.seismos_events ?? null;
      voidMap = $taskStatus.void_map ?? null;
      strataMap = $taskStatus.strata_map ?? null;
      gravityMap = $taskStatus.gravity_map ?? null;
      pulseMap = $taskStatus.pulse_map ?? null;
      keyMatrix = $taskStatus.key_matrix ?? null;

      if ($taskStatus.reso) {
        // W3: yalniz ResonanceProfile'da GERCEKTEN bulunan alanlar okunur.
        resonanceScore = ($taskStatus.reso.compatibility_score ?? 0) * 100;
        resonanceApproach = $taskStatus.reso.recommended_approach ?? '';
        redFlags = $taskStatus.reso.red_flags ?? [];
      }
      if ($taskStatus.runs) {
        runs = $taskStatus.runs;
      }
      // [038] fix: "TOPLAM SİSTEM GÜVENİ" artık backend'in gerçek toplamıdır
      // (holistic_profile.overall_confidence = profile ajanlarının dürüst
      // ortalaması). Nesne sırasına göre 'son ajanın confidence'ı' gösterilmez.
      overallConfidence = $taskStatus.holistic_profile?.overall_confidence ?? 0;
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
        <div class="screen-card" style="padding: 8px 10px;">
          <div style="display: flex; justify-content: space-between; font-size: 10px; color: var(--text-dim); margin-bottom: 4px;">
            <span>{t[$currentLang].resonanceScoreLabel}</span>
            <strong style="color: var(--text-main); font-size: 11px;">%{resonanceScore.toFixed(0)}</strong>
          </div>
          <div style="height: 6px; background: #1f140e; border-radius: 3px; overflow: hidden; border: 1px solid #3d2b17;">
            <div style="height: 100%; width: {Math.max(5, resonanceScore)}%; background: #10b981; transition: width 0.4s ease;"></div>
          </div>
          {#if resonanceApproach}
            <div style="font-size: 9px; color: var(--text-muted); margin-top: 6px; line-height: 1.35;">
              <b style="color: var(--text-dim);">{t[$currentLang].approachLabel}:</b> {resonanceApproach}
            </div>
          {/if}
          {#if redFlags.length}
            <div style="font-size: 8px; color: #f87171; margin-top: 5px; line-height: 1.4;">
              <b>{t[$currentLang].redFlagsLabel}:</b>
              {#each redFlags as flag}
                <span style="display: inline-block; background: rgba(239,68,68,0.15); border: 1px solid rgba(239,68,68,0.4); padding: 1px 5px; border-radius: 3px; margin: 2px 3px 0 0;">{flag}</span>
              {/each}
            </div>
          {/if}
        </div>
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
          <label for="targetUrlInput" style="display: block; font-size: 10px; color: var(--text-dim); margin-bottom: 4px; font-weight: 600;">
            {t[$currentLang].targetUrlLabel}
          </label>
          <input 
            id="targetUrlInput"
            style="font-size: 13px; font-weight: 600; padding: 8px 12px;" 
            bind:value={targetUrl} 
            placeholder={t[$currentLang].targetUrlPlaceholder} 
            disabled={$isProcessing}
          />
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px;">
          <div>
            <label for="userRitualsInput" style="display: block; font-size: 9px; color: var(--text-muted); margin-bottom: 2px;">{t[$currentLang].ritualsLabel}</label>
            <input id="userRitualsInput" bind:value={userRituals} placeholder={t[$currentLang].ritualsPlaceholder} disabled={$isProcessing} />
          </div>
          <div>
            <label for="userPlaylistInput" style="display: block; font-size: 9px; color: var(--text-muted); margin-bottom: 2px;">{t[$currentLang].playlistLabel}</label>
            <input id="userPlaylistInput" bind:value={userPlaylist} placeholder={t[$currentLang].playlistPlaceholder} disabled={$isProcessing} />
          </div>
          <div>
            <label for="userEnviesInput" style="display: block; font-size: 9px; color: var(--text-muted); margin-bottom: 2px;">{t[$currentLang].enviesLabel}</label>
            <input id="userEnviesInput" bind:value={userEnvies} placeholder={t[$currentLang].enviesPlaceholder} disabled={$isProcessing} />
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
          {#if $isProcessing && $taskStatus?.task_id}
            <button class="btn-dark" style="padding: 8px 14px; font-size: 11px; color: #fca5a5;" on:click={cancelAnalysis}>
              İPTAL
            </button>
          {/if}
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
            {#if holisticProfile.passions?.data_confidence === false}
              <span style="font-size: 8px; font-weight: 800; background: #ef4444; color: #fff; padding: 1px 4px; border-radius: 3px; margin-left: 4px;" title="{holisticProfile.passions.fallback_reason || ''}">[FALLBACK]</span>
            {/if}
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
            {#if holisticProfile.frictions?.data_confidence === false}
              <span style="font-size: 8px; font-weight: 800; background: #ef4444; color: #fff; padding: 1px 4px; border-radius: 3px; margin-left: 4px;" title="{holisticProfile.frictions.fallback_reason || ''}">[FALLBACK]</span>
            {/if}
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
            {#if holisticProfile.cognitive?.data_confidence === false}
              <span style="font-size: 8px; font-weight: 800; background: #ef4444; color: #fff; padding: 1px 4px; border-radius: 3px; margin-left: 4px;" title="{holisticProfile.cognitive.fallback_reason || ''}">[FALLBACK]</span>
            {/if}
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
              <!-- P1-6: model tahmini mi, yoksa fallback mi — gizlenemez -->
              {#if holisticProfile.bridge.data_confidence === false || holisticProfile.bridge.fallback_reason}
                <span style="font-size: 9px; font-weight: 800; background: #ef4444; color: #fff; padding: 2px 6px; border-radius: 4px; margin-left: 6px;" title="{holisticProfile.bridge.fallback_reason || 'data_confidence=false'}">
                  [FALLBACK — KANIT DEĞİL: {holisticProfile.bridge.fallback_reason || 'düşük güven'}]
                </span>
              {/if}
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

    <!-- ==================== 4 FORENSİK DAMGA VE DERİNLİK RAPORU ==================== -->
    {#if followerAudit || timingForensics || depthReport}
    <div class="brass-plate" style="border: 1px solid var(--gold); display: flex; flex-direction: column; gap: 10px;">
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2a1e12; padding-bottom: 6px;">
        <span class="font-cinzel" style="font-size: 12px; font-weight: 800; color: var(--gold);">
          🏛️ 6 DAMGA FORENSİK KONTROLÜ
        </span>
        <span style="font-size: 9px; font-weight: 700; color: var(--accent-green); background: rgba(16,185,129,0.15); border: 1px solid var(--accent-green); padding: 2px 8px; border-radius: 4px;">
          ● {(followerAudit ? 1 : 0) + (timingForensics ? 1 : 0) + (depthReport ? 1 : 0) + (visualEvidence ? 1 : 0) + (shadowProfile ? 1 : 0) + (osintFootprint ? 1 : 0)} DOĞRULANMIŞ DAMGA
        </span>
      </div>

      <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
        <!-- 1. 🔍 TAKİPÇİ VE BOT DENETİMİ -->
        {#if followerAudit}
          <div class="screen-card" style="border-color: {followerAudit.verdict_code === 'healthy' ? 'rgba(16,185,129,0.5)' : followerAudit.verdict_code === 'inflated' ? 'rgba(239,68,68,0.5)' : 'rgba(245,158,11,0.5)'};">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <span class="font-cinzel" style="font-size: 10px; font-weight: 700; color: var(--gold);">
                {t[$currentLang].followerAuditTitle}
              </span>
              <span style="font-size: 9px; font-weight: 800; padding: 2px 6px; border-radius: 4px; {followerAudit.verdict_code === 'healthy' ? 'background: #10b981; color: #000;' : followerAudit.verdict_code === 'inflated' ? 'background: #ef4444; color: #fff;' : 'background: #f59e0b; color: #000;'}">
                {followerAudit.verdict_code === 'healthy' ? t[$currentLang].verdictHealthy : followerAudit.verdict_code === 'inflated' ? t[$currentLang].verdictInflated : followerAudit.verdict_code === 'suspicious' ? t[$currentLang].verdictSuspicious : t[$currentLang].verdictInsufficient}
              </span>
            </div>
            <div style="font-size: 9px; color: var(--text-dim); margin-bottom: 3px;">
              <b>{t[$currentLang].engagementRateLabel}:</b> %{followerAudit.engagement_rate !== undefined && followerAudit.engagement_rate !== null ? followerAudit.engagement_rate : '--'} ({followerAudit.expected_rate_range || 'N/A'}) | 
              <b>Takipçi:</b> {followerAudit.follower_count || 0}
            </div>
            {#if followerAudit.evidence?.length}
              <div style="font-size: 8px; color: var(--text-muted); line-height: 1.3; background: rgba(0,0,0,0.3); padding: 4px; border-radius: 4px;">
                {#each followerAudit.evidence.slice(0, 2) as ev}
                  <div>• {ev}</div>
                {/each}
              </div>
            {/if}
          </div>
        {/if}

        <!-- 2. ⏰ ZAMAN FORENSİĞİ -->
        {#if timingForensics}
          <div class="screen-card" style="border-color: rgba(6,182,212,0.5);">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
              <span class="font-cinzel" style="font-size: 10px; font-weight: 700; color: var(--accent-cyan);">
                {t[$currentLang].timingForensicsTitle}
              </span>
              <span style="font-size: 9px; font-weight: 700; color: #67e8f9;">
                UTC {timingForensics.peak_hour ?? '--'}
              </span>
            </div>
            <div style="font-size: 9px; color: var(--text-dim); margin-bottom: 3px;">
              <b>{t[$currentLang].nightOwlScoreLabel}:</b> %{((timingForensics.night_share || 0) * 100).toFixed(0)} | 
              <b>{t[$currentLang].tzShiftLabel}:</b> {timingForensics.median_drift_hours >= 0 ? '+' : ''}{timingForensics.median_drift_hours ?? 0}sa
            </div>
            {#if timingForensics.machine_note}
              <div style="font-size: 8px; color: var(--text-muted); line-height: 1.3; background: rgba(0,0,0,0.3); padding: 4px; border-radius: 4px;">
                ⏱️ {timingForensics.machine_note}
              </div>
            {/if}
          </div>
        {/if}
      </div>

      <!-- 3. 🧠 DERİNLİK VE GERÇEKLİK RAPORU + 4. 🛡️ ALINTI KALKANI -->
      {#if depthReport}
        <div class="screen-card" style="border-color: rgba(16,185,129,0.6); background: #0c140d;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="font-cinzel" style="font-size: 11px; font-weight: 800; color: var(--accent-green);">
                {t[$currentLang].depthReportTitle}
              </span>
              <span style="font-size: 9px; font-weight: 700; color: var(--gold);">
                {t[$currentLang].realityIndexLabel}: %{((depthReport.reality_index || 0) * 100).toFixed(0)}
              </span>
            </div>

            <!-- 4. 🛡️ KALKAN ROZETİ -->
            {#if depthReport.quote_guard}
              <span style="font-size: 9px; font-weight: 700; background: rgba(16,185,129,0.2); border: 1px solid var(--accent-green); color: #86efac; padding: 2px 6px; border-radius: 4px;">
                🛡️ {depthReport.quote_guard.kept || depthReport.reality_findings?.length || 0} {t[$currentLang].kalkanAyakta} ({depthReport.quote_guard.dropped_fake_quote || 0} {t[$currentLang].kalkanElenen})
              </span>
            {/if}
          </div>

          <!-- Gerçeklik Endeksi Çubuğu -->
          <div style="height: 6px; background: #1a120b; border-radius: 3px; overflow: hidden; border: 1px solid #3d2b17; margin-bottom: 6px;">
            <div style="height: 100%; width: {Math.max(5, (depthReport.reality_index || 0) * 100)}%; background: linear-gradient(90deg, #ef4444 0%, #f59e0b 50%, #10b981 100%); transition: width 0.4s ease;"></div>
          </div>

          {#if depthReport.essence_one_liner}
            <div style="font-size: 10px; color: var(--text-main); font-weight: 600; margin-bottom: 6px; font-style: italic;">
              "{depthReport.essence_one_liner}"
            </div>
          {/if}

          <!-- Bulgular ve Çelişkiler -->
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 6px;">
            {#if depthReport.reality_findings?.length}
              <div style="background: rgba(0,0,0,0.3); padding: 5px; border-radius: 4px; border: 1px solid rgba(16,185,129,0.3);">
                <div style="font-size: 9px; font-weight: 700; color: var(--accent-green); margin-bottom: 3px;">
                  ✓ {t[$currentLang].findingsTitle}
                </div>
                {#each depthReport.reality_findings.slice(0, 3) as f}
                  <div style="font-size: 8px; color: var(--text-dim); margin-bottom: 2px;">
                    <b style="color: #86efac;">{f.topic}:</b> {f.observation}
                    {#if f.evidence_quotes?.length}
                      <span style="color: #65a30d; font-style: italic;">("{f.evidence_quotes[0]}")</span>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}

            {#if depthReport.contradictions?.length}
              <div style="background: rgba(0,0,0,0.3); padding: 5px; border-radius: 4px; border: 1px solid rgba(239,68,68,0.3);">
                <div style="font-size: 9px; font-weight: 700; color: var(--accent-red); margin-bottom: 3px;">
                  ⚠️ {t[$currentLang].contradictionsTitle}
                </div>
                {#each depthReport.contradictions.slice(0, 3) as c}
                  <div style="font-size: 8px; color: #fca5a5; margin-bottom: 2px;">
                    <b style="color: #f87171;">{c.topic}:</b> {c.observation}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        </div>
      {/if}

    <!-- ==================== TELEMETRİ / ZEKÂ PANELİ ==================== -->
    {#if telemetry}
      <div class="screen-card" style="border-color: rgba(71, 85, 105, 0.4); background: #000000; box-shadow: inset 0 0 20px rgba(0,0,0,0.8), 0 0 10px rgba(255,255,255,0.02); margin-top: 10px;">
        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 6px; margin-bottom: 8px;">
          <span class="font-cinzel" style="font-size: 11px; font-weight: 800; color: #94a3b8; text-shadow: 0 0 5px rgba(148, 163, 184, 0.3);">
            📡 ZEKÂ PANELİ (TELEMETRİ)
          </span>
          <span style="font-size: 9px; font-weight: 700; color: #64748b;">
            CANLI VERİ
          </span>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 8px;">
          <div style="background: rgba(15,23,42,0.4); padding: 6px; border-radius: 4px; border: 1px solid rgba(51,65,85,0.4);">
            <div style="font-size: 8px; color: #64748b; margin-bottom: 2px; font-weight: 700;">CACHE HİT ORANI</div>
            <div style="font-size: 12px; color: #38bdf8; font-weight: 800;">{telemetry.cache_hit_rate || '0.0%'}</div>
          </div>
          <div style="background: rgba(15,23,42,0.4); padding: 6px; border-radius: 4px; border: 1px solid rgba(51,65,85,0.4);">
            <div style="font-size: 8px; color: #64748b; margin-bottom: 2px; font-weight: 700;">CACHE HIT</div>
            <div style="font-size: 12px; color: #4ade80; font-weight: 800;">{telemetry.cache_hits ?? 0}</div>
          </div>
          <div style="background: rgba(15,23,42,0.4); padding: 6px; border-radius: 4px; border: 1px solid rgba(51,65,85,0.4);">
            <div style="font-size: 8px; color: #64748b; margin-bottom: 2px; font-weight: 700;">GÖZLENEN LLM ÇAĞRISI</div>
            <div style="font-size: 12px; color: #a78bfa; font-weight: 800;">{telemetry.llm_calls_observed ?? 0}</div>
          </div>
        </div>
      </div>
    {/if}

      <!-- 6. 📸 GÖRSEL KANIT -->
      {#if visualEvidence}
        <div class="screen-card" style="border-color: rgba(236, 72, 153, 0.6); background: #1a0b16;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="font-cinzel" style="font-size: 11px; font-weight: 800; color: #f472b6;">
                📸 GÖRSEL KANIT (6. DAMGA)
              </span>
            </div>
          </div>
          <div style="font-size: 10px; color: #fbcfe8; font-weight: 600; margin-bottom: 4px;">
            Stil: {visualEvidence.aesthetic_style || 'Bilinmiyor'}
          </div>
          <div style="font-size: 8px; color: #f9a8d4; line-height: 1.3;">
            {visualEvidence.visual_evidence_summary || 'Özet bulunamadı.'}
          </div>
        </div>
      {/if}
    </div>
    {/if}

    <!-- ==================== 5. VE 6. DAMGALAR (YENİ) ==================== -->
    {#if shadowProfile}
      <div class="screen-card" style="border-color: rgba(139, 92, 246, 0.6); background: #1a1025; margin-top: 10px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="font-cinzel" style="font-size: 11px; font-weight: 800; color: #a78bfa;">
              🕳️ 5. DAMGA: GÖLGE PROFİLİ
              <!-- P1-6/P2-9: fallback veya güvensiz çıktı açıkça işaretlenir -->
              {#if shadowProfile.data_confidence === false || shadowProfile.fallback_reason}
                <span style="font-size: 9px; font-weight: 800; background: #ef4444; color: #fff; padding: 2px 6px; border-radius: 4px; margin-left: 6px;" title="{shadowProfile.fallback_reason || 'data_confidence=false'}">
                  [FALLBACK — KANIT DEĞİL]
                </span>
              {:else if shadowProfile._provenance?.source === 'llm' || shadowProfile._provenance?.source === 'llm_cache'}
                <span style="font-size: 9px; font-weight: 800; background: rgba(16,185,129,0.25); border: 1px solid #10b981; color: #6ee7b7; padding: 2px 6px; border-radius: 4px; margin-left: 6px;" title="LLM: {shadowProfile._provenance.model}">
                  [LLM: {shadowProfile._provenance.model?.split('/').pop()}]
                </span>
              {/if}
            </span>
            <span style="font-size: 9px; font-weight: 700; color: var(--gold);">
              Manipülasyon Skoru: %{((shadowProfile.dark_profile?.narcissism || 0) * 100).toFixed(0)}
            </span>
          </div>
        </div>
        
        <div style="font-size: 10px; color: #e9d5ff; font-style: italic; margin-bottom: 6px;">
          "{shadowProfile.message || 'Gölge dizisi oluşturulamadı'}"
        </div>
        
        <div style="background: rgba(0,0,0,0.3); padding: 5px; border-radius: 4px; border: 1px solid rgba(139,92,246,0.3);">
          <div style="font-size: 9px; font-weight: 700; color: #c4b5fd; margin-bottom: 3px;">
            🧠 NLP & Strateji
          </div>
          <div style="font-size: 8px; color: #ddd; margin-bottom: 4px;">
            {shadowProfile.strategy || 'Belirtilmedi'}
          </div>
          {#if shadowProfile.dark_profile}
            <div style="display: flex; gap: 8px; font-size: 8px; color: #c4b5fd;">
              <span>NAR: {shadowProfile.dark_profile.narcissism?.toFixed(2)}</span>
              <span>MAC: {shadowProfile.dark_profile.machiavellianism?.toFixed(2)}</span>
              <span>PSY: {shadowProfile.dark_profile.psychopathy?.toFixed(2)}</span>
            </div>
          {/if}
        </div>
      </div>
    {/if}

    {#if osintFootprint}
      <div class="screen-card" style="border-color: rgba(56, 189, 248, 0.6); background: #0c1a25; margin-top: 10px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="font-cinzel" style="font-size: 11px; font-weight: 800; color: #7dd3fc;">
              🌐 6. DAMGA: DİJİTAL AYAK İZİ
              {#if osintFootprint.fallback_reason}
                <span style="font-size: 9px; font-weight: 800; background: #ef4444; color: #fff; padding: 2px 6px; border-radius: 4px; margin-left: 6px;">
                  [SİMÜLASYON / API BAĞLANTISI YOK]
                </span>
              {/if}
            </span>
            <span style="font-size: 9px; font-weight: 700; color: var(--gold);">
              Ağ Eşleşme Skoru: %{((osintFootprint.digital_footprint_score || 0) * 100).toFixed(0)}
            </span>
          </div>
          
          <span style="font-size: 9px; font-weight: 700; background: rgba(56,189,248,0.2); border: 1px solid #7dd3fc; color: #bae6fd; padding: 2px 6px; border-radius: 4px;">
            {(osintFootprint.associated_platforms || []).length} Platform
          </span>
        </div>
        
        <div style="background: rgba(0,0,0,0.3); padding: 5px; border-radius: 4px; border: 1px solid rgba(56,189,248,0.3); font-size: 8px; color: #e0f2fe;">
          <b style="color: #7dd3fc;">Kanıtlar:</b> 
          {(osintFootprint.associated_platforms || []).join(', ') || 'Platform kaydı bulunamadı (Simülasyon/Olası Bot)'}
        </div>
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
              <!-- P2-9 PROVENANCE: bu çıktının kökeni. Damga yoksa kanıt sayılmaz. -->
              {#if isCompleted && run?.output_summary?._provenance}
                {@const prov = run.output_summary._provenance}
                <div style="margin-top: 2px;">
                  {#if prov.source === 'llm'}
                    <span style="font-size: 7px; font-weight: 800; background: rgba(16,185,129,0.2); border: 1px solid #10b981; color: #6ee7b7; padding: 1px 4px; border-radius: 3px;" title="Gerçek LLM çağrısı: {prov.model}">
                      LLM ✓ {prov.model?.split('/').pop() || ''}
                    </span>
                  {:else if prov.source === 'llm_cache'}
                    <span style="font-size: 7px; font-weight: 800; background: rgba(6,182,212,0.2); border: 1px solid #06b6d4; color: #67e8f9; padding: 1px 4px; border-radius: 3px;" title="Önbellekten gelen LLM yanıtı: {prov.model}">
                      CACHE {prov.model?.split('/').pop() || ''}
                    </span>
                  {:else if prov.source === 'deterministic'}
                    <span style="font-size: 7px; font-weight: 800; background: rgba(212,175,55,0.2); border: 1px solid var(--gold); color: var(--gold); padding: 1px 4px; border-radius: 3px;" title="Yerel hesaplama — LLM yok, tahmin yok">
                      DETERMİNİSTİK
                    </span>
                  {:else if prov.source === 'fallback'}
                    <span style="font-size: 7px; font-weight: 800; background: rgba(239,68,68,0.25); border: 1px solid #ef4444; color: #fca5a5; padding: 1px 4px; border-radius: 3px;" title="Fallback üretim: {prov.fallback_reason} — kanıt DEĞİL">
                      ⚠ FALLBACK
                    </span>
                  {:else}
                    <span style="font-size: 7px; font-weight: 800; background: rgba(100,116,139,0.2); border: 1px solid #64748b; color: #94a3b8; padding: 1px 4px; border-radius: 3px;" title="Köken izlenemedi">
                      ? KÖKEN YOK
                    </span>
                  {/if}
                </div>
              {/if}
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

      <PillarFeed {frequencyMap} {seismosEvents} {voidMap} {strataMap} {gravityMap} {pulseMap} {keyMatrix} />
    </div>

  </aside>
</div>
