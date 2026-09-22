<script lang="ts">
  import { onMount, onDestroy } from 'svelte';
  import { isProcessing } from '../store';

  export let size: number = 520;
  export let active: boolean = false;
  export let intensity: number = 0.85;

  let canvasEl: HTMLCanvasElement | null = null;
  let ctx: CanvasRenderingContext2D | null = null;
  let rafId = 0;
  let alive = false;
  let startTime = 0;

  interface Node {
    x: number;
    y: number;
    baseAngle: number;
    radius: number;
    pulseOffset: number;
  }

  let nodes: Node[] = [];
  let innerNodes: Node[] = [];

  function generateNodes() {
    nodes = [];
    innerNodes = [];
    const outerCount = 12;
    const innerCount = 8;
    for (let i = 0; i < outerCount; i++) {
      nodes.push({
        x: 0,
        y: 0,
        baseAngle: (i / outerCount) * Math.PI * 2,
        radius: 0.42,
        pulseOffset: Math.random() * Math.PI * 2,
      });
    }
    for (let i = 0; i < innerCount; i++) {
      innerNodes.push({
        x: 0,
        y: 0,
        baseAngle: (i / innerCount) * Math.PI * 2 + 0.2,
        radius: 0.24,
        pulseOffset: Math.random() * Math.PI * 2,
      });
    }
  }

  function resizeCanvas() {
    if (!canvasEl) return;
    const dpr = window.devicePixelRatio || 1;
    canvasEl.width = size * dpr;
    canvasEl.height = size * dpr;
    canvasEl.style.width = `${size}px`;
    canvasEl.style.height = `${size}px`;
    if (ctx) {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }
  }

  function render(t: number) {
    if (!ctx || !canvasEl) return;
    const elapsed = (t - startTime) * 0.001;
    const center = size / 2;
    const processing = $isProcessing || active;
    const procSpeed = processing ? 1.8 : 0.6;
    const procPulse = processing ? 0.25 : 0.08;

    ctx.clearRect(0, 0, size, size);

    // Background subtle radial
    const bgGrad = ctx.createRadialGradient(center, center, 0, center, center, size * 0.5);
    bgGrad.addColorStop(0, `rgba(56, 239, 125, ${0.03 * intensity})`);
    bgGrad.addColorStop(0.5, `rgba(16, 185, 129, ${0.015 * intensity})`);
    bgGrad.addColorStop(1, 'transparent');
    ctx.fillStyle = bgGrad;
    ctx.beginPath();
    ctx.arc(center, center, size * 0.5, 0, Math.PI * 2);
    ctx.fill();

    // Outer resonance ring
    ctx.save();
    ctx.translate(center, center);
    ctx.rotate(elapsed * 0.15 * procSpeed);

    ctx.strokeStyle = `rgba(56, 239, 125, ${0.35 * intensity})`;
    ctx.lineWidth = 1.2;
    ctx.setLineDash([8, 12]);
    ctx.lineDashOffset = -elapsed * 20 * procSpeed;
    ctx.beginPath();
    ctx.arc(0, 0, size * 0.42, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Inner ring
    ctx.strokeStyle = `rgba(56, 239, 125, ${0.22 * intensity})`;
    ctx.lineWidth = 0.8;
    ctx.setLineDash([4, 8]);
    ctx.lineDashOffset = elapsed * 15 * procSpeed;
    ctx.beginPath();
    ctx.arc(0, 0, size * 0.24, 0, Math.PI * 2);
    ctx.stroke();
    ctx.setLineDash([]);

    // Outer nodes + connections (wireframe)
    const outerRadius = size * 0.42;
    const innerRadius = size * 0.24;

    // Update node positions with breathing
    nodes.forEach((node, i) => {
      const breath = Math.sin(elapsed * 0.5 + node.pulseOffset) * (size * 0.01 * procPulse);
      const angle = node.baseAngle + elapsed * 0.08 * procSpeed;
      const r = outerRadius + breath;
      node.x = Math.cos(angle) * r;
      node.y = Math.sin(angle) * r;
    });

    innerNodes.forEach((node) => {
      const breath = Math.sin(elapsed * 0.7 + node.pulseOffset) * (size * 0.008 * procPulse);
      const angle = node.baseAngle - elapsed * 0.12 * procSpeed;
      const r = innerRadius + breath;
      node.x = Math.cos(angle) * r;
      node.y = Math.sin(angle) * r;
    });

    // Draw wireframe - outer to inner + outer to outer
    ctx.strokeStyle = `rgba(56, 239, 125, ${0.18 * intensity})`;
    ctx.lineWidth = 0.6;

    // Outer ring connections (triangulated)
    for (let i = 0; i < nodes.length; i++) {
      const a = nodes[i];
      const b = nodes[(i + 1) % nodes.length];
      const c = nodes[(i + 2) % nodes.length];
      // a-b
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
      // a to inner nearest
      const innerIdx = i % innerNodes.length;
      const inner = innerNodes[innerIdx];
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(inner.x, inner.y);
      ctx.stroke();
      // a-c skip one (web)
      if (i % 2 === 0) {
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(c.x, c.y);
        ctx.stroke();
      }
    }

    // Inner connections
    for (let i = 0; i < innerNodes.length; i++) {
      const a = innerNodes[i];
      const b = innerNodes[(i + 1) % innerNodes.length];
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(b.x, b.y);
      ctx.stroke();
      // inner to center
      ctx.beginPath();
      ctx.moveTo(a.x, a.y);
      ctx.lineTo(0, 0);
      ctx.globalAlpha = 0.08 * intensity;
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    // Nodes - outer
    nodes.forEach((node) => {
      const pulse = Math.sin(elapsed * 2.2 + node.pulseOffset) * 0.5 + 0.5;
      ctx.fillStyle = `rgba(56, 239, 125, ${0.6 + pulse * 0.4})`;
      ctx.shadowColor = '#38ef7d';
      ctx.shadowBlur = 8 + pulse * 6;
      ctx.beginPath();
      ctx.arc(node.x, node.y, 2.5 + pulse * 1.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    });

    // Nodes - inner
    innerNodes.forEach((node) => {
      const pulse = Math.sin(elapsed * 1.8 + node.pulseOffset) * 0.5 + 0.5;
      ctx.fillStyle = `rgba(212, 175, 55, ${0.5 + pulse * 0.3})`;
      ctx.shadowColor = '#d4af37';
      ctx.shadowBlur = 6 + pulse * 4;
      ctx.beginPath();
      ctx.arc(node.x, node.y, 2 + pulse, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    });

    // Center core
    const corePulse = Math.sin(elapsed * 1.2) * 0.5 + 0.5;
    ctx.fillStyle = `rgba(56, 239, 125, ${0.15 + corePulse * 0.15})`;
    ctx.beginPath();
    ctx.arc(0, 0, 6 + corePulse * 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = `rgba(255, 255, 255, ${0.8 + corePulse * 0.2})`;
    ctx.beginPath();
    ctx.arc(0, 0, 1.5, 0, Math.PI * 2);
    ctx.fill();

    // Radial scan line when processing
    if (processing) {
      ctx.strokeStyle = `rgba(56, 239, 125, ${0.12 + corePulse * 0.08})`;
      ctx.lineWidth = 1;
      ctx.beginPath();
      ctx.moveTo(0, 0);
      const scanAngle = elapsed * 2.5;
      ctx.lineTo(Math.cos(scanAngle) * outerRadius, Math.sin(scanAngle) * outerRadius);
      ctx.stroke();
    }

    ctx.restore();
  }

  function loop(t: number) {
    if (!alive) return;
    render(t);
    rafId = requestAnimationFrame(loop);
  }

  onMount(() => {
    if (!canvasEl) return;
    ctx = canvasEl.getContext('2d', { alpha: true })!;
    generateNodes();
    resizeCanvas();
    startTime = performance.now();
    alive = true;
    rafId = requestAnimationFrame(loop);
  });

  onDestroy(() => {
    alive = false;
    if (rafId) cancelAnimationFrame(rafId);
  });

  $: if (canvasEl && size) {
    resizeCanvas();
  }
</script>

<div class="holographic-mesh-container" style="--size:{size}px;">
  <canvas bind:this={canvasEl} class="holographic-canvas gpu-accelerated" width={size} height={size}></canvas>
  <div class="mesh-vignette"></div>
</div>

<style>
  .holographic-mesh-container {
    position: relative;
    width: var(--size);
    height: var(--size);
    display: flex;
    align-items: center;
    justify-content: center;
    pointer-events: none;
    transform: translateZ(0);
    will-change: transform;
  }

  .holographic-canvas {
    position: absolute;
    inset: 0;
    width: 100% !important;
    height: 100% !important;
    display: block;
    transform: translateZ(0);
    will-change: transform;
    backface-visibility: hidden;
    filter: contrast(1.1) brightness(1.05);
  }

  .mesh-vignette {
    position: absolute;
    inset: 0;
    border-radius: 50%;
    background: radial-gradient(circle, transparent 60%, rgba(0, 0, 0, 0.4) 100%);
    pointer-events: none;
  }
</style>
