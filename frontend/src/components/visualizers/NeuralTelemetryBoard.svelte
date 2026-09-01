<script lang="ts">
  import { onMount } from 'svelte';
  
  // Backend'den gelen canlı telemetri objesi (App.svelte'den beslenecek)
  export let telemetry: any = null;
  
  // Görseldeki sıvı akış hızını kontrol eden iç değişkenler
  let flowSpeed = 2; 
  let activeNodes = new Set<string>();

  // Düzmece/Gerçek veriyi ayrıştırma mantığı
  $: {
    if (telemetry) {
      const state = telemetry.status || 'idle';
      const active = telemetry.active_tasks?.length > 0;
      
      activeNodes.clear();
      if (active) {
        activeNodes.add('gateway');
        activeNodes.add('router');
        
        // Örnek: Eğer memory read varsa
        if (JSON.stringify(telemetry).includes('memory')) {
          activeNodes.add('memory');
        }
        
        if (telemetry.router === 'unified' || JSON.stringify(telemetry).includes('llm')) {
          activeNodes.add('llm');
        }
      }
      activeNodes = activeNodes; // Svelte reaktivitesini tetikle
      flowSpeed = active ? 0.5 : 3;
    }
  }

  // Parçacık efekti için (arka planda kayan tozlar)
  let particles = Array(20).fill(0).map(() => ({
    x: Math.random() * 100,
    y: Math.random() * 100,
    size: Math.random() * 2 + 1,
    speed: Math.random() * 1 + 0.5,
    delay: Math.random() * -10
  }));
</script>

<div class="telemetry-board">
  <!-- Arka plan ortam parçacıkları -->
  {#each particles as p}
    <div class="ambient-particle" 
         style="left: {p.x}%; top: {p.y}%; width: {p.size}px; height: {p.size}px; 
                animation-duration: {10 / p.speed}s; animation-delay: {p.delay}s;">
    </div>
  {/each}

  <div class="board-header">
    <div class="title-container">
      <div class="status-dot" class:pulsing={activeNodes.size > 0}></div>
      <h2 class="board-title">PINEAL NEURAL FLUID PIPELINE</h2>
    </div>
    <div class="metrics">
      <div class="metric-box">
        <span class="metric-lbl">SYSTEM STATUS</span>
        <span class="metric-val" style="color: {activeNodes.size > 0 ? '#00ffa3' : '#a0aec0'}">
          {activeNodes.size > 0 ? 'PROCESSING' : 'IDLE'}
        </span>
      </div>
      <div class="metric-box">
        <span class="metric-lbl">ACTIVE TUBES</span>
        <span class="metric-val">{activeNodes.size}</span>
      </div>
    </div>
  </div>

  <div class="pipeline-canvas">
    <!-- SVG Boru Hatları (Şeffaf Su Hortumu Metaphoru) -->
    <svg width="100%" height="100%" preserveAspectRatio="none" viewBox="0 0 1000 400" class="pipes-svg">
      <defs>
        <!-- Akışkan filtre efekti (Neon Glow) -->
        <filter id="neon-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="4" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
        
        <!-- Boş Hortum Doku (Cam hissi) -->
        <linearGradient id="glass-pipe" x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stop-color="rgba(255,255,255,0.1)" />
          <stop offset="50%" stop-color="rgba(255,255,255,0.02)" />
          <stop offset="100%" stop-color="rgba(255,255,255,0.1)" />
        </linearGradient>

        <linearGradient id="fluid-gradient" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#00ffa3" />
          <stop offset="50%" stop-color="#00b8ff" />
          <stop offset="100%" stop-color="#7000ff" />
        </linearGradient>
      </defs>

      <!-- Dış Cam Borular (Zemin) -->
      <path d="M 100,200 L 300,200" class="glass-path" />
      <path d="M 300,200 L 500,100 L 700,100" class="glass-path" />
      <path d="M 300,200 L 500,300 L 700,300" class="glass-path" />
      <path d="M 700,100 L 900,200" class="glass-path" />
      <path d="M 700,300 L 900,200" class="glass-path" />

      <!-- İçerideki Akışkan Sıvı (Fluid) -->
      <!-- Gateway -> Router -->
      <path d="M 100,200 L 300,200" 
            class="fluid-path" filter="url(#neon-glow)" 
            style="animation-duration: {flowSpeed}s; opacity: {activeNodes.has('gateway') ? 1 : 0.1};" />
            
      <!-- Router -> Memory/OSINT (Üst Kol) -->
      <path d="M 300,200 L 500,100 L 700,100" 
            class="fluid-path" filter="url(#neon-glow)" 
            style="animation-duration: {flowSpeed}s; opacity: {activeNodes.has('memory') ? 1 : 0.05};" />
            
      <!-- Router -> LLM Engine (Alt Kol) -->
      <path d="M 300,200 L 500,300 L 700,300" 
            class="fluid-path alt-fluid" filter="url(#neon-glow)" 
            style="animation-duration: {flowSpeed}s; opacity: {activeNodes.has('llm') ? 1 : 0.05};" />
            
      <!-- Merge -> Output -->
      <path d="M 700,100 L 900,200" 
            class="fluid-path" filter="url(#neon-glow)" 
            style="animation-duration: {flowSpeed}s; opacity: {activeNodes.has('memory') ? 1 : 0.05};" />
      <path d="M 700,300 L 900,200" 
            class="fluid-path alt-fluid" filter="url(#neon-glow)" 
            style="animation-duration: {flowSpeed}s; opacity: {activeNodes.has('llm') ? 1 : 0.05};" />
    </svg>

    <!-- Node UI'ları (Cam Kartlar) -->
    <!-- Gateway -->
    <div class="cyber-node" style="left: 10%; top: 50%;">
      <div class="node-icon" class:active={activeNodes.has('gateway')}>⛩️</div>
      <div class="node-label">API GATEWAY</div>
    </div>

    <!-- Unified Router -->
    <div class="cyber-node" style="left: 30%; top: 50%;">
      <div class="node-icon" class:active={activeNodes.has('router')}>🚦</div>
      <div class="node-label">UNIFIED ROUTER</div>
      <div class="node-pulse" class:pulsing={activeNodes.has('router')}></div>
    </div>

    <!-- OSINT / Memory -->
    <div class="cyber-node" style="left: 60%; top: 25%;">
      <div class="node-icon" class:active={activeNodes.has('memory')}>🧠</div>
      <div class="node-label">OSINT & MEMORY</div>
      {#if activeNodes.has('memory')}
        <div class="mini-hud">READING VAULT...</div>
      {/if}
    </div>

    <!-- LLM Engine -->
    <div class="cyber-node" style="left: 60%; top: 75%;">
      <div class="node-icon" class:active={activeNodes.has('llm')}>🔥</div>
      <div class="node-label">LLM ENGINE</div>
      {#if activeNodes.has('llm')}
        <div class="mini-hud stream-text">SYNTHESIZING...</div>
      {/if}
    </div>

    <!-- Output -->
    <div class="cyber-node" style="left: 90%; top: 50%;">
      <div class="node-icon" class:active={activeNodes.has('gateway')}>✅</div>
      <div class="node-label">CLIENT RESPONSE</div>
    </div>
  </div>
</div>

<style>
  .telemetry-board {
    position: relative;
    width: 100%;
    height: 450px;
    background: radial-gradient(circle at center, #0a0f1d 0%, #03050a 100%);
    border: 1px solid rgba(0, 255, 163, 0.1);
    border-radius: 16px;
    overflow: hidden;
    font-family: 'Courier New', Courier, monospace;
    box-shadow: inset 0 0 50px rgba(0,0,0,0.8), 0 10px 30px rgba(0,0,0,0.5);
  }

  .ambient-particle {
    position: absolute;
    background: #00b8ff;
    border-radius: 50%;
    opacity: 0.3;
    animation: floatUp linear infinite;
    pointer-events: none;
  }

  .board-header {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    padding: 15px 25px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    z-index: 10;
    background: linear-gradient(180deg, rgba(3,5,10,0.8) 0%, rgba(3,5,10,0) 100%);
  }

  .title-container {
    display: flex;
    align-items: center;
    gap: 12px;
  }

  .status-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #4a5568;
    box-shadow: 0 0 0 rgba(0,0,0,0);
  }

  .status-dot.pulsing {
    background: #00ffa3;
    animation: redAlert 1.5s infinite;
  }

  .board-title {
    margin: 0;
    color: #fff;
    font-size: 14px;
    letter-spacing: 4px;
    font-weight: 600;
    text-shadow: 0 0 10px rgba(255,255,255,0.3);
  }

  .metrics {
    display: flex;
    gap: 20px;
  }

  .metric-box {
    display: flex;
    flex-direction: column;
    align-items: flex-end;
  }

  .metric-lbl {
    font-size: 10px;
    color: #4a5568;
    letter-spacing: 1px;
  }

  .metric-val {
    font-size: 14px;
    font-weight: bold;
    color: #fff;
  }

  .pipeline-canvas {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
  }

  .pipes-svg {
    position: absolute;
    top: 0;
    left: 0;
    z-index: 1;
    pointer-events: none;
  }

  .glass-path {
    fill: none;
    stroke: url(#glass-pipe);
    stroke-width: 12;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  /* Ana akışkan (Neon yeşil/mavi) */
  .fluid-path {
    fill: none;
    stroke: url(#fluid-gradient);
    stroke-width: 6;
    stroke-linecap: round;
    stroke-linejoin: round;
    stroke-dasharray: 20 40;
    animation: flowData linear infinite;
    transition: opacity 0.4s ease;
  }

  /* İkinci akışkan (Neon mor/kırmızı - LLM ateşi) */
  .alt-fluid {
    stroke: #ff0055;
    stroke-dasharray: 15 30;
  }

  .cyber-node {
    position: absolute;
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    z-index: 5;
  }

  .node-icon {
    width: 50px;
    height: 50px;
    background: rgba(10, 15, 30, 0.8);
    border: 1px solid #2d3748;
    border-radius: 12px;
    display: flex;
    justify-content: center;
    align-items: center;
    font-size: 20px;
    backdrop-filter: blur(4px);
    transition: all 0.3s ease;
    box-shadow: 0 4px 6px rgba(0,0,0,0.5);
    position: relative;
  }

  .node-icon.active {
    border-color: #00ffa3;
    box-shadow: 0 0 20px rgba(0, 255, 163, 0.4), inset 0 0 10px rgba(0, 255, 163, 0.2);
    transform: scale(1.1);
  }

  .node-label {
    margin-top: 10px;
    color: #a0aec0;
    font-size: 11px;
    font-weight: 600;
    letter-spacing: 1px;
    text-shadow: 0 2px 4px rgba(0,0,0,0.8);
  }

  .node-pulse {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 50px;
    height: 50px;
    transform: translate(-50%, -50%);
    border-radius: 12px;
    border: 2px solid #00b8ff;
    opacity: 0;
    pointer-events: none;
  }

  .node-pulse.pulsing {
    animation: pulseRing 1.5s cubic-bezier(0.215, 0.61, 0.355, 1) infinite;
  }

  .mini-hud {
    position: absolute;
    top: -25px;
    background: rgba(0, 255, 163, 0.1);
    border: 1px solid #00ffa3;
    color: #00ffa3;
    padding: 2px 6px;
    font-size: 9px;
    border-radius: 4px;
    white-space: nowrap;
  }

  .stream-text {
    color: #ff0055;
    border-color: #ff0055;
    background: rgba(255, 0, 85, 0.1);
  }

  @keyframes flowData {
    to { stroke-dashoffset: -120; }
  }

  @keyframes pulseRing {
    0% { transform: translate(-50%, -50%) scale(1); opacity: 0.8; }
    100% { transform: translate(-50%, -50%) scale(1.8); opacity: 0; }
  }

  @keyframes redAlert {
    0% { box-shadow: 0 0 0 0 rgba(0, 255, 163, 0.7); }
    70% { box-shadow: 0 0 0 10px rgba(0, 255, 163, 0); }
    100% { box-shadow: 0 0 0 0 rgba(0, 255, 163, 0); }
  }

  @keyframes floatUp {
    0% { transform: translateY(0); opacity: 0; }
    10% { opacity: 0.5; }
    90% { opacity: 0.5; }
    100% { transform: translateY(-100px); opacity: 0; }
  }
</style>
