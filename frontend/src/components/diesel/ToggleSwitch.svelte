<!-- Pirinç levhalı bıçak şalter: POWER · ARM · RECORD · SIGINT
     İki dilli: label (EN) + tr (TR alt satır). -->
<script lang="ts">
  export let label: string;
  export let tr: string = '';
  export let engaged: boolean;
  export let led: 'green' | 'red' | 'off' = 'green';
  export let onToggle: () => void;
</script>

<div class="tswitch">
  <div class="jewel {led === 'green' && engaged ? 'j-green' : led === 'red' && engaged ? 'j-red' : 'j-off'}"></div>
  <button
    class="plate {engaged ? 'on' : 'off'}"
    aria-label={label}
    aria-pressed={engaged}
    on:click={onToggle}
  >
    <span class="screw tl"></span>
    <span class="screw tr"></span>
    <span class="slot"></span>
    <span class="bat"><span class="bat-tip"></span></span>
    <span class="screw bl"></span>
    <span class="screw br"></span>
  </button>
  <span class="tlabel">{label}</span>
  {#if tr}<span class="tlabel-tr">{tr}</span>{/if}
</div>

<style>
  .tswitch {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 3px;
  }
  .jewel {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    border: 1px solid #160d04;
  }
  .j-green { background: #10b981; box-shadow: 0 0 8px #10b981, 0 0 2px #fff; }
  .j-red { background: #ef4444; box-shadow: 0 0 8px #ef4444; animation: blink 1s infinite alternate; }
  .j-off { background: #1b120a; box-shadow: inset 0 1px 2px #000; }
  @keyframes blink { from { opacity: 0.5; } to { opacity: 1; } }

  .plate {
    position: relative;
    width: 34px;
    height: 56px;
    border-radius: 5px;
    cursor: pointer;
    background: linear-gradient(145deg, #c9a24a 0%, #8a6332 45%, #5a3d1c 100%);
    border: 1px solid #ffe89e;
    box-shadow: 0 3px 7px rgba(0, 0, 0, 0.7), inset 0 1px 1px rgba(255, 255, 255, 0.55);
    padding: 0;
  }
  .slot {
    position: absolute;
    left: 50%;
    top: 8px;
    bottom: 8px;
    width: 8px;
    transform: translateX(-50%);
    background: #0d0703;
    border-radius: 4px;
    box-shadow: inset 0 2px 4px #000, 0 1px 0 rgba(255, 255, 255, 0.25);
  }
  .bat {
    position: absolute;
    left: 50%;
    top: 50%;
    width: 10px;
    height: 34px;
    transform-origin: 50% 50%;
    transition: transform 0.14s ease;
  }
  .plate.on .bat { transform: translate(-50%, -50%) rotate(0deg); }
  .plate.off .bat { transform: translate(-50%, -50%) rotate(180deg); }
  .bat::before {
    content: '';
    position: absolute;
    left: 3px;
    top: 12px;
    width: 4px;
    height: 18px;
    background: linear-gradient(90deg, #6b6b6b, #d8d8d8, #6b6b6b);
    border-radius: 2px;
  }
  .bat-tip {
    position: absolute;
    left: 0;
    top: 0;
    width: 10px;
    height: 15px;
    border-radius: 5px 5px 3px 3px;
    background: radial-gradient(circle at 35% 30%, #4a4a4a, #0a0a0a 75%);
    border: 1px solid #000;
    box-shadow: 0 2px 3px rgba(0, 0, 0, 0.7);
  }
  .screw {
    position: absolute;
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 30%, #8a8a8a, #2a2a2a);
    box-shadow: inset 0 1px 1px #000;
  }
  .tl { top: 3px; left: 3px; } .tr { top: 3px; right: 3px; }
  .bl { bottom: 3px; left: 3px; } .br { bottom: 3px; right: 3px; }
  .tlabel {
    font-family: 'Cinzel', serif;
    font-size: 7px;
    font-weight: 800;
    letter-spacing: 0.6px;
    color: var(--text-dim);
  }
  .tlabel-tr {
    font-family: 'JetBrains Mono', monospace;
    font-size: 6px;
    font-weight: 700;
    letter-spacing: 0.4px;
    color: var(--text-muted);
  }
</style>
