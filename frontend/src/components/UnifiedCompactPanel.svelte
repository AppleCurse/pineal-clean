<script lang="ts">
  import { onMount, onDestroy, afterUpdate } from 'svelte';
  import { get } from 'svelte/store';
  import {
    clientId, apiFetch, apiToken, setApiToken, currentApiToken,
    isAuthFailure, isProcessing, logs, taskStatus, telemetryEvents,
    armEngaged, sigintEngaged, recordEngaged, keyUnlocked, powerEngaged
  } from '../store';
  import { currentLang, t } from '../i18n';
  import { playClick, playRunning, playHalt, playToggle, setSoundEnabled } from '../lib/consoleAudio';
  import {
    health, sysTelemetry, uplinkState, throttleIdx, THROTTLE_DETENTS,
    ttsRate, TTS_DETENTS, startHealthPoll, stopHealthPoll
  } from '../lib/telemetry';
  import AnalogGauge from './diesel/AnalogGauge.svelte';
  import ToggleSwitch from './diesel/ToggleSwitch.svelte';
  import KeyLock from './diesel/KeyLock.svelte';
  import EmergencyStop from './diesel/EmergencyStop.svelte';
  import SplitFlap from './diesel/SplitFlap.svelte';
  import LcdLogin from './diesel/LcdLogin.svelte';

  onMount(() => startHealthPoll());
  onDestroy(() => stopHealthPoll());

  // ==========================================
  // ANALOG ŞALTER & DÜĞME FONKSİYONLARI (USER CODE)
  // ==========================================
  function toggleArm() {
    armEngaged.update(v => {
      const next = !v;
      playToggle(next);
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'INFO', msg: next ? 'ARM: ENGAGED' : 'ARM: SAFE' }]);
      return next;
    });
  }

  function toggleSigint() {
    sigintEngaged.update(v => {
      const next = !v;
      playToggle(next);
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'INFO', msg: next ? 'SIGINT: OPEN' : 'SIGINT: CLOSED' }]);
      if (next && $isProcessing) {
        cancelAnalysis();
      }
      return next;
    });
  }

  function toggleRecord() {
    recordEngaged.update(v => {
      const next = !v;
      playToggle(next);
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'INFO', msg: next ? 'RECORD: ON' : 'RECORD: OFF' }]);
      return next;
    });
  }

  function toggleKey() {
    keyUnlocked.update(v => {
      const next = !v;
      playClick(next ? 280 : 120, 70);
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'INFO', msg: next ? 'KEY LOCK: UNLOCKED' : 'KEY LOCK: LOCKED' }]);
      return next;
    });
  }

  function togglePower() {
    powerEngaged.update(v => {
      const next = !v;
      playToggle(next);
      // POWER bildirimi RECORD'dan muaftır: bilinçli kesintinin kaydı kaybolmaz.
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: next ? 'INFO' : 'WARNING', msg: next ? 'POWER: UPLINK AÇILDI' : 'POWER: UPLINK KAPATILDI' }]);
      return next;
    });
  }

  function emergencyStop() {
    playHalt();
    const active = get(isProcessing) || get(taskStatus)?.status === 'processing';
    if (active) {
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'ERROR', msg: 'ACİL STOP: görev iptal emri verildi' }]);
      cancelAnalysis();
    } else {
      playClick(120, 90);
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'INFO', msg: 'ACİL STOP: hat boşta (iptal edilecek görev yok)' }]);
    }
  }

  // Düğmeler GERÇEK işlevlidir (süs değil):
  // THROTTLE → sağlık/telemetri ping aralığı · MIXTURE → Aspasia TTS hızı ·
  // PROP → konsol sesleri ana şalteri. Her detent loglanır.
  let throttleAngle = 45;
  let mixtureAngle = 120;
  let propAngle = 210;
  let soundOn = true;

  function cycleThrottle() {
    playClick(240, 30);
    throttleAngle = (throttleAngle + 45) % 360;
    throttleIdx.update(i => {
      const next = (i + 1) % THROTTLE_DETENTS.length;
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'INFO', msg: `THROTTLE: ping aralığı ${THROTTLE_DETENTS[next]} sn` }]);
      return next;
    });
  }

  function cycleMixture() {
    playClick(240, 30);
    mixtureAngle = (mixtureAngle + 45) % 360;
    const cur = TTS_DETENTS.indexOf(get(ttsRate));
    const next = TTS_DETENTS[(cur + 1) % TTS_DETENTS.length];
    ttsRate.set(next);
    logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'INFO', msg: `MIXTURE: Aspasia TTS hızı ${next}x` }]);
  }

  function cycleProp() {
    soundOn = !soundOn;
    setSoundEnabled(soundOn);
    propAngle = (propAngle + 45) % 360;
    if (soundOn) playClick(240, 30);
    logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'INFO', msg: soundOn ? 'PROP: konsol sesi AÇIK' : 'PROP: konsol sesi KAPALI' }]);
  }

  // Odometer (REC 00087)
  let odometer = 87;
  $: if ($logs.length > 0) {
    odometer = 87 + $logs.length;
  }

  // ==========================================
  // 13 AJAN LİSTESİ (KULLANICININ VERDİĞİ LİSTE)
  // ==========================================
  // <ROUTING-GENERATED-START do-not-edit>
  const agentList = [
    { id: "mirror_truth",          name: "MIRROR TRUTH",          color: "#10b981", primaryModel: "claude-sonnet-5",     backupModel: "gemini-3.7-flash",  via: "openrouter", capability: "strong_reasoning", glyph: "🪞" },
    { id: "autonomous_verifier",   name: "AUTONOMOUS VERIFIER",   color: "#a855f7", primaryModel: "claude-sonnet-5",   backupModel: "grok-4.6",   via: "openrouter", capability: "extract+judgment", glyph: "⚖️" },
    { id: "human_behavior",        name: "HUMAN BEHAVIOR",        color: "#f59e0b", primaryModel: "gpt-oss-120b",     backupModel: "gemini-3.7-flash",   via: "openrouter", capability: "strong_reasoning", glyph: "👤" },
    { id: "passion_mapper",        name: "PASSION MAPPER",        color: "#f59e0b", primaryModel: "gpt-oss-120b",     backupModel: "laguna-s-2.1:free",  via: "openrouter", capability: "strong_reasoning", glyph: "✨" },
    { id: "friction_detector",     name: "FRICTION & BOUNDS",     color: "#ef4444", primaryModel: "claude-sonnet-5",     backupModel: "deepseek-v4-pro",   via: "openrouter", capability: "strong_reasoning", glyph: "🛡️" },
    { id: "cognitive_profiler",    name: "COGNITIVE PROFILER",    color: "#06b6d4", primaryModel: "gpt-oss-120b",     backupModel: "deepseek-v4-flash",          via: "openrouter", capability: "strong_reasoning", glyph: "🧠" },
    { id: "resonance_calc",        name: "RESONANCE CALCULATOR",  color: "#3b82f6", primaryModel: "local-numpy",         backupModel: "—",                 via: "local",      capability: "calc",             glyph: "📐" },
    { id: "pattern_interrupt",     name: "PATTERN INTERRUPT",     color: "#dc2626", primaryModel: "gpt-oss-120b",     backupModel: "laguna-s-2.1:free", via: "openrouter", capability: "strong_reasoning", glyph: "⚡" },
    { id: "resonance_synthesizer", name: "AUTHENTIC BRIDGE",      color: "#10b981", primaryModel: "gpt-5.6-luna",     backupModel: "claude-sonnet-5",   via: "openrouter", capability: "synthesis",        glyph: "🌿" },
    { id: "vision_analyzer",       name: "VISION ANALYZER",       color: "#38bdf8", primaryModel: "gemini-3.7-flash",    backupModel: "grok-4.6",          via: "openrouter", capability: "vision",           glyph: "👁️" },
    { id: "osint_investigator",    name: "OSINT INVESTIGATOR",    color: "#f97316", primaryModel: "grok-4.6",            backupModel: "deepseek-v4-pro",   via: "openrouter",  capability: "osint_synthesis",  glyph: "🌐" },
    { id: "authenticity_auditor",  name: "AUTHENTICITY AUDITOR",  color: "#eab308", primaryModel: "deepseek-v4-flash",    backupModel: "gemini-3.7-flash",   via: "openrouter", capability: "vision+verify",   glyph: "🔍" },
    { id: "depth_analyst",         name: "DEPTH ANALYST",         color: "#8b5cf6", primaryModel: "deepseek-v4-pro",     backupModel: "claude-sonnet-5",   via: "openrouter", capability: "strong_reasoning", glyph: "💎" },
  ];
  
// <ROUTING-GENERATED-END>

  // --- İKİ DİLLİ ETİKETLER (EN gravür + TR alt satır) ---
  // Ajan TR adları ROUTING bloğunun dışında tutulur (üretilmiş blok korunur).
  const agentTr: Record<string, string> = {
    mirror_truth: 'HAKİKAT AYNASI',
    autonomous_verifier: 'OTONOM DOĞRULAYICI',
    human_behavior: 'İNSAN DAVRANIŞI',
    passion_mapper: 'TUTKU HARİTASI',
    friction_detector: 'SÜRTÜNME & SINIRLAR',
    cognitive_profiler: 'BİLİŞSEL PROFİL',
    resonance_calc: 'REZONANS HESABI',
    pattern_interrupt: 'ÖRÜNTÜ KESİCİ',
    resonance_synthesizer: 'SAHİCİ KÖPRÜ',
    vision_analyzer: 'GÖRÜ ANALİZİ',
    osint_investigator: 'OSINT ARAŞTIRMACI',
    authenticity_auditor: 'ÖZGÜNLÜK DENETÇİSİ',
    depth_analyst: 'DERİNLİK ANALİZİ',
  };
  const tabTr: Record<string, string> = {
    ASPASIA: 'ASPASİA', VISION: 'GÖRÜ', OSINT: 'OSINT',
    FRICTION: 'SÜRTÜNME', VERIFY: 'DOĞRULA',
  };
  function trStatus(s: string): string {
    const m: Record<string, string> = {
      ready: 'HAZIR', degraded: 'KISMÎ', failed: 'HATALI',
      unreachable: 'ERİŞİLEMEZ', unknown: 'BİLİNMEYEN',
      processing: 'İŞLENİYOR', completed: 'TAMAMLANDI',
    };
    return m[(s || '').toLowerCase()] || (s || '').toUpperCase();
  }

  // ==========================================
  // STATE & TELEMETRY
  // ==========================================
  export let targetUrl = "";
  export let userRituals = "";
  export let userPlaylist = "";
  export let userEnvies = "";
  let runs: Record<string, any> = {};
  let currentAgent = "";
  let taskState = "IDLE";
  let taskId = "";
  let overallConfidence = 0;
  let haltedReason: string | null = null;
  let holisticProfile: any = null;
  let followerAudit: any = null;
  let timingForensics: any = null;
  let depthReport: any = null;
  let visualEvidence: any = null;
  let shadowProfile: any = null;
  let osintFootprint: any = null;
  let resonanceCalc: any = null;

  // Active Tab: ASPASIA, VISION, OSINT, FRICTION, VERIFY
  let activeTab = 'ASPASIA';

  // Active Forensic Drawer / Modal: FOLLOWER, TIMING, DEPTH, VISUAL, SHADOW, OSINT
  let activeForensicModal: string | null = null;

  function toggleForensic(name: string) {
    playClick(350, 40);
    activeForensicModal = activeForensicModal === name ? null : name;
  }

  // Audio reactivity
  let prevAgent = '';
  let prevState = '';

  $: {
    if ($taskStatus?.current_agent && $taskStatus.current_agent !== prevAgent && $taskStatus.status === 'processing') {
      playRunning();
      prevAgent = $taskStatus.current_agent;
    }
    if ($taskStatus?.status && $taskStatus.status !== prevState) {
      if (String($taskStatus.status).startsWith('halted') || $taskStatus.status === 'failed') playHalt();
      prevState = $taskStatus.status;
    }
  }

  $: {
    if ($taskStatus) {
      if ($taskStatus.task_id) taskId = $taskStatus.task_id;
      if ($taskStatus.status) taskState = $taskStatus.status;
      if ($taskStatus.halted_reason !== undefined) haltedReason = $taskStatus.halted_reason;
      if ($taskStatus.current_agent) currentAgent = $taskStatus.current_agent;
      if ($taskStatus.runs) runs = $taskStatus.runs;
      if ($taskStatus.holistic_profile) holisticProfile = $taskStatus.holistic_profile;
      if ($taskStatus.follower_audit) followerAudit = $taskStatus.follower_audit;
      if ($taskStatus.timing_forensics) timingForensics = $taskStatus.timing_forensics;
      if ($taskStatus.depth_report) depthReport = $taskStatus.depth_report;
      if ($taskStatus.visual_evidence) visualEvidence = $taskStatus.visual_evidence;
      if ($taskStatus.shadow_profile) shadowProfile = $taskStatus.shadow_profile;
      if ($taskStatus.osint_footprint) osintFootprint = $taskStatus.osint_footprint;
      // resonance_calc sonucu runs.output_summary altında taşınır (gerçek anahtarlar).
      resonanceCalc = $taskStatus.runs?.resonance_calc?.output_summary || null;
      overallConfidence = $taskStatus.holistic_profile?.overall_confidence ?? 0;
    }
  }

  // ==========================================
  // ASPASIA CHAT & SPEECH
  // ==========================================
  let messages: {sender: string, text: string, time: string}[] = [
    { sender: 'ASPASIA', text: 'Provide a discreet OSINT sweep on recent financial flows into Aegean shell entities.', time: '14:32:11' },
    { sender: 'ASPASIA', text: 'Sweep initialized. 7 entities flagged. Flows routed through Cyprus → Luxembourg → BVI. Risk score: 0.78. Source confidence: high.', time: '14:32:47' },
    { sender: 'ASPASIA', text: 'Cross-reference with maritime tracking and flag-state anomalies.', time: '14:33:02' },
    { sender: 'ASPASIA', text: 'Cross-ref complete. 3 vessels flagged under flags of convenience. AIS spoofing detected on 2. Raw packet samples attached.', time: '14:33:41' }
  ];
  let inputMessage = "";
  let chatContainer: HTMLElement;
  let isSending = false;
  let attachedImage: string | null = null;
  let fileInput: HTMLInputElement;

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
    const nowTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
    const displayMsg = attachedImage ? `[GÖRSEL] ${inputMessage}` : inputMessage;
    messages = [...messages, { sender: 'SİZ', text: displayMsg, time: nowTime }];
    
    let currentInput = inputMessage;
    let currentImage = attachedImage;
    inputMessage = ""; 
    attachedImage = null; 
    isSending = true;
    playClick(280, 50);

    try {
      const activeAgentId = activeTab;

      // [UI-BRIDGE] ASPASIA serbest metni ÖNCE komut kanalına gider
      // (doğal dil niyet -> yapılandırılmış komut -> GERÇEK görev akışı;
      // ikinci bir orchestrator yok: /api/aspasia/command tek dispatch
      // kanalından /api/initiate akışına bağlanır). Kabul edilen komut
      // (accepted && task_id) görev kartına bağlanır. Reddedilen/boş
      // yanıtta aşağıdaki chat fallback'ine geçilir — mesaj kaybi yok.
      if (activeAgentId === 'ASPASIA' && currentInput.trim()) {
        try {
          const cmdRes = await apiFetch(`/api/aspasia/command`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ client_id: $clientId, user_message: currentInput })
          });
          const cmd = cmdRes.ok ? await cmdRes.json() : null;
          if (cmd && cmd.accepted && cmd.task_id) {
            taskStatus.update(s => ({ ...s, task_id: cmd.task_id, status: 'processing' }));
            const boundTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
            messages = [...messages, {
              sender: 'ASPASIA',
              text: `Görev başlatıldı: ${cmd.task_id} [${cmd.intent || 'run_profile_analysis'}]`,
              time: boundTime
            }];
            logs.update(l => [...l, { ts: boundTime, level: 'INFO', msg: `ASPASIA KOMUT kabul edildi -> görev ${cmd.task_id}` }]);
            isSending = false;
            return;
          }
        } catch (_cmdErr) {
          /* komut kanalı boşta/hatalı -> chat fallback (mesaj kaybi yok) */
        }
      }

      // [UI-BRIDGE] Chat ağızları: tüm sekmeler aynı tek /api/aspasia/chat
      // ağzını kullanır; sekme yalnız bağlam değiştirir.
      const chatUrl = activeAgentId === 'ASPASIA' ? '/api/aspasia/chat' : '/api/aspasia/chat';
      const payload: any = { client_id: $clientId, user_message: currentInput };
      if (currentImage) payload.image_data = currentImage;
      const res = await apiFetch(chatUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!res.ok) throw new Error(isAuthFailure(res) ? "Yetki hatası (PINEAL_TOKEN)" : "Ağ geçidi yanıt vermedi");
      const data = await res.json();
      const reply = data.message || data.error?.message || "Yanıt alındı.";
      const resTime = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
      messages = [...messages, { sender: 'ASPASIA', text: reply, time: resTime }];

      // Ses + yazı birlikte (Kullanıcının verdiği TTS kodu)
      if (typeof window !== 'undefined' && window.speechSynthesis) {
        window.speechSynthesis.cancel();
        const u = new SpeechSynthesisUtterance(reply);
        u.lang = $currentLang === 'tr' ? 'tr-TR' : 'en-US';
        u.rate = get(ttsRate);
        window.speechSynthesis.speak(u);
      }
    } catch (error: any) {
      messages = [...messages, { sender: 'SİSTEM', text: `HATA: ${error.message}`, time: nowTime }];
    } finally {
      isSending = false;
    }
  }

  function handleKeydown(e: KeyboardEvent) { if (e.key === 'Enter') sendMessage(); }

  export async function triggerAnalysis() {
    if (!targetUrl) return;
    // VAULT interlock: anahtar açılmadan ateşleme yok.
    if (!$keyUnlocked) {
      playHalt();
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'ERROR', msg: 'ATEŞLEME REDDEDİLDİ: VAULT anahtarı kilitli — önce anahtarı çevirin' }]);
      return;
    }
    if (!$armEngaged) {
      armEngaged.set(true);
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'INFO', msg: 'SİSTEM KİLİDİ AÇILDI: ARM otonom aktif edildi' }]);
    }
    isProcessing.set(true);
    playRunning();
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
      if (!res.ok) throw new Error(isAuthFailure(res) ? "Yetki hatası (PINEAL_TOKEN)" : "API hatası: " + res.statusText);
      const started = await res.json();
      if (started.task_id) taskStatus.update(s => ({ ...s, task_id: started.task_id, status: 'processing' }));
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: "INFO", msg: `ANALİZ EMRİ VERİLDİ: ${targetUrl}` }]);
    } catch (e: any) {
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: "ERROR", msg: `HATA: ${e.message}` }]);
      isProcessing.set(false);
    }
  }

  async function cancelAnalysis() {
    const activeTaskId = $taskStatus?.task_id;
    if (!activeTaskId) return;
    playHalt();
    await apiFetch(`/api/tasks/${activeTaskId}/cancel?client_id=${$clientId}`, { method: 'POST' });
  }

  afterUpdate(() => {
    if (chatContainer) chatContainer.scrollTop = chatContainer.scrollHeight;
  });
</script>

<div class="steampunk-console">
  <!-- ==================== ÜST SIRA: CANLI GÖSTERGELER + DURUM PANOSU ==================== -->
  <!-- İbreler /health + /api/telemetry ölçümlerine bağlıdır; veri yoksa park eder. -->
  <div class="top-dials-row">
    <LcdLogin />
    <div class="dials-cluster">
    <AnalogGauge
      label="LLM GATEWAY"
      tr="LLM GEÇİDİ"
      tone="red"
      value={$sysTelemetry.ok ? ($sysTelemetry.gateway ? 82 : 12) : null}
      sub={$sysTelemetry.ok ? ($sysTelemetry.gateway ? `CANLI · $${$sysTelemetry.spendUsd.toFixed(2)}` : 'BEKLEMEDE (STANDBY)') : '—'}
    />
    <AnalogGauge
      label="SCRAPER NODE"
      tr="KAZIYICI DÜĞÜM"
      tone="gold"
      value={$sysTelemetry.ok ? (($sysTelemetry.scraper || $sysTelemetry.browser) ? 82 : 12) : null}
      sub={$sysTelemetry.ok ? (($sysTelemetry.scraper || $sysTelemetry.browser) ? 'HAZIR (READY)' : 'TARAYICI YOK (NO BROWSER)') : '—'}
    />
    <AnalogGauge
      label="CORE ENGINE"
      tr="ÇEKİRDEK MOTOR"
      tone="green"
      value={$health.ok ? $health.integrityPct : null}
      sub={$health.ok ? `${$health.integrityPct}% · ${$health.status.toUpperCase()} (${trStatus($health.status)})` : '—'}
    />
    </div>
    <SplitFlap
      title="PINEAL · STATUS"
      titleTr="PİNEAL DURUM PANOSU"
      rows={[
        { k: 'LATENCY', ktr: 'GECİKME', v: $health.ok && $health.latencyMs !== null ? `${$health.latencyMs}ms` : '—' },
        { k: 'INTEGRITY', ktr: 'BÜTÜNLÜK', v: $health.ok ? `${$health.integrityPct}%` : '—' },
        { k: 'HAT', ktr: 'LINE', v: $uplinkState },
      ]}
      foot={$health.ok ? `SYS ${$health.status.toUpperCase()} · NOMINAL` : 'SYS UNREACHABLE'}
      footTr={$health.ok ? `SİS. ${trStatus($health.status)} · NOMİNAL` : 'SİS. ERİŞİLEMEZ'}
      online={$uplinkState === 'ONLINE' && $health.ok}
    />
    <SplitFlap
      title="SEFER · LEDGER"
      titleTr="GÖREV DEFTERİ"
      rows={[
        { k: 'HARCAMA', ktr: 'SPEND', v: $sysTelemetry.ok ? `$${$sysTelemetry.spendUsd.toFixed(4)}` : '—' },
        { k: 'TAVAN', ktr: 'CAP', v: $sysTelemetry.ok ? ($sysTelemetry.spendCapUsd > 0 ? `$${$sysTelemetry.spendCapUsd.toFixed(2)}` : 'YOK (NONE)') : '—' },
        { k: 'REZERV', ktr: 'RESV', v: $sysTelemetry.ok ? String($sysTelemetry.activeReservations) : '—' },
        { k: 'GÖREV', ktr: 'RUNS', v: $sysTelemetry.ok ? String($sysTelemetry.taskRuns) : '—' },
      ]}
      foot="BÜTÇE · QUOTA"
      footTr={$sysTelemetry.ok ? 'CANLI AKIŞ' : 'VERİ YOK'}
      online={$sysTelemetry.ok}
    />
  </div>

  <!-- ==================== ANA KOKPİT GÖVDESİ (3 SÜTUN) ==================== -->
  <div class="main-cockpit-grid">

    <!-- SOL PANEL: DONANIM VE ŞALTERLER -->
    <aside class="left-hardware-rack">
      <!-- 1. VAULT KEY LOCK (ateşleme interlock'u) -->
      <div class="hardware-module keylock-module">
        <div class="module-title">VAULT KEY LOCK<span class="module-tr">KASA ANAHTAR KİLİDİ</span></div>
        <KeyLock unlocked={$keyUnlocked} onToggle={toggleKey} />
        <span class="knob-detent">{$keyUnlocked ? 'AÇIK · ateş serbest' : 'KİLİTLİ'}</span>
      </div>

      <!-- 2. THROTTLE · MIXTURE · PROP (gerçek işlevli detentler) -->
      <div class="hardware-module knobs-module">
        <div class="module-title">THROTTLE &bull; MIXTURE &bull; PROP<span class="module-tr">GAZ · KARIŞIM · PERVANE</span></div>
        <div class="knobs-row">
          <div class="knob-col">
            <button class="knurled-knob" aria-label="Throttle: ping aralığı" style="transform: rotate({throttleAngle}deg);" on:click={cycleThrottle}>
              <div class="knob-notch"></div>
            </button>
            <span class="knob-label">THROTTLE</span>
            <span class="knob-tr">GAZ</span>
            <span class="knob-detent">{THROTTLE_DETENTS[$throttleIdx]} sn</span>
          </div>
          <div class="knob-col">
            <button class="knurled-knob" aria-label="Mixture: TTS hızı" style="transform: rotate({mixtureAngle}deg);" on:click={cycleMixture}>
              <div class="knob-notch"></div>
            </button>
            <span class="knob-label">MIXTURE</span>
            <span class="knob-tr">KARIŞIM</span>
            <span class="knob-detent">{$ttsRate}x</span>
          </div>
          <div class="knob-col">
            <button class="knurled-knob" aria-label="Prop: konsol sesi" style="transform: rotate({propAngle}deg);" on:click={cycleProp}>
              <div class="knob-notch"></div>
            </button>
            <span class="knob-label">PROP</span>
            <span class="knob-tr">PERVANE</span>
            <span class="knob-detent">{soundOn ? 'SES' : 'SESSİZ'}</span>
          </div>
        </div>
      </div>

      <!-- 3. POWER · ARM · RECORD · SIGINT -->
      <div class="hardware-module switches-module">
        <div class="module-title">POWER<span class="module-tr">GÜÇ</span></div>
        <div class="switches-row">
          <ToggleSwitch label="POWER" tr="GÜÇ" engaged={$powerEngaged} led="green" onToggle={togglePower} />
          <ToggleSwitch label="ARM" tr="KURMA" engaged={$armEngaged} led="green" onToggle={toggleArm} />
          <ToggleSwitch label="RECORD" tr="KAYIT" engaged={$recordEngaged} led="green" onToggle={toggleRecord} />
          <ToggleSwitch label="SIGINT" tr="SİNYAL" engaged={$sigintEngaged} led="red" onToggle={toggleSigint} />
        </div>
      </div>

      <!-- 4. EMERGENCY STOP (işleyen görevi iptal eder) -->
      <div class="hardware-module estop-module">
        <EmergencyStop armed={$isProcessing || taskState === 'processing'} onPress={emergencyStop} />
      </div>

      <!-- 4. REC ODOMETER COUNTER (00087) -->
      <div class="hardware-module odometer-module">
        <span class="counter-tag">REC <span class="tr-micro">(KAYIT)</span></span>
        <div class="odometer-bezel">
          <div class="odometer-digits">
            {#each String(odometer).padStart(5, '0').split('') as digit}
              <span class="odo-digit">{digit}</span>
            {/each}
          </div>
        </div>
      </div>

      <!-- 6. STATUS ACTIVE LAMP -->
      <div class="hardware-module status-module">
        <span class="status-title">STATUS<br>ACTIVE<br><span class="tr-micro">DURUM: AKTİF</span></span>
        <div class="big-jewel-lamp {$isProcessing ? 'lamp-pulse' : 'lamp-steady'}"></div>
      </div>

      <!-- 7. PINEAL TOKEN PLAQUE (canlı kasa durumu — uydurma seri no yok) -->
      <div class="hardware-module token-plaque">
        <div class="plaque-screw top-left"></div>
        <div class="plaque-screw top-right"></div>
        <div class="plaque-screw btm-left"></div>
        <div class="plaque-screw btm-right"></div>
        <div class="plaque-header">PINEAL TOKEN</div>
        <div class="plaque-tr">PİNEAL ANAHTARI</div>
        <div class="plaque-code">{$apiToken ? 'KASA · AÇIK' : 'KASA · KİLİTLİ'}</div>
        <div class="plaque-sub">{$clientId}</div>
      </div>
    </aside>

    <!-- ORTA PANEL: AGENT DECK • ASPASIA OBSERVER -->
    <main class="center-monitor-chassis">
      <div class="crt-screen-bezel">
        <div class="crt-screen-inner">
          <!-- Monitor Header -->
          <div class="crt-header">
            <div class="header-title-group">
              <span class="font-cinzel deck-title">AGENT DECK &bull; ASPASIA OBSERVER<span class="deck-tr">AJAN GÜVERTESİ • ASPASİA GÖZLEM</span></span>
              <span class="sound-wave-icon {isSending ? 'wave-active' : ''}">)))</span>
            </div>

            <!-- Tabs: ASPASIA, VISION, OSINT, FRICTION, VERIFY -->
            <div class="monitor-tabs-bar">
              {#each ['ASPASIA', 'VISION', 'OSINT', 'FRICTION', 'VERIFY'] as tab}
                <button 
                  class="monitor-tab-btn {activeTab === tab ? 'tab-selected' : ''}" 
                  on:click={() => { activeTab = tab; playClick(300, 30); }}
                >
                  {tab}<span class="tab-tr">{tabTr[tab]}</span>
                </button>
              {/each}
            </div>
          </div>

          <!-- Active Route Bar (Dinamik Telemetri) -->
          <div class="active-route-subbar">
            <div class="route-text">
              {#if ($isProcessing || taskState === 'processing') && currentAgent}
                <b style="color: var(--gold);">AKTİF (ACTIVE):</b> {currentAgent}
                &bull; <b style="color: var(--gold);">MODEL:</b> {runs[currentAgent]?.model || agentList.find(a => a.id === currentAgent)?.primaryModel || 'auto'}
                &bull; <b style="color: var(--gold);">YOL (VIA):</b> {runs[currentAgent]?.via || agentList.find(a => a.id === currentAgent)?.via || 'unified-router'}
              {:else if $isProcessing || taskState === 'processing'}
                <b style="color: var(--gold);">DURUM (STATUS):</b> İŞLENİYOR (Ajan başlatılıyor...)
              {:else if taskState === 'completed'}
                <b style="color: #22c55e;">DURUM (STATUS):</b> TAMAMLANDI (Tüm kanıtlar doğrulandı)
              {:else if taskState && taskState.startsWith('halted')}
                <b style="color: #ef4444;">DURUM (STATUS):</b> DURDURULDU ({haltedReason || taskState})
              {:else}
                <b style="color: var(--gold);">DURUM (STATUS):</b> BEKLEMEDE (Sistem Hazır &bull; Hedef Bekleniyor)
              {/if}
            </div>
            <div class="route-dots">
              <span class="dot-led {($isProcessing || taskState === 'processing') ? 'dot-green pulse' : 'dot-amber'}"></span>
            </div>
          </div>

          <!-- Hedef Profil Girişi (Kompakt Çubuk) -->
          <div class="quick-target-strip">
            <input 
              type="text" 
              bind:value={targetUrl} 
              placeholder="Hedef kullanıcı adı / URL (@kullanici) · Target username / URL..." 
              disabled={$isProcessing} 
            />
            <button 
              class="launch-btn {$armEngaged ? 'btn-armed' : 'btn-unarmed'}" 
              on:click={triggerAnalysis} 
              disabled={$isProcessing || !targetUrl}
            >
              {$isProcessing ? 'İŞLENİYOR (BUSY)...' : 'BAŞLAT (LAUNCH)'}
            </button>
          </div>

          <!-- Chat Dialogue Feed -->
          <div class="dialogue-scroll-area" bind:this={chatContainer}>
            {#each messages as msg}
              <div class="chat-row {msg.sender === 'SİZ' ? 'row-user' : 'row-aspasia'}">
                <div class="avatar-disc">
                  {#if msg.sender === 'SİZ'}
                    <span class="avatar-glyph">👤</span>
                  {:else}
                    <span class="avatar-glyph">🏛️</span>
                  {/if}
                </div>
                <div class="bubble-body">
                  <div class="bubble-text">{msg.text}</div>
                  <div class="bubble-footer">
                    <span class="msg-timestamp">{msg.time}</span>
                    <span class="check-marks">✓✓</span>
                  </div>
                </div>
              </div>
            {/each}
          </div>

          <!-- Input Bar -->
          <div class="monitor-input-tray">
            <button class="cam-btn" on:click={() => fileInput.click()} title="Görsel Yükle">
              📷
            </button>
            <input type="file" accept="image/*" bind:this={fileInput} on:change={handleImageUpload} style="display:none;" />
            <input 
              type="text" 
              class="terminal-input"
              bind:value={inputMessage} 
              on:keydown={handleKeydown} 
              placeholder="Komut girin · Enter command or query..." 
              disabled={isSending} 
            />
            <button class="brass-send-btn" on:click={sendMessage} disabled={isSending || (!inputMessage.trim() && !attachedImage)}>
              GÖNDER (SEND)
            </button>
          </div>
        </div>
      </div>
    </main>

    <!-- SAĞ PANEL: AJAN ZİNCİRİ (KULLANICININ VERDİĞİ KODUN TAM VE EKSİKSİZ UYARLAMASI) -->
    <aside class="right-agent-rack">
      <div class="rack-header">
        <span class="font-cinzel rack-title">AJAN ZİNCİRİ<span class="rack-tr">AGENT CHAIN · 13 CANLI AJAN</span></span>
        <div class="jewel-led led-on-green"></div>
      </div>

      <div class="agent-cards-stack">
        {#each agentList as agent, i}
          {@const run = runs[agent.id] || (agent.id === 'depth_analyst' ? runs['depth_forensics'] : null)}
          {@const isCompleted = run?.status === 'completed'}
          {@const isRunning = currentAgent === agent.id && ($isProcessing || taskState === 'processing')}
          {@const isHalted = run?.status === 'halted' || run?.status === 'failed'}
          {@const liveModel = run?.model || agent.primaryModel}
          {@const liveVia = run?.via || agent.via}
          <!-- W4: kanonik çağrı bağlayıcısı — run.output_summary._provenance
               üzerinden call_id okunur (LLM'siz/uydurma satır üretilmez). -->
          {@const provCallId = (run && run.output_summary && run.output_summary._provenance) ? (run.output_summary._provenance.call_id || '') : ''}

          <div class="agent-instrument-card {isRunning ? 'card-running' : isHalted ? 'card-halted' : isCompleted ? 'card-done' : 'card-wait'}">
            <div class="card-top-line">
              <!-- Antik Madalyon / İkon -->
              <div class="agent-medal {isRunning ? 'medal-pulse-red' : ''}">
                <span class="medal-symbol">{agent.glyph || '⚙️'}</span>
              </div>

              <div class="agent-info-meta">
                <div class="agent-title-text">{agent.name}</div>
                <div class="agent-tr">{agentTr[agent.id] || ''}</div>
                <div class="agent-spec-lines">
                  <div><b style="color: var(--gold);">DURUM:</b> {isCompleted ? 'TAMAM' : isHalted ? 'DURDU' : isRunning ? 'ÇALIŞIYOR' : 'BEKLİYOR'}</div>
                  <div><b style="color: var(--gold);">MODEL:</b> {liveModel}</div>
                  <div><b style="color: var(--gold);">YOL:</b> {liveVia}</div>
                  <div><b style="color: var(--gold);">ÇAĞRI:</b> {provCallId ? provCallId.slice(0, 14) + '…' : '—'}</div>
                </div>
              </div>

              <!-- İlerleme Çubuğu -->
              <div class="agent-meter-bar">
                <div 
                  class="meter-fill {isCompleted ? 'fill-green' : isRunning ? 'fill-running-red' : isHalted ? 'fill-red' : 'fill-dim'}"
                  style="width: {isCompleted ? '100%' : isRunning ? '65%' : isHalted ? '100%' : '0%'};"
                ></div>
              </div>
            </div>
          </div>
        {/each}
      </div>
    </aside>

  </div>

  <!-- ==================== ALT SIRA: 6 ADLİ DAMGA YUVARLAK BUTONU ==================== -->
  <footer class="bottom-forensic-bar">
    <div class="forensic-buttons-track">
      <button class="round-brass-btn {activeForensicModal === 'follower' ? 'btn-active' : ''}" on:click={() => toggleForensic('follower')}>
        <div class="btn-inner-disc">
          <span class="forensic-icon">🕸️</span>
        </div>
        <span class="forensic-name">FOLLOWER</span>
        <span class="forensic-tr">TAKİPÇİ</span>
      </button>

      <button class="round-brass-btn {activeForensicModal === 'timing' ? 'btn-active' : ''}" on:click={() => toggleForensic('timing')}>
        <div class="btn-inner-disc">
          <span class="forensic-icon">⏱️</span>
        </div>
        <span class="forensic-name">TIMING</span>
        <span class="forensic-tr">ZAMANLAMA</span>
      </button>

      <button class="round-brass-btn {activeForensicModal === 'depth' ? 'btn-active' : ''}" on:click={() => toggleForensic('depth')}>
        <div class="btn-inner-disc">
          <span class="forensic-icon">📑</span>
        </div>
        <span class="forensic-name">DEPTH</span>
        <span class="forensic-tr">DERİNLİK</span>
      </button>

      <button class="round-brass-btn {activeForensicModal === 'visual' ? 'btn-active' : ''}" on:click={() => toggleForensic('visual')}>
        <div class="btn-inner-disc">
          <span class="forensic-icon">👁️</span>
        </div>
        <span class="forensic-name">VISUAL</span>
        <span class="forensic-tr">GÖRSEL</span>
      </button>

      <button class="round-brass-btn {activeForensicModal === 'shadow' ? 'btn-active' : ''}" on:click={() => toggleForensic('shadow')}>
        <div class="btn-inner-disc">
          <span class="forensic-icon">🎭</span>
        </div>
        <span class="forensic-name">SHADOW</span>
        <span class="forensic-tr">GÖLGE</span>
      </button>

      <button class="round-brass-btn {activeForensicModal === 'osint' ? 'btn-active' : ''}" on:click={() => toggleForensic('osint')}>
        <div class="btn-inner-disc">
          <span class="forensic-icon">🌐</span>
        </div>
        <span class="forensic-name">OSINT</span>
        <span class="forensic-tr">OSINT</span>
      </button>

      <button class="round-brass-btn {activeForensicModal === 'resonance' ? 'btn-active' : ''}" on:click={() => toggleForensic('resonance')}>
        <div class="btn-inner-disc">
          <span class="forensic-icon">🎯</span>
        </div>
        <span class="forensic-name">RESONANCE</span>
        <span class="forensic-tr">REZONANS</span>
      </button>
    </div>
  </footer>

  <!-- ==================== DAMGA AÇILIR PANELİ (POPUP DRAWER) ==================== -->
  {#if activeForensicModal}
    <div class="forensic-modal-backdrop" role="presentation" on:click={() => activeForensicModal = null} on:keydown={(e) => { if (e.key === 'Escape') activeForensicModal = null; }}>
      <div class="forensic-modal-card" role="dialog" aria-modal="true" tabindex="-1" on:click|stopPropagation on:keydown|stopPropagation>
        <div class="modal-header-brass">
          <span class="font-cinzel modal-title">ADLİ RAPOR: {activeForensicModal.toUpperCase()}</span>
          <button class="modal-close" on:click={() => activeForensicModal = null}>✕</button>
        </div>
        <div class="modal-content-body">
          {#if activeForensicModal === 'follower' && followerAudit}
            <div class="report-box">
              <h4>Takipçi & Kitle Denetimi</h4>
              <!-- W2: UI Türkce metin eslemek yerine makine-okunur verdict_code'u okur -->
              <p>Hüküm: {followerAudit.verdict || 'BİLİNMİYOR'} <span style="opacity:0.7;">({followerAudit.verdict_code || 'unknown'})</span></p>
              <p>Takipçi: {followerAudit.follower_count ?? 0} · Takip: {followerAudit.following_count ?? 'ölçülmedi'} · Gönderi: {followerAudit.post_count ?? 0}</p>
              <p>Etkileşim: {followerAudit.engagement_rate ?? '—'} (beklenen: {followerAudit.expected_rate_range || 'N/A'})</p>
              <p>Veri Tamamlık: %{((followerAudit.data_completeness ?? 0) * 100).toFixed(0)}</p>
            </div>
          {:else if activeForensicModal === 'timing' && timingForensics}
            <div class="report-box">
              <h4>Zaman & Sirkadiyen Forensik</h4>
              <!-- W1: GERÇEK backend anahtarları (timing_forensics çıktısı):
                   night_share, peak_hour, median_drift_hours -->
              <p>Gece Payı: %{((timingForensics.night_share ?? 0) * 100).toFixed(0)}</p>
              <p>Tepe Saati: {timingForensics.peak_hour ?? '—'}</p>
              <p>Medyan Drift: {timingForensics.median_drift_hours ?? '—'} saat</p>
            </div>
          {:else if activeForensicModal === 'resonance' && resonanceCalc}
            <div class="report-box">
              <h4>Rezonans & Yaklaşım Önerisi</h4>
              <!-- resonance_calc GERÇEK çıktısı: compatibility_score,
                   recommended_approach, red_flags (runs.output_summary) -->
              <p>Uyumluluk: %{((resonanceCalc.compatibility_score ?? 0) * 100).toFixed(0)}</p>
              <p>Önerilen Yaklaşım: {resonanceCalc.recommended_approach || '—'}</p>
              <p>Kırmızı Bayraklar: {(resonanceCalc.red_flags || []).join(', ') || 'Yok'}</p>
            </div>
          {:else if activeForensicModal === 'depth' && depthReport}
            <div class="report-box">
              <h4>Derinlik & Alıntı Kalkanı</h4>
              <p>Gerçeklik Skoru: %{((depthReport.reality_index || 0) * 100).toFixed(0)}</p>
              <p>Özet: {depthReport.essence_one_liner || 'Kanıtlar incelendi.'}</p>
            </div>
          {:else if activeForensicModal === 'visual' && visualEvidence}
            <div class="report-box">
              <h4>Görsel & Estetik Damga</h4>
              <p>Stil: {visualEvidence.aesthetic_style || 'Klasik'}</p>
              <p>Özet: {visualEvidence.visual_evidence_summary || 'Fotoğraf analiz edildi.'}</p>
            </div>
          {:else if activeForensicModal === 'shadow' && shadowProfile}
            <div class="report-box">
              <h4>Gölge Profili (Karanlık Üçlü)</h4>
              <p>Narsisizm: {shadowProfile.dark_profile?.narcissism ?? 0}</p>
              <p>Strateji: {shadowProfile.strategy || 'Doğal profil'}</p>
            </div>
          {:else if activeForensicModal === 'osint' && osintFootprint}
            <div class="report-box">
              <h4>OSINT Dijital Ayak İzi</h4>
              <p>Platform Eşleşmesi: {(osintFootprint.associated_platforms || []).join(', ') || 'Temiz'}</p>
            </div>
          {:else}
            <div class="report-box">
              <p style="color: var(--text-dim);">Bu modül için henüz analiz çalıştırılmadı veya hedef veri bekleniyor.</p>
            </div>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  /* ===================================================
     HERETIC VICTORIAN STEAMPUNK INSTRUMENT CONSOLE CSS
     =================================================== */
  .steampunk-console {
    background: radial-gradient(circle at center, #22140a 0%, #140b05 100%);
    border: 3px solid #7d5b32;
    box-shadow: inset 0 0 40px rgba(0,0,0,0.9), 0 15px 40px rgba(0,0,0,0.95);
    border-radius: 14px;
    padding: 16px;
    display: flex;
    flex-direction: column;
    gap: 16px;
    position: relative;
  }

  /* --- TOP DIALS ROW (canlı göstergeler + split-flap pano) --- */
  .top-dials-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 20px;
    padding-bottom: 8px;
    flex-wrap: wrap;
  }
  .dials-cluster {
    display: flex;
    gap: 28px;
    flex-wrap: wrap;
    justify-content: center;
    align-items: flex-start;
  }

  /* --- MAIN COCKPIT 3-COLUMN GRID --- */
  .main-cockpit-grid {
    display: grid;
    grid-template-columns: 210px 1fr 280px;
    gap: 16px;
    align-items: stretch;
  }

  /* --- LEFT HARDWARE RACK --- */
  .left-hardware-rack {
    background: #1a1008;
    border: 2px solid #5a3d1c;
    border-radius: 8px;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 10px;
    box-shadow: inset 0 0 20px rgba(0,0,0,0.8);
  }

  .hardware-module {
    background: #23160c;
    border: 1px solid #4a3014;
    border-radius: 6px;
    padding: 8px;
    display: flex;
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .module-title {
    font-family: 'Cinzel', serif;
    font-size: 8px;
    font-weight: 800;
    color: var(--gold);
    letter-spacing: 0.8px;
    margin-bottom: 6px;
  }

  /* Knobs (KeyLock bileşenine taşındı) */
  .knobs-row {
    display: flex;
    justify-content: space-around;
    width: 100%;
    gap: 4px;
  }
  .knob-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
  }
  .knurled-knob {
    width: 32px;
    height: 32px;
    border-radius: 50%;
    background: radial-gradient(circle, #7a5629 0%, #3a220e 100%);
    border: 2px dashed #99733d;
    box-shadow: 0 2px 5px rgba(0,0,0,0.8);
    cursor: pointer;
    position: relative;
    transition: transform 0.2s ease;
  }
  .knob-notch {
    position: absolute;
    top: 2px;
    left: 14px;
    width: 4px;
    height: 7px;
    background: #fff;
    border-radius: 1px;
  }
  .knob-label {
    font-size: 6px;
    color: var(--text-dim);
    font-weight: 700;
  }

  /* Switches (ToggleSwitch bileşenleri; 4'lü sıra) */
  .switches-row {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    width: 100%;
    gap: 2px;
  }
  .knob-detent {
    font-family: 'JetBrains Mono', monospace;
    font-size: 7px;
    font-weight: 700;
    color: #7dfcd0;
    background: #050302;
    border: 1px solid #3d2b17;
    border-radius: 2px;
    padding: 1px 5px;
    margin-top: 2px;
    white-space: nowrap;
  }
  .estop-module {
    padding: 4px 8px 8px;
  }
  .jewel-led {
    width: 7px;
    height: 7px;
    border-radius: 50%;
  }
  .led-on-green {
    background: #10b981;
    box-shadow: 0 0 8px #10b981, 0 0 2px #fff;
  }

  /* Odometer */
  .odometer-module {
    flex-direction: row;
    justify-content: space-between;
    padding: 6px 10px;
  }
  .counter-tag {
    font-size: 8px;
    font-weight: 800;
    color: var(--gold);
  }
  .odometer-bezel {
    background: #0d0703;
    border: 1px solid #5a3d1c;
    padding: 2px 6px;
    border-radius: 3px;
    box-shadow: inset 0 0 5px #000;
  }
  .odometer-digits {
    display: flex;
    gap: 3px;
  }
  .odo-digit {
    background: #000;
    color: #fff;
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 800;
    padding: 1px 3px;
    border-radius: 2px;
    border: 1px solid #222;
  }

  /* Status Lamp */
  .status-module {
    flex-direction: row;
    justify-content: space-between;
    padding: 6px 12px;
  }
  .status-title {
    font-size: 8px;
    font-weight: 800;
    color: var(--gold);
    text-align: left;
    line-height: 1.1;
  }
  .big-jewel-lamp {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #10b981;
    border: 2px solid #5a3d1c;
    box-shadow: 0 0 12px #10b981;
  }
  .lamp-pulse {
    animation: lampBlink 1s infinite alternate;
  }
  @keyframes lampBlink {
    from { opacity: 0.4; box-shadow: 0 0 4px #10b981; }
    to { opacity: 1; box-shadow: 0 0 16px #10b981; }
  }

  /* Token Plaque */
  .token-plaque {
    position: relative;
    background: linear-gradient(145deg, #a67c3b 0%, #684a1d 100%);
    border: 1px solid #d4af37;
    color: #0d0703;
    padding: 6px;
    box-shadow: inset 0 1px 1px #fff6, 0 3px 6px rgba(0,0,0,0.6);
  }
  .plaque-screw {
    position: absolute;
    width: 4px;
    height: 4px;
    border-radius: 50%;
    background: #2a1a08;
    box-shadow: inset 0 1px 0 #000;
  }
  .plaque-screw.top-left { top: 3px; left: 3px; }
  .plaque-screw.top-right { top: 3px; right: 3px; }
  .plaque-screw.btm-left { bottom: 3px; left: 3px; }
  .plaque-screw.btm-right { bottom: 3px; right: 3px; }
  .plaque-header { font-family: 'Cinzel', serif; font-size: 8px; font-weight: 900; letter-spacing: 0.5px; }
  .plaque-code { font-family: 'JetBrains Mono', monospace; font-size: 9px; font-weight: 800; letter-spacing: 1px; }
  .plaque-sub { font-family: 'JetBrains Mono', monospace; font-size: 7px; font-weight: 500; letter-spacing: 0.5px; opacity: 0.75; margin-top: 2px; }

  /* --- CENTER MONITOR CHASSIS --- */
  .center-monitor-chassis {
    display: flex;
    flex-direction: column;
  }

  .crt-screen-bezel {
    background: #1c1109;
    border: 3px solid #7d5b32;
    border-radius: 10px;
    padding: 8px;
    box-shadow: inset 0 0 15px rgba(0,0,0,0.9);
    height: 100%;
    display: flex;
    flex-direction: column;
  }

  .crt-screen-inner {
    background: #080604;
    border: 2px solid #2a180b;
    border-radius: 6px;
    padding: 10px;
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .crt-header {
    display: flex;
    flex-direction: column;
    gap: 8px;
    border-bottom: 1px solid #2a180b;
    padding-bottom: 8px;
  }

  .header-title-group {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .deck-title {
    font-size: 11px;
    font-weight: 800;
    color: var(--gold);
    letter-spacing: 1px;
  }

  .sound-wave-icon {
    color: #10b981;
    font-weight: 900;
    font-size: 12px;
  }
  .wave-active {
    animation: wavePulse 0.5s infinite alternate;
  }
  @keyframes wavePulse {
    from { color: #10b981; text-shadow: 0 0 2px #10b981; }
    to { color: #34d399; text-shadow: 0 0 10px #34d399; }
  }

  /* Monitor Tabs */
  .monitor-tabs-bar {
    display: flex;
    gap: 6px;
  }
  .monitor-tab-btn {
    flex: 1;
    background: #170d06;
    border: 1px solid #4a3014;
    color: var(--text-dim);
    font-family: 'Cinzel', serif;
    font-size: 9px;
    font-weight: 700;
    padding: 4px 6px;
    border-radius: 4px;
    cursor: pointer;
    transition: all 0.2s;
  }
  .monitor-tab-btn.tab-selected {
    background: linear-gradient(180deg, #99733d 0%, #5a3d1c 100%);
    color: #fff;
    border-color: var(--gold);
    box-shadow: 0 0 8px rgba(212,175,55,0.4);
  }

  /* Active Route Subbar */
  .active-route-subbar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    background: #110904;
    border: 1px solid #331d0b;
    padding: 4px 8px;
    border-radius: 4px;
    font-size: 8px;
    letter-spacing: 0.4px;
  }
  .route-text {
    color: var(--text-muted);
  }
  .route-dots {
    display: flex;
    gap: 4px;
  }
  .dot-led {
    width: 6px;
    height: 6px;
    border-radius: 50%;
  }
  .dot-green { background: #10b981; box-shadow: 0 0 4px #10b981; }
  .dot-amber { background: #f59e0b; box-shadow: 0 0 4px #f59e0b; }

  /* Quick Target Strip */
  .quick-target-strip {
    display: flex;
    gap: 6px;
  }
  .quick-target-strip input {
    flex: 1;
    background: #0d0703;
    border: 1px solid #3d230f;
    color: #fff;
    font-size: 11px;
    padding: 6px 10px;
    border-radius: 4px;
  }
  .launch-btn {
    font-family: 'Cinzel', serif;
    font-size: 10px;
    font-weight: 800;
    padding: 6px 14px;
    border-radius: 4px;
    cursor: pointer;
  }
  .btn-armed {
    background: linear-gradient(180deg, #10b981 0%, #065f46 100%);
    color: #fff;
    border: 1px solid #34d399;
    box-shadow: 0 0 10px rgba(16,185,129,0.5);
  }
  .btn-unarmed {
    background: #2a1e12;
    color: var(--text-muted);
    border: 1px solid #3d2b17;
  }

  /* Dialogue Area */
  .dialogue-scroll-area {
    flex: 1;
    min-height: 250px;
    max-height: 320px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 8px;
    padding-right: 4px;
  }
  .chat-row {
    display: flex;
    gap: 8px;
    align-items: flex-start;
  }
  .row-user {
    flex-direction: row-reverse;
  }
  .avatar-disc {
    width: 26px;
    height: 26px;
    border-radius: 50%;
    background: #1f1309;
    border: 1px solid #6b4e2a;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .avatar-glyph {
    font-size: 13px;
  }
  .bubble-body {
    background: #140d07;
    border: 1px solid #3d2714;
    border-radius: 6px;
    padding: 8px 10px;
    max-width: 85%;
  }
  .row-user .bubble-body {
    background: #241408;
    border-color: #7d5021;
  }
  .bubble-text {
    font-size: 11px;
    color: #f1e9da;
    line-height: 1.45;
  }
  .bubble-footer {
    display: flex;
    justify-content: flex-end;
    align-items: center;
    gap: 4px;
    margin-top: 4px;
    font-size: 8px;
    color: var(--text-muted);
  }
  .check-marks {
    color: #10b981;
  }

  /* Monitor Input Tray */
  .monitor-input-tray {
    display: flex;
    gap: 6px;
    align-items: center;
    border-top: 1px solid #2a180b;
    padding-top: 8px;
  }
  .cam-btn {
    background: #1f1309;
    border: 1px solid #5a3d1c;
    color: #fff;
    padding: 6px 10px;
    border-radius: 4px;
    cursor: pointer;
  }
  .terminal-input {
    flex: 1;
    background: #0c0703;
    border: 1px solid #4a2c12;
    color: #fff;
    font-size: 11px;
    padding: 6px 10px;
    border-radius: 4px;
  }
  .brass-send-btn {
    background: linear-gradient(180deg, #d4af37 0%, #8a6332 100%);
    color: #120904;
    font-family: 'Cinzel', serif;
    font-size: 11px;
    font-weight: 800;
    padding: 6px 16px;
    border-radius: 4px;
    border: 1px solid #ffd700;
    cursor: pointer;
    box-shadow: 0 2px 4px rgba(0,0,0,0.6);
  }

  /* --- RIGHT AGENT RACK --- */
  .right-agent-rack {
    background: #1a1008;
    border: 2px solid #5a3d1c;
    border-radius: 8px;
    padding: 10px;
    display: flex;
    flex-direction: column;
    gap: 8px;
    box-shadow: inset 0 0 20px rgba(0,0,0,0.8);
    max-height: 520px;
    overflow-y: auto;
  }

  .rack-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid #3d2714;
    padding-bottom: 6px;
  }
  .rack-title {
    font-size: 11px;
    font-weight: 800;
    color: var(--gold);
    letter-spacing: 1px;
  }

  .agent-cards-stack {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .agent-instrument-card {
    background: #140c06;
    border: 1px solid #3d2714;
    border-radius: 5px;
    padding: 6px 8px;
    transition: all 0.2s;
  }
  .card-running {
    border-color: #ef4444;
    box-shadow: 0 0 10px rgba(239,68,68,0.3);
  }
  .card-done {
    border-color: #10b981;
  }

  .card-top-line {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .agent-medal {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: radial-gradient(circle, #7a5629 0%, #3a220e 100%);
    border: 1px solid #b8860b;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
  }
  .medal-pulse-red {
    border-color: #ef4444;
    box-shadow: 0 0 8px #ef4444;
    animation: medalBlink 1s infinite alternate;
  }
  @keyframes medalBlink {
    from { box-shadow: 0 0 2px #ef4444; }
    to { box-shadow: 0 0 10px #ef4444; }
  }
  .medal-symbol {
    font-size: 11px;
  }

  .agent-info-meta {
    flex: 1;
    min-width: 0;
  }
  .agent-title-text {
    font-family: 'Cinzel', serif;
    font-size: 9px;
    font-weight: 800;
    color: #e2d7c5;
    letter-spacing: 0.5px;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .agent-spec-lines {
    font-size: 7px;
    color: var(--text-muted);
    line-height: 1.25;
    margin-top: 1px;
  }

  .agent-meter-bar {
    width: 50px;
    height: 4px;
    background: #000;
    border: 1px solid #331d0b;
    border-radius: 2px;
    overflow: hidden;
    flex-shrink: 0;
  }
  .meter-fill {
    height: 100%;
    transition: width 0.3s;
  }
  .fill-green {
    background: #10b981;
    box-shadow: 0 0 6px #10b981;
  }
  .fill-running-red {
    background: linear-gradient(90deg, #ef4444, #f59e0b);
    box-shadow: 0 0 8px #ef4444;
    animation: barPulse 1s infinite alternate;
  }
  @keyframes barPulse {
    from { opacity: 0.7; }
    to { opacity: 1; }
  }
  .fill-red { background: #ef4444; }
  .fill-dim { background: transparent; }

  /* --- İKİ DİLLİ ALT SATIRLAR (TR) --- */
  .module-tr { display: block; font-family: 'JetBrains Mono', monospace; font-size: 7px; font-weight: 500; color: var(--text-muted); letter-spacing: 0.4px; margin-top: 1px; }
  .knob-tr { font-family: 'JetBrains Mono', monospace; font-size: 6px; font-weight: 700; color: var(--text-muted); }
  .tr-micro { font-family: 'JetBrains Mono', monospace; font-size: 7px; color: var(--text-muted); }
  .deck-tr { display: block; font-family: 'JetBrains Mono', monospace; font-size: 7px; font-weight: 500; color: var(--text-muted); letter-spacing: 0.8px; margin-top: 1px; }
  .tab-tr { display: block; font-family: 'JetBrains Mono', monospace; font-size: 6px; font-weight: 500; color: var(--text-muted); }
  .rack-tr { display: block; font-family: 'JetBrains Mono', monospace; font-size: 7px; font-weight: 500; color: var(--text-muted); letter-spacing: 0.8px; }
  .agent-tr { font-family: 'JetBrains Mono', monospace; font-size: 7px; color: var(--text-muted); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
  .forensic-tr { font-family: 'JetBrains Mono', monospace; font-size: 6px; font-weight: 700; color: var(--text-muted); }
  .plaque-tr { font-family: 'JetBrains Mono', monospace; font-size: 6px; font-weight: 700; letter-spacing: 0.5px; opacity: 0.7; }

  /* --- BOTTOM FORENSIC BAR --- */
  .bottom-forensic-bar {
    background: #170e06;
    border: 2px solid #5a3d1c;
    border-radius: 8px;
    padding: 8px 12px;
    box-shadow: inset 0 0 10px #000;
  }
  .forensic-buttons-track {
    display: flex;
    justify-content: space-around;
    align-items: center;
  }
  .round-brass-btn {
    background: transparent;
    border: none;
    cursor: pointer;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 4px;
    transition: transform 0.15s;
  }
  .round-brass-btn:hover {
    transform: translateY(-2px);
  }
  .btn-inner-disc {
    width: 44px;
    height: 44px;
    border-radius: 50%;
    background: radial-gradient(circle, #5a3d1c 0%, #2a1a08 100%);
    border: 2px solid #b8860b;
    box-shadow: 0 3px 6px rgba(0,0,0,0.8), inset 0 1px 1px #fff3;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  .round-brass-btn.btn-active .btn-inner-disc {
    border-color: #10b981;
    box-shadow: 0 0 12px #10b981, inset 0 0 6px #10b981;
  }
  .forensic-icon {
    font-size: 18px;
  }
  .forensic-name {
    font-family: 'Cinzel', serif;
    font-size: 8px;
    font-weight: 800;
    color: var(--gold);
    letter-spacing: 0.8px;
  }

  /* --- FORENSIC MODAL POPUP --- */
  .forensic-modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    background: rgba(0,0,0,0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
  }
  .forensic-modal-card {
    background: #1c1109;
    border: 2px solid var(--gold);
    border-radius: 8px;
    width: 90%;
    max-width: 500px;
    box-shadow: 0 10px 30px rgba(0,0,0,0.9);
    overflow: hidden;
  }
  .modal-header-brass {
    background: linear-gradient(145deg, #d4af37, #8a6332);
    color: #120904;
    padding: 8px 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .modal-title {
    font-size: 11px;
    font-weight: 900;
    letter-spacing: 1px;
  }
  .modal-close {
    background: none;
    border: none;
    font-size: 14px;
    font-weight: 900;
    cursor: pointer;
    color: #120904;
  }
  .modal-content-body {
    padding: 14px;
    color: var(--text-main);
  }
  .report-box h4 {
    color: var(--gold);
    margin-bottom: 8px;
    font-family: 'Cinzel', serif;
  }
  .report-box p {
    font-size: 12px;
    margin-bottom: 6px;
    color: #e2d7c5;
  }
</style>
