let ctx: AudioContext | null = null;

// PROP düğmesi: konsol sesleri ana şalteri (varsayılan açık).
let soundEnabled = true;
export function setSoundEnabled(on: boolean) {
  soundEnabled = on;
}
export function isSoundEnabled(): boolean {
  return soundEnabled;
}

function getCtx() {
  if (typeof window === 'undefined') return null;
  if (!soundEnabled) return null;
  if (!ctx) {
    const AudioCtx = window.AudioContext || (window as any).webkitAudioContext;
    if (AudioCtx) ctx = new AudioCtx();
  }
  if (ctx && ctx.state === 'suspended') {
    ctx.resume().catch(() => {});
  }
  return ctx;
}

/** Kısa mekanik tık */
export function playClick(freq = 180, ms = 40) {
  const c = getCtx();
  if (!c) return;
  try {
    const o = c.createOscillator();
    const g = c.createGain();
    o.type = 'square';
    o.frequency.value = freq;
    g.gain.value = 0.08;
    o.connect(g);
    g.connect(c.destination);
    o.start();
    g.gain.exponentialRampToValueAtTime(0.001, c.currentTime + ms / 1000);
    o.stop(c.currentTime + ms / 1000);
  } catch (_) {}
}

/** RUNNING — kısa yükselen ton */
export function playRunning() {
  playClick(320, 60);
  setTimeout(() => playClick(420, 50), 50);
}

/** HALT — alçak uyarı */
export function playHalt() {
  playClick(90, 120);
  setTimeout(() => playClick(70, 150), 80);
}

/** Kol / şalter */
export function playToggle(on: boolean) {
  playClick(on ? 220 : 140, 45);
}
