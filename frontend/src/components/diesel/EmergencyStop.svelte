<!-- EMERGENCY STOP: kırmızı flip kapak + mantar buton.
     Basınca onPress çalışır (işleyen görevi iptal eder). -->
<script lang="ts">
  export let armed: boolean; // hatta işleyen görev var mı
  export let onPress: () => void;

  let slammed = false;

  function press() {
    slammed = true;
    setTimeout(() => (slammed = false), 220);
    onPress();
  }
</script>

<div class="estop-mod">
  <div class="flip-cover"><span class="cover-glass"></span></div>
  <button
    class="mushroom {slammed ? 'slammed' : ''}"
    aria-label="Emergency stop"
    on:click={press}
    title={armed ? 'İşleyen görevi DURDUR' : 'Hat boşta'}
  >
    <span class="cap">STOP</span>
  </button>
  <div class="ring-text">EMERGENCY · STOP</div>
  <div class="ring-text-tr">ACİL DURDURMA</div>
  {#if armed}<div class="armed-dot"></div>{/if}
</div>

<style>
  .estop-mod {
    position: relative;
    display: flex;
    flex-direction: column;
    align-items: center;
    padding-top: 26px;
  }
  .flip-cover {
    position: absolute;
    top: 0;
    width: 56px;
    height: 30px;
    border-radius: 8px 8px 0 0;
    background: linear-gradient(180deg, rgba(220, 38, 38, 0.55), rgba(127, 29, 29, 0.55));
    border: 2px solid #7f1d1d;
    border-bottom: none;
    box-shadow: inset 0 2px 4px rgba(255, 255, 255, 0.25);
  }
  .cover-glass {
    position: absolute;
    left: 6px;
    top: 4px;
    width: 10px;
    height: 20px;
    border-radius: 5px;
    background: rgba(255, 255, 255, 0.28);
  }
  .mushroom {
    width: 58px;
    height: 44px;
    border-radius: 12px;
    cursor: pointer;
    background: radial-gradient(circle at 50% 25%, #f87171 0%, #dc2626 45%, #7f1d1d 100%);
    border: 3px solid #450a0a;
    box-shadow: 0 5px 0 #450a0a, 0 8px 12px rgba(0, 0, 0, 0.7), inset 0 2px 3px rgba(255, 255, 255, 0.5);
    transition: transform 0.07s, box-shadow 0.07s;
    padding: 0;
  }
  .mushroom.slammed {
    transform: translateY(4px);
    box-shadow: 0 1px 0 #450a0a, 0 3px 6px rgba(0, 0, 0, 0.7);
  }
  .cap {
    font-family: 'Cinzel', serif;
    font-size: 10px;
    font-weight: 900;
    color: #fff;
    letter-spacing: 1px;
    text-shadow: 0 1px 2px #000;
  }
  .ring-text {
    margin-top: 5px;
    font-family: 'Cinzel', serif;
    font-size: 7px;
    font-weight: 800;
    letter-spacing: 0.8px;
    color: var(--gold);
  }
  .ring-text-tr {
    font-family: 'JetBrains Mono', monospace;
    font-size: 6px;
    font-weight: 700;
    letter-spacing: 0.5px;
    color: var(--text-muted);
  }
  .armed-dot {
    position: absolute;
    right: 6px;
    top: 30px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #ef4444;
    box-shadow: 0 0 8px #ef4444;
    animation: blink 0.7s infinite alternate;
  }
  @keyframes blink { from { opacity: 0.4; } to { opacity: 1; } }
</style>
