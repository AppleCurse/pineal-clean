<script lang="ts">
  import { onMount, onDestroy } from 'svelte';

  // PINEAL GÖZÜ — kokpitin tam ortasındaki canlı göz.
  // Bebek fareyi/imleci takip eder, periyodik olarak göz kırpar,
  // tarama kipinde iris büzülür ve tarama hüzmesi süpürür.
  export let size: number = 232;
  export let scanning: boolean = false;
  export let customImage: string | null = null;
  export let interactive: boolean = true;

  let root: HTMLDivElement | null = null;
  let irisGroup: HTMLDivElement | null = null;
  let pupilEl: HTMLDivElement | null = null;
  let glintEl: HTMLDivElement | null = null;
  let photoEl: HTMLImageElement | null = null;

  let tx = 0;
  let ty = 0;
  let px = 0;
  let py = 0;
  let blinking = false;
  let raf = 0;
  let blinkTimer: ReturnType<typeof setTimeout> | null = null;
  let alive = false;
  let startT = 0;

  function handleMove(cx: number, cy: number) {
    if (!interactive || !root) return;
    const r = root.getBoundingClientRect();
    const dx = cx - (r.left + r.width / 2);
    const dy = cy - (r.top + r.height / 2);
    const dist = Math.hypot(dx, dy);
    const max = size * 0.085;
    if (dist < 1) {
      tx = 0;
      ty = 0;
      return;
    }
    const mag = Math.min(dist / 320, 1) * max;
    tx = (dx / dist) * mag;
    ty = (dy / dist) * mag;
  }

  function onMouse(e: MouseEvent) {
    handleMove(e.clientX, e.clientY);
  }

  function onTouch(e: TouchEvent) {
    if (e.touches.length > 0) handleMove(e.touches[0].clientX, e.touches[0].clientY);
  }

  function scheduleBlink() {
    if (!alive) return;
    blinkTimer = setTimeout(() => {
      if (!alive) return;
      blinking = true;
      setTimeout(() => {
        blinking = false;
      }, 120);
      scheduleBlink();
    }, 2400 + Math.random() * 3800);
  }

  export function blink() {
    blinking = true;
    setTimeout(() => {
      blinking = false;
    }, 140);
  }

  function loop(t: number) {
    if (!alive) return;
    px += (tx - px) * 0.14;
    py += (ty - py) * 0.14;
    const breath = Math.sin((t - startT) / 1500);
    const scanPulse = scanning ? Math.sin((t - startT) / 130) * 0.5 + 0.5 : 0;
    if (irisGroup) {
      irisGroup.style.transform = `translate(${px.toFixed(2)}px, ${py.toFixed(2)}px) scale(${(1 + breath * 0.008).toFixed(4)})`;
    }
    if (pupilEl) {
      const d = scanning ? 0.7 + scanPulse * 0.28 : 1 + breath * 0.05;
      pupilEl.style.transform = `scale(${d.toFixed(3)})`;
    }
    if (glintEl) {
      glintEl.style.transform = `translate(${(px * 0.35).toFixed(2)}px, ${(py * 0.35).toFixed(2)}px)`;
    }
    if (photoEl && customImage) {
      photoEl.style.transform = `translate(${(-px * 0.4).toFixed(2)}px, ${(-py * 0.4).toFixed(2)}px) scale(1.14)`;
    }
    raf = requestAnimationFrame(loop);
  }

  onMount(() => {
    alive = true;
    startT = performance.now();
    window.addEventListener('mousemove', onMouse, { passive: true });
    window.addEventListener('touchmove', onTouch, { passive: true });
    scheduleBlink();
    raf = requestAnimationFrame(loop);
  });

  onDestroy(() => {
    alive = false;
    cancelAnimationFrame(raf);
    if (blinkTimer) clearTimeout(blinkTimer);
    window.removeEventListener('mousemove', onMouse);
    window.removeEventListener('touchmove', onTouch);
  });
</script>

<div class="pineal-eye {scanning ? 'is-scanning' : ''}" bind:this={root} style="--eye:{size}px;">
  <div class="halo"></div>
  <div class="bezel">
    <span class="screw s-n"></span>
    <span class="screw s-e"></span>
    <span class="screw s-s"></span>
    <span class="screw s-w"></span>
    <div class="socket">
      {#if customImage}
        <img class="photo" src={customImage} alt="Senin gözün" bind:this={photoEl} draggable="false" />
        <div class="photo-shade"></div>
      {:else}
        <div class="sclera">
          <svg class="veins" viewBox="0 0 100 100" aria-hidden="true">
            <path d="M2,30 Q25,32 38,44" />
            <path d="M98,62 Q75,60 62,52" />
            <path d="M15,78 Q30,66 40,60" />
            <path d="M85,20 Q72,30 64,38" />
            <path d="M50,3 Q48,20 44,34" />
            <path d="M50,97 Q52,80 56,66" />
            <path d="M6,55 Q22,54 34,50" />
            <path d="M94,42 Q78,44 68,48" />
          </svg>
        </div>
        <div class="iris-group" bind:this={irisGroup}>
          <div class="iris">
            <div class="fibers fibers-a"></div>
            <div class="fibers fibers-b"></div>
            <div class="collarette"></div>
            <div class="pupil-wrap">
              <div class="pupil" bind:this={pupilEl}></div>
            </div>
          </div>
        </div>
      {/if}
      <div class="glint" bind:this={glintEl}></div>
      <div class="glint glint-sm"></div>
      <div class="lid lid-top" class:closed={blinking}></div>
      <div class="lid lid-bottom" class:closed={blinking}></div>
      {#if scanning}
        <div class="scan-beam"></div>
      {/if}
      <div class="inner-shadow"></div>
    </div>
  </div>
</div>

<style>
  .pineal-eye {
    position: relative;
    width: var(--eye);
    height: var(--eye);
    flex-shrink: 0;
  }

  .halo {
    position: absolute;
    inset: -24%;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(212, 175, 55, 0.4) 0%, rgba(212, 175, 55, 0.12) 45%, transparent 70%);
    filter: blur(12px);
    animation: haloPulse 4s ease-in-out infinite;
    pointer-events: none;
  }

  .is-scanning .halo {
    background: radial-gradient(circle, rgba(56, 239, 125, 0.45) 0%, rgba(56, 239, 125, 0.14) 45%, transparent 70%);
    animation-duration: 1.1s;
  }

  @keyframes haloPulse {
    0%, 100% { opacity: 0.75; transform: scale(1); }
    50% { opacity: 1; transform: scale(1.06); }
  }

  /* İşlenmiş pirinç çerçeve */
  .bezel {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: conic-gradient(from 210deg, #5a3a16, #d8b45a, #8a6332, #fef0be, #8a6332, #5a3a16, #e8c766, #5a3a16);
    padding: calc(var(--eye) * 0.045);
    box-shadow:
      0 0 0 2px #120803,
      0 0 0 3px #ffecb3,
      0 14px 44px rgba(0, 0, 0, 0.9),
      0 0 55px rgba(212, 175, 55, 0.35),
      inset 0 2px 4px rgba(255, 255, 255, 0.7),
      inset 0 -3px 6px rgba(0, 0, 0, 0.7);
  }

  .is-scanning .bezel {
    box-shadow:
      0 0 0 2px #120803,
      0 0 0 3px #baffdb,
      0 14px 44px rgba(0, 0, 0, 0.9),
      0 0 70px rgba(56, 239, 125, 0.6),
      inset 0 2px 4px rgba(255, 255, 255, 0.7),
      inset 0 -3px 6px rgba(0, 0, 0, 0.7);
  }

  .screw {
    position: absolute;
    width: 7px;
    height: 7px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 30%, #a67f38 0%, #3a220e 70%, #120803 100%);
    border: 1px solid #0d0602;
    box-shadow: inset 0 1px 1px rgba(255, 255, 255, 0.5);
    z-index: 3;
  }
  .s-n { top: 1.6%; left: calc(50% - 3.5px); }
  .s-s { bottom: 1.6%; left: calc(50% - 3.5px); }
  .s-e { right: 1.6%; top: calc(50% - 3.5px); }
  .s-w { left: 1.6%; top: calc(50% - 3.5px); }

  .socket {
    position: relative;
    width: 100%;
    height: 100%;
    border-radius: 50%;
    overflow: hidden;
    background: #050302;
    box-shadow:
      inset 0 0 calc(var(--eye) * 0.14) rgba(0, 0, 0, 0.95),
      0 0 0 2px #120904;
  }

  /* Göz akı */
  .sclera {
    position: absolute;
    inset: 0;
    background: radial-gradient(circle at 50% 42%, #fffdf6 0%, #f3e9d2 45%, #d9c39a 72%, #8a6a45 100%);
  }

  .veins {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
    opacity: 0.55;
    filter: blur(0.4px);
  }
  .veins path {
    fill: none;
    stroke: #a93226;
    stroke-width: 0.7;
    opacity: 0.7;
  }

  /* İris grubu (imleci takip eder) */
  .iris-group {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    will-change: transform;
    z-index: 2;
  }

  .iris {
    position: relative;
    width: 62%;
    height: 62%;
    border-radius: 50%;
    overflow: hidden;
    background:
      radial-gradient(circle at 50% 40%, rgba(255, 244, 214, 0.85) 0%, rgba(255, 244, 214, 0) 26%),
      radial-gradient(circle, #1c0d03 0 15%, #5a2f0c 24%, #a86f1d 36%, #e9c25c 48%, #7a4d12 60%, #2a1505 74%, #0d0502 88%, #000 100%);
    box-shadow:
      0 0 0 3px #0a0502,
      0 0 22px rgba(0, 0, 0, 0.9),
      inset 0 0 18px rgba(0, 0, 0, 0.75);
  }

  .fibers {
    position: absolute;
    inset: 0;
    border-radius: 50%;
  }
  .fibers-a {
    background: repeating-conic-gradient(
      from 0deg,
      rgba(255, 236, 180, 0.3) 0deg 1.6deg,
      rgba(255, 236, 180, 0) 1.6deg 5deg,
      rgba(40, 20, 4, 0.42) 5deg 6.4deg,
      rgba(40, 20, 4, 0) 6.4deg 11deg
    );
    -webkit-mask: radial-gradient(circle, transparent 0 17%, #000 26%, #000 62%, transparent 73%);
    mask: radial-gradient(circle, transparent 0 17%, #000 26%, #000 62%, transparent 73%);
  }
  .fibers-b {
    background: repeating-conic-gradient(
      from 7deg,
      rgba(255, 214, 120, 0.22) 0deg 2deg,
      rgba(255, 214, 120, 0) 2deg 7deg,
      rgba(20, 10, 2, 0.35) 7deg 9deg,
      rgba(20, 10, 2, 0) 9deg 15deg
    );
    -webkit-mask: radial-gradient(circle, transparent 0 30%, #000 40%, #000 58%, transparent 70%);
    mask: radial-gradient(circle, transparent 0 30%, #000 40%, #000 58%, transparent 70%);
  }

  .collarette {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: radial-gradient(circle, transparent 0 29%, rgba(30, 15, 3, 0.6) 33%, rgba(212, 175, 55, 0.4) 38%, transparent 45%);
  }

  .pupil-wrap {
    position: absolute;
    inset: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .pupil {
    width: 36%;
    height: 36%;
    border-radius: 50%;
    background: radial-gradient(circle at 38% 35%, #2c2c2c 0%, #000 46%, #000 100%);
    box-shadow: 0 0 12px #000, inset 0 0 8px #000;
    will-change: transform;
  }

  /* Kullanıcının yüklediği göz fotoğrafı */
  .photo {
    position: absolute;
    inset: -10%;
    width: 120%;
    height: 120%;
    object-fit: cover;
    will-change: transform;
    z-index: 1;
  }
  .photo-shade {
    position: absolute;
    inset: 0;
    background: radial-gradient(circle, transparent 52%, rgba(5, 2, 0, 0.6) 100%);
    z-index: 2;
    pointer-events: none;
  }

  /* Parlaklık yansımaları */
  .glint {
    position: absolute;
    left: 29%;
    top: 23%;
    width: 20%;
    height: 13%;
    border-radius: 50%;
    background: radial-gradient(ellipse, rgba(255, 255, 255, 0.95) 0%, rgba(255, 255, 255, 0.25) 55%, transparent 70%);
    mix-blend-mode: screen;
    will-change: transform;
    z-index: 4;
    pointer-events: none;
  }
  .glint-sm {
    left: 61%;
    top: 63%;
    width: 9%;
    height: 6.5%;
    opacity: 0.55;
  }

  /* Göz kapakları (panjur) */
  .lid {
    position: absolute;
    left: 0;
    right: 0;
    height: 52%;
    z-index: 6;
    transition: transform 0.12s ease-in;
    pointer-events: none;
  }
  .lid-top {
    top: 0;
    transform: scaleY(0);
    transform-origin: top center;
    background: linear-gradient(180deg, #3a2410 0%, #170d05 100%);
    border-bottom: 3px solid #0a0502;
    box-shadow: 0 3px 8px rgba(212, 175, 55, 0.35);
  }
  .lid-bottom {
    bottom: 0;
    transform: scaleY(0);
    transform-origin: bottom center;
    background: linear-gradient(0deg, #3a2410 0%, #170d05 100%);
    border-top: 3px solid #0a0502;
    box-shadow: 0 -3px 8px rgba(212, 175, 55, 0.35);
  }
  .lid.closed {
    transform: scaleY(1);
  }

  /* Tarama hüzmesi */
  .scan-beam {
    position: absolute;
    left: -5%;
    right: -5%;
    top: -25%;
    height: 22%;
    background: linear-gradient(180deg, transparent, rgba(56, 239, 125, 0.5) 42%, rgba(225, 255, 236, 0.9) 50%, rgba(56, 239, 125, 0.5) 58%, transparent);
    filter: blur(0.5px);
    animation: beamSweep 1.15s linear infinite;
    z-index: 7;
    pointer-events: none;
  }
  @keyframes beamSweep {
    from { top: -25%; }
    to { top: 112%; }
  }

  .inner-shadow {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    box-shadow: inset 0 0 calc(var(--eye) * 0.1) rgba(0, 0, 0, 0.85);
    z-index: 8;
    pointer-events: none;
  }

  @media (prefers-reduced-motion: reduce) {
    .halo, .scan-beam { animation: none; }
  }
</style>
