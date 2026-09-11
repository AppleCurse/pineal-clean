<!-- Analog ibreli gösterge: pirinç bezel + sedef kadran + canlı ibre.
     value=null ise veri yok demektir: ibre park konumuna çekilir.
     İki dilli: label (EN gravür) + tr (TR alt satır). -->
<script lang="ts">
  export let label: string;
  export let tr: string = '';
  export let value: number | null; // 0..100, null = veri yok
  export let sub: string; // dijital alt okuma (örn. "12ms", "100%", "—")
  export let tone: 'red' | 'gold' | 'green' = 'gold';

  const CX = 60;
  const CY = 58;
  const ARC = 240; // derece süpürme
  const START = -120; // 0 değeri (sol park)

  $: angle = value === null ? START : START + (Math.max(0, Math.min(100, value)) / 100) * ARC;

  // 12 küçük + 4 büyük taksimat
  const ticks = Array.from({ length: 13 }, (_, i) => {
    const a = ((START + (i / 12) * ARC) * Math.PI) / 180;
    const major = i % 3 === 0;
    const r1 = major ? 33 : 36;
    const r2 = 40;
    return {
      x1: CX + r1 * Math.sin(a),
      y1: CY - r1 * Math.cos(a),
      x2: CX + r2 * Math.sin(a),
      y2: CY - r2 * Math.cos(a),
      major,
    };
  });

  const numerals = [0, 50, 100].map((v) => {
    const a = ((START + (v / 100) * ARC) * Math.PI) / 180;
    return { v, x: CX + 26 * Math.sin(a), y: CY - 26 * Math.cos(a) + 2 };
  });

  const screws = [45, 135, 225, 315].map((deg) => {
    const a = (deg * Math.PI) / 180;
    return { x: CX + 52 * Math.sin(a), y: CY - 52 * Math.cos(a) };
  });
</script>

<div class="agauge">
  <svg viewBox="0 0 120 116" class="agauge-svg" role="img" aria-label={label}>
    <defs>
      <radialGradient id="brass-{label}" cx="35%" cy="30%" r="80%">
        <stop offset="0%" stop-color="#f3e5ab" />
        <stop offset="35%" stop-color="#b8860b" />
        <stop offset="70%" stop-color="#6b4e2a" />
        <stop offset="100%" stop-color="#2a1a08" />
      </radialGradient>
      <radialGradient id="pearl-{label}" cx="40%" cy="35%" r="75%">
        <stop offset="0%" stop-color="#fdfbf4" />
        <stop offset="55%" stop-color="#e9e2d2" />
        <stop offset="85%" stop-color="#c9bfa8" />
        <stop offset="100%" stop-color="#a99e86" />
      </radialGradient>
    </defs>

    <!-- bezel -->
    <circle cx={CX} cy={CY} r="56" fill="url(#brass-{label})" stroke="#160d04" stroke-width="2" />
    <circle cx={CX} cy={CY} r="47" fill="#0d0703" />
    <!-- sedef kadran -->
    <circle cx={CX} cy={CY} r="44" fill="url(#pearl-{label})" stroke="#5a3d1c" stroke-width="1" />

    {#each ticks as tk}
      <line
        x1={tk.x1} y1={tk.y1} x2={tk.x2} y2={tk.y2}
        stroke={tk.major ? '#2a1a08' : '#5a4a30'}
        stroke-width={tk.major ? 2 : 1}
      />
    {/each}
    {#each numerals as n}
      <text x={n.x} y={n.y} text-anchor="middle" font-size="7" font-weight="700" fill="#3a2a12" font-family="Cinzel, serif">{n.v}</text>
    {/each}

    <!-- ibre -->
    <g class="needle" style="transform: rotate({angle}deg);">
      <line x1={CX} y1={CY + 8} x2={CX} y2={CY - 34} class="needle-line {tone}" />
    </g>
    <circle cx={CX} cy={CY} r="6" fill="url(#brass-{label})" stroke="#160d04" stroke-width="1.5" />
    <circle cx={CX} cy={CY} r="2" fill="#120904" />

    <!-- cam parlaması -->
    <ellipse cx="44" cy="38" rx="20" ry="10" fill="#ffffff" opacity="0.18" transform="rotate(-25 44 38)" />

    <!-- bezel vidaları -->
    {#each screws as s}
      <circle cx={s.x} cy={s.y} r="3" fill="#2a1a08" stroke="#d4af37" stroke-width="0.8" />
      <line x1={s.x - 1.8} y1={s.y} x2={s.x + 1.8} y2={s.y} stroke="#d4af37" stroke-width="0.8" />
    {/each}
  </svg>

  <div class="agauge-plate">{label}</div>
  {#if tr}<div class="agauge-tr">{tr}</div>{/if}
  <div class="agauge-sub {value === null ? 'nodata' : ''}">{sub}</div>
</div>

<style>
  .agauge {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
    min-width: 140px;
  }
  .agauge-svg {
    width: 132px;
    height: auto;
    filter: drop-shadow(0 4px 10px rgba(0, 0, 0, 0.8));
  }
  .needle {
    transform-origin: 60px 58px;
    transition: transform 0.9s cubic-bezier(0.3, 1.35, 0.5, 1);
  }
  .needle-line {
    stroke-width: 2.5;
    stroke-linecap: round;
  }
  .needle-line.red { stroke: #dc2626; filter: drop-shadow(0 0 3px #ef4444); }
  .needle-line.gold { stroke: #8a5a12; filter: drop-shadow(0 0 2px #d4af37); }
  .needle-line.green { stroke: #047857; filter: drop-shadow(0 0 3px #10b981); }
  .agauge-plate {
    font-family: 'Cinzel', serif;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1px;
    color: #120b04;
    background: linear-gradient(180deg, #d4af37 0%, #8a6332 100%);
    border: 1px solid #ffe89e;
    border-radius: 3px;
    padding: 2px 10px;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.6), inset 0 1px 1px rgba(255, 255, 255, 0.6);
    white-space: nowrap;
  }
  .agauge-tr {
    font-family: 'JetBrains Mono', monospace;
    font-size: 7px;
    font-weight: 700;
    letter-spacing: 0.6px;
    color: var(--text-muted);
  }
  .agauge-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 11px;
    font-weight: 700;
    color: #7dfcd0;
    background: #050302;
    border: 1px solid #3d2b17;
    border-radius: 3px;
    padding: 1px 10px;
    min-width: 84px;
    text-align: center;
    text-shadow: 0 0 6px rgba(16, 185, 129, 0.7);
    box-shadow: inset 0 0 8px #000;
  }
  .agauge-sub.nodata {
    color: #6b5a3e;
    text-shadow: none;
  }
</style>
