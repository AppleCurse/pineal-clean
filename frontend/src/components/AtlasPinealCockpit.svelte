<script lang="ts">
  import { onMount } from 'svelte';
  import {
    apiFetch, clientId, isAuthFailure, logs, taskStatus, isProcessing,
    apiToken
  } from '../store';
  import { playClick, playHalt, playRunning } from '../lib/consoleAudio';

  // Tek dokunulmaz ana şasi görseli (Kayıpsız 16:9 Master Referans)
  import cockpitSkin from '../assets/cockpit-v10-reference.png';
  import livingPinealDisk from '../assets/living_pineal_disk.png';

  // --- STATE ---
  let targetUrl = '';
  let inputMessage = '';
  let isSending = false;
  let activePillarModal: string | null = null;
  let activeTab = 'ASPASIA';

  // --- YAŞAYAN PİNEAL GÖZ (ORGANİK VE YAVAŞ HAREKET) ---
  let eyeX = 0;
  let eyeY = 0;
  let targetEyeX = 0;
  let targetEyeY = 0;
  let eyeScale = 1.0;
  let animFrameId: number;

  function handleMouseMove(e: MouseEvent) {
    const width = typeof window !== 'undefined' ? window.innerWidth : 1920;
    const height = typeof window !== 'undefined' ? window.innerHeight : 1080;
    const normX = (e.clientX - width / 2) / (width / 2);
    const normY = (e.clientY - height / 2) / (height / 2);
    // Yavaş ve zarif bakış hedefi (maksimum ±4.5px kayma)
    targetEyeX = Math.max(-4.5, Math.min(4.5, normX * 4.5));
    targetEyeY = Math.max(-3.5, Math.min(3.5, normY * 3.5));
  }

  onMount(() => {
    let startTime = performance.now();

    function animate(time: number) {
      const elapsed = (time - startTime) * 0.001;

      // Organik, yavaş, hipnotik mikro salınım (2 farklı frekansta sinüs)
      const organicDriftX = Math.sin(elapsed * 0.45) * 2.2 + Math.sin(elapsed * 0.18) * 1.0;
      const organicDriftY = Math.cos(elapsed * 0.35) * 1.8 + Math.cos(elapsed * 0.12) * 0.8;

      // Analiz sırasında hafif odak nefesi
      const processingFlutter = $isProcessing ? Math.sin(elapsed * 3.5) * 0.6 : 0;

      const desiredX = targetEyeX + organicDriftX + processingFlutter;
      const desiredY = targetEyeY + organicDriftY;

      // Yumuşak sönümleme (lerp 0.04) ile yavaş ve kaliteli akış
      eyeX += (desiredX - eyeX) * 0.04;
      eyeY += (desiredY - eyeY) * 0.04;

      // Yavaş göz bebeği nefes alışı (1.008 ile 1.024 arası)
      eyeScale = 1.016 + Math.sin(elapsed * 0.5) * 0.012;

      animFrameId = requestAnimationFrame(animate);
    }

    animFrameId = requestAnimationFrame(animate);

    return () => {
      if (animFrameId) cancelAnimationFrame(animFrameId);
    };
  });

  // 7 Sütun Adli Rapor Listesi
  const pillarsList = [
    { id: 'follower',  label: 'FOLLOWER',  tr: 'TAKİPÇİ' },
    { id: 'timing',    label: 'TIMING',    tr: 'ZAMAN' },
    { id: 'depth',     label: 'DEPTH',     tr: 'DERİNLİK' },
    { id: 'visual',    label: 'VISUAL',    tr: 'GÖRSEL' },
    { id: 'shadow',    label: 'SHADOW',    tr: 'GÖLGE' },
    { id: 'osint',     label: 'OSINT',     tr: 'OSINT' },
    { id: 'resonance', label: 'RESONANCE', tr: 'REZONANS' },
  ];

  // Adli Telemetri Durumları
  $: followerAudit = $taskStatus?.follower_audit || null;
  $: timingForensics = $taskStatus?.timing_forensics || null;
  $: depthReport = $taskStatus?.depth_report || null;
  $: visualEvidence = $taskStatus?.visual_evidence || null;
  $: shadowProfile = $taskStatus?.shadow_profile || null;
  $: osintFootprint = $taskStatus?.osint_footprint || null;
  $: resonanceCalc = $taskStatus?.runs?.resonance_calc?.output_summary || null;

  function nowTime() {
    return new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }

  function addLog(msg: string, level = 'INFO') {
    logs.update(l => [...l, { ts: nowTime(), level, msg }].slice(-80));
  }

  // --- ACTIONS ---
  async function launchAnalysis() {
    const url = targetUrl.trim();
    if (!url || $isProcessing) return;
    isProcessing.set(true);
    playRunning();
    addLog(`ANALİZ BAŞLATILDI: ${url}`, 'INFO');

    try {
      const res = await apiFetch('/api/initiate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: $clientId,
          url,
          scraper_type: 'cross',
        })
      });
      if (!res.ok) throw new Error(isAuthFailure(res) ? 'PINEAL_TOKEN yetki hatası' : `HTTP ${res.status}`);
      const data = await res.json();
      if (data.task_id) {
        taskStatus.update(s => ({ ...(s || {}), task_id: data.task_id, status: 'processing' }));
        addLog(`GÖREV DEVREDE: ${data.task_id}`, 'INFO');
      }
    } catch (e: any) {
      isProcessing.set(false);
      playHalt();
      addLog(`HATA: ${e?.message || e}`, 'ERROR');
    }
  }

  async function sendAspasiaMessage() {
    const text = inputMessage.trim();
    if (!text || isSending) return;
    inputMessage = '';
    isSending = true;
    playClick(440, 30);
    addLog(`SİZ: ${text}`, 'INFO');

    try {
      const res = await apiFetch('/api/aspasia/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          client_id: $clientId || 'default',
          user_message: text
        })
      });

      if (res.ok) {
        const data = await res.json();
        const reply = data.message || data.reply || data.response || 'Emir alındı.';
        addLog(`ASPASIA: ${reply}`, 'INFO');
        playClick(520, 40);
      } else {
        throw new Error(`HTTP ${res.status}`);
      }
    } catch (err: any) {
      addLog(`ASPASIA HATA: ${err.message}`, 'ERROR');
    } finally {
      isSending = false;
    }
  }

  function togglePillar(pillarId: string) {
    playClick(320, 40);
    activePillarModal = activePillarModal === pillarId ? null : pillarId;
    addLog(`7 SÜTUN: ${pillarId.toUpperCase()} raporu açıldı`, 'INFO');
  }
</script>

<svelte:window on:mousemove={handleMouseMove} />

<div class="cockpit-viewport-frame" role="region" aria-label="Atlas Epifiz Pineal Observatory">
  <!-- 1. TEK VE DOKUNULMAZ ANA ŞASİ GÖRSELİ (Kayıpsız 16:9) -->
  <img class="master-cockpit-bg" src={cockpitSkin} alt="Atlas Pineal Observatory Cockpit" />

  <!-- 1.5. YAŞAYAN PİNEAL GÖZ (Pirinç yuva içine gömülü, yavaş, organik ve hipnotik hareket) -->
  <div class="living-eye-viewport" aria-label="Atlas Pineal Eye">
    <img
      class="living-eye-disk"
      src={livingPinealDisk}
      alt="Atlas Pineal Eye"
      style="transform: translate(calc(-50% + {eyeX.toFixed(2)}px), calc(-50% + {eyeY.toFixed(2)}px)) scale({eyeScale.toFixed(3)});"
    />
  </div>

  <!-- 2. SADECE İŞLEVSEL ŞEFFAF HİTBOX'LAR (TIKLAMA ALANLARI) -->

  <!-- Orta Güverte 5 Tab Butonları -->
  <div class="tabs-hitbox-group">
    {#each ['ASPASIA', 'VISION', 'OSINT', 'FRICTION', 'VERIFY'] as tab}
      <button
        class="tab-touch-seal {activeTab === tab ? 'tab-active' : ''}"
        on:click={() => { activeTab = tab; playClick(300, 30); }}
        title="{tab} Ekranı"
      ></button>
    {/each}
  </div>

  <!-- URL Yazma Kutusu (Kaset ekranına tam oturan şeffaf giriş alanı) -->
  <div class="url-cassette-chamber">
    <input
      type="text"
      class="url-cassette-input"
      bind:value={targetUrl}
      placeholder=""
      disabled={$isProcessing}
      on:keydown={(e) => { if (e.key === 'Enter') launchAnalysis(); }}
      title="Hedef Profil / URL Kaseti"
    />
  </div>

  <!-- Mekanik CAPTURE Butonu (Yeşil başlatma butonu üzerine şeffaf alan) -->
  <button
    class="antique-touch-btn capture-mechanical-spot {$isProcessing ? 'capture-running' : ''}"
    on:click={launchAnalysis}
    disabled={$isProcessing || !targetUrl.trim()}
    title="ANALİZİ BAŞLAT (CAPTURE)"
  ></button>

  <!-- Aspasia Sohbet/Komut Satırı (Sol alttaki '> Komut veya sorgu gir...' üzerine şeffaf alan) -->
  <div class="aspasia-command-slot">
    <input
      type="text"
      class="aspasia-command-input"
      bind:value={inputMessage}
      placeholder=""
      disabled={isSending}
      on:keydown={(e) => { if (e.key === 'Enter') sendAspasiaMessage(); }}
      title="Aspasia Komut Satırı"
    />
  </div>

  <!-- Aspasia GÖNDER Butonu ('GÖNDER' butonu üzerine şeffaf alan) -->
  <button
    class="antique-touch-btn aspasia-send-spot"
    on:click={sendAspasiaMessage}
    disabled={isSending || !inputMessage.trim()}
    title="GÖNDER"
  ></button>

  <!-- 7 Sütun Dokunmatik Butonları (FOLLOWER, TIMING, DEPTH, VISUAL, SHADOW, OSINT, RESONANCE) -->
  <div class="seven-pillars-hitbox-rack">
    {#each pillarsList as p}
      <button
        class="pillar-touch-seal {activePillarModal === p.id ? 'pillar-active' : ''}"
        on:click={() => togglePillar(p.id)}
        title="{p.label} ({p.tr}) Adli Raporu"
      ></button>
    {/each}
  </div>

  <!-- 3. ADLİ RAPOR KARTI (Sadece bir sütuna tıklandığında açılır) -->
  {#if activePillarModal}
    <div class="forensic-backdrop" role="presentation" on:click={() => activePillarModal = null} on:keydown={(e) => { if (e.key === 'Escape') activePillarModal = null; }}>
      <div class="forensic-card" role="dialog" aria-modal="true" tabindex="-1" on:click|stopPropagation on:keydown|stopPropagation>
        <div class="forensic-card-header">
          <span class="card-title">ADLİ SÜTUN: {activePillarModal.toUpperCase()}</span>
          <button class="close-x" on:click={() => activePillarModal = null}>✕</button>
        </div>
        <div class="forensic-card-body">
          {#if activePillarModal === 'follower' && followerAudit}
            <div class="report-block">
              <h4>Takipçi & Kitle Bütünlüğü</h4>
              <p>Hüküm: <strong>{followerAudit.verdict || 'BİLİNMİYOR'}</strong> ({followerAudit.verdict_code || 'nominal'})</p>
              <p>Takipçi Sayısı: {followerAudit.follower_count ?? 0} · Takip: {followerAudit.following_count ?? '—'}</p>
              <p>Etkileşim Katsayısı: {followerAudit.engagement_rate ?? '—'}</p>
              <p>Veri Tamlığı: %{((followerAudit.data_completeness ?? 0) * 100).toFixed(0)}</p>
            </div>
          {:else if activePillarModal === 'timing' && timingForensics}
            <div class="report-block">
              <h4>Zaman & Sirkadiyen Forensik</h4>
              <p>Gece Payı: %{((timingForensics.night_share ?? 0) * 100).toFixed(0)}</p>
              <p>Tepe Saati: {timingForensics.peak_hour ?? '—'}</p>
              <p>Medyan Kayma: {timingForensics.median_drift_hours ?? '—'} saat</p>
            </div>
          {:else if activePillarModal === 'depth' && depthReport}
            <div class="report-block">
              <h4>Derinlik & Alıntı Kalkanı</h4>
              <p>Gerçeklik İndeksi: %{((depthReport.reality_index || 0) * 100).toFixed(0)}</p>
              <p>Öz Çıkarım: {depthReport.essence_one_liner || 'Veri mevcut değil'}</p>
            </div>
          {:else if activePillarModal === 'visual' && visualEvidence}
            <div class="report-block">
              <h4>Görsel & Estetik Forensik</h4>
              <p>Estetik Stil: {visualEvidence.aesthetic_style || '—'}</p>
              <p>Özet: {visualEvidence.visual_evidence_summary || 'Veri mevcut değil'}</p>
            </div>
          {:else if activePillarModal === 'shadow' && shadowProfile}
            <div class="report-block">
              <h4>Gölge Profili (Karanlık Üçlü)</h4>
              <p>Narsisizm Skoru: {shadowProfile.dark_profile?.narcissism ?? 0}</p>
              <p>Tespit Edilen Strateji: {shadowProfile.strategy || '—'}</p>
            </div>
          {:else if activePillarModal === 'osint' && osintFootprint}
            <div class="report-block">
              <h4>OSINT Dijital Ayak İzi</h4>
              <p>İlişkili Platformlar: {(osintFootprint.associated_platforms || []).join(', ') || '—'}</p>
            </div>
          {:else if activePillarModal === 'resonance' && resonanceCalc}
            <div class="report-block">
              <h4>Rezonans & Uyum</h4>
              <p>Uyum Skoru: %{((resonanceCalc.compatibility_score ?? 0) * 100).toFixed(0)}</p>
              <p>Yaklaşım Protokolü: {resonanceCalc.recommended_approach || '—'}</p>
            </div>
          {:else}
            <div class="report-block">
              <h4>{activePillarModal.toUpperCase()} Sinyali</h4>
              <p>Bu sütun için henüz aktif analiz verisi işlenmedi. Hedef kasetine profil girip CAPTURE tuşuna basın.</p>
            </div>
          {/if}
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  /* =========================================================
     TAM EKRAN SİNEMATİK KOKPİT (TEK ANA ŞASİ)
     ========================================================= */
  .cockpit-viewport-frame {
    position: relative;
    width: 100vw;
    height: 100vh;
    max-width: calc(100vh * 16 / 9);
    max-height: calc(100vw * 9 / 16);
    aspect-ratio: 16 / 9;
    margin: auto;
    overflow: hidden;
    background: #000;
    user-select: none;
    font-family: 'JetBrains Mono', monospace;
  }

  /* Tek Dokunulmaz Orijinal Ana Şasi */
  .master-cockpit-bg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    object-fit: fill;
    pointer-events: none;
    z-index: 1;
  }

  /* =========================================================
     YAŞAYAN PİNEAL GÖZ (MERKEZİ PİRİNÇ YUVA)
     ========================================================= */
  .living-eye-viewport {
    position: absolute;
    left: 49.76%;
    top: 45.70%;
    width: 12.2%;
    aspect-ratio: 1;
    transform: translate(-50%, -50%);
    border-radius: 50%;
    overflow: hidden;
    pointer-events: none;
    z-index: 2;
    box-shadow:
      inset 0 0 10px rgba(0, 0, 0, 0.85),
      inset 0 2px 6px rgba(0, 0, 0, 0.95);
  }

  .living-eye-disk {
    position: absolute;
    left: 50%;
    top: 50%;
    width: 108%;
    height: 108%;
    border-radius: 50%;
    object-fit: cover;
    pointer-events: none;
    will-change: transform;
    filter: contrast(1.02) brightness(1.01);
  }

  /* =========================================================
     ŞEFFAF HİTBOX'LAR (SIFIR ÇİRKİN KENARLIK, HAFİF AMBER GLOW)
     ========================================================= */
  .antique-touch-btn {
    position: absolute;
    background: transparent;
    border: none;
    outline: none;
    cursor: pointer;
    z-index: 10;
    transition: box-shadow 0.25s ease, background 0.25s ease;
  }

  .antique-touch-btn:hover {
    box-shadow: 0 0 16px rgba(230, 140, 30, 0.45), inset 0 0 8px rgba(245, 158, 11, 0.25);
    background: rgba(230, 130, 20, 0.08);
  }

  /* 5 Orta Güverte Sekmesi */
  .tabs-hitbox-group {
    position: absolute;
    left: 28.5%;
    top: 67.0%;
    width: 38.0%;
    height: 4.5%;
    display: flex;
    gap: 2%;
    z-index: 10;
  }

  .tab-touch-seal {
    flex: 1;
    background: transparent;
    border: none;
    outline: none;
    cursor: pointer;
    border-radius: 2px;
    transition: all 0.2s ease;
  }

  .tab-touch-seal:hover, .tab-touch-seal.tab-active {
    background: rgba(230, 140, 30, 0.18);
    box-shadow: 0 0 10px rgba(230, 140, 30, 0.4);
  }

  /* URL Yazma Kutusu */
  .url-cassette-chamber {
    position: absolute;
    left: 39.10%;
    top: 70.20%;
    width: 21.30%;
    height: 8.20%;
    z-index: 12;
    display: flex;
    align-items: center;
  }

  .url-cassette-input {
    width: 100%;
    height: 100%;
    background: transparent;
    border: none;
    outline: none;
    padding: 0 10px;
    color: #fde68a;
    font-size: clamp(9px, 0.95vw, 13px);
    font-family: 'JetBrains Mono', monospace;
    caret-color: #f59e0b;
    text-shadow: 0 0 8px rgba(245, 158, 11, 0.6);
  }

  .url-cassette-input:focus, .url-cassette-input:not(:placeholder-shown) {
    background: #040907;
    border-radius: 3px;
    box-shadow: inset 0 0 10px rgba(0, 0, 0, 0.95);
  }

  /* CAPTURE Butonu */
  .capture-mechanical-spot {
    left: 60.60%;
    top: 70.80%;
    width: 4.80%;
    height: 7.20%;
    border-radius: 50%;
  }

  .capture-mechanical-spot:hover {
    box-shadow: 0 0 18px rgba(230, 140, 30, 0.65), inset 0 0 10px rgba(245, 158, 11, 0.35);
  }

  .capture-mechanical-spot.capture-running {
    box-shadow: 0 0 18px rgba(239, 68, 68, 0.7);
    animation: amberPulse 0.8s infinite alternate;
  }

  /* Aspasia Sohbet/Komut Satırı */
  .aspasia-command-slot {
    position: absolute;
    left: 5.44%;
    top: 93.30%;
    width: 39.17%;
    height: 4.20%;
    z-index: 12;
    display: flex;
    align-items: center;
  }

  .aspasia-command-input {
    width: 100%;
    height: 100%;
    background: transparent;
    border: none;
    outline: none;
    padding-left: 22px;
    color: #fef3c7;
    font-size: clamp(8px, 0.88vw, 12px);
    font-family: 'JetBrains Mono', monospace;
    caret-color: #f59e0b;
    text-shadow: 0 0 6px rgba(245, 158, 11, 0.5);
  }

  .aspasia-command-input:focus, .aspasia-command-input:not(:placeholder-shown) {
    background: #030805;
    border-radius: 3px;
    box-shadow: inset 0 0 8px rgba(0, 0, 0, 0.95);
  }

  /* Aspasia GÖNDER Butonu */
  .aspasia-send-spot {
    left: 44.92%;
    top: 93.30%;
    width: 6.58%;
    height: 4.20%;
    border-radius: 3px;
  }

  /* 7 Sütun Dokunmatik Alanları */
  .seven-pillars-hitbox-rack {
    position: absolute;
    left: 53.95%;
    top: 86.72%;
    width: 42.05%;
    height: 9.88%;
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 1.2%;
    z-index: 10;
  }

  .pillar-touch-seal {
    background: transparent;
    border: none;
    outline: none;
    cursor: pointer;
    border-radius: 4px;
    transition: all 0.2s ease;
  }

  .pillar-touch-seal:hover, .pillar-touch-seal.pillar-active {
    background: rgba(230, 140, 30, 0.18);
    box-shadow: 0 0 16px rgba(230, 140, 30, 0.5), inset 0 0 8px rgba(245, 158, 11, 0.3);
  }

  /* =========================================================
     ADLİ RAPOR KARTI (SADECE TIKLANDIĞINDA AÇILIR)
     ========================================================= */
  .forensic-backdrop {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.85);
    backdrop-filter: blur(5px);
    z-index: 99999;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .forensic-card {
    background: #0e0a06;
    border: 2px solid #8e6538;
    border-radius: 6px;
    box-shadow: 0 0 50px rgba(0, 0, 0, 0.95), inset 0 0 30px rgba(0, 0, 0, 0.8);
    width: min(88vw, 640px);
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    overflow: hidden;
    color: #f5edd8;
  }

  .forensic-card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 16px;
    background: linear-gradient(180deg, #2a1a0c 0%, #160e06 100%);
    border-bottom: 1px solid #785226;
  }

  .card-title {
    font-family: 'Cinzel', serif;
    font-weight: 800;
    font-size: 13px;
    color: #d4af37;
    letter-spacing: 0.12em;
  }

  .close-x {
    background: transparent;
    border: none;
    color: #d4af37;
    font-size: 16px;
    cursor: pointer;
  }

  .forensic-card-body {
    padding: 16px;
    overflow-y: auto;
  }

  .report-block h4 {
    color: #d4af37;
    margin: 0 0 8px 0;
    font-size: 14px;
    border-bottom: 1px solid #5a3d1c;
    padding-bottom: 4px;
  }

  .report-block p {
    margin: 6px 0;
    font-size: 12px;
    color: #fde68a;
    line-height: 1.5;
  }

  @keyframes amberPulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.6; transform: scale(0.98); }
  }
</style>
