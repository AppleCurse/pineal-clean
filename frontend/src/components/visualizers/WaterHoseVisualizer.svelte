<script lang="ts">
  import { onMount } from 'svelte';
  
  // Suyun akış hızını, rengini ve içindeki "parçacıkları" (veriyi) temsil eden reaktif veriler
  export let isActive = false;
  export let currentAgent = "Idle";
  export let pressure = 0; // İşlem yoğunluğu / token hızı

  interface Particle {
    id: string;
    type: string; // 'osint', 'llm', 'scrape'
    progress: number;
    speed: number;
  }

  let particles: Particle[] = [];
  let flowInterval: ReturnType<typeof setInterval> | null = null;

  // Parçacık (Veri) animasyonu
  function spawnParticle(type: string) {
    const p: Particle = {
      id: Math.random().toString(36).substr(2, 9),
      type: type,
      progress: 0,
      speed: 0.5 + (Math.random() * 0.5) // basınca göre değişebilir
    };
    particles = [...particles, p];
    
    // İşiniz biten parçacığı sil
    setTimeout(() => {
      particles = particles.filter(x => x.id !== p.id);
    }, 2000);
  }

  onMount(() => {
    flowInterval = setInterval(() => {
      if (isActive && pressure > 0) {
        spawnParticle('data');
      }
    }, 300);
    
    return () => {
      if (flowInterval) clearInterval(flowInterval);
    };
  });
</script>

<div class="hose-container">
  <!-- Şeffaf Borunun Dış Camı -->
  <div class="glass-tube" class:active={isActive}>
    <div class="tube-glare"></div>
    
    <!-- İçerideki Su/Veri Akışı -->
    <div class="water-flow" style="opacity: {isActive ? 0.8 : 0.1}; width: {pressure}%">
      
      <!-- Suyun içindeki veri parçacıkları (Agent'ın bulduğu kanıtlar) -->
      {#each particles as particle (particle.id)}
        <div class="data-particle {particle.type}" 
             style="left: {particle.progress}%; animation: flowAnim {2 / particle.speed}s linear infinite">
        </div>
      {/each}
      
      <!-- Akıntı dalgaları (Görsel efekt) -->
      <div class="waves"></div>
    </div>
  </div>
  
  <!-- Borunun Altındaki Telemetri Oku -->
  <div class="telemetry-hud">
    <div class="hud-item">
      <span class="label">AGENT</span>
      <span class="value" class:highlight={isActive}>{currentAgent}</span>
    </div>
    <div class="hud-item">
      <span class="label">THROUGHPUT</span>
      <span class="value">{Math.floor(pressure * 10)} tk/s</span>
    </div>
  </div>
</div>

<style>
  .hose-container {
    width: 100%;
    padding: 20px 0;
    position: relative;
    font-family: monospace;
  }

  /* Şeffaf cam boru tasarımı */
  .glass-tube {
    height: 40px;
    width: 100%;
    border-radius: 20px;
    background: rgba(10, 15, 30, 0.6);
    border: 2px solid rgba(100, 150, 255, 0.2);
    box-shadow: inset 0 0 15px rgba(0,0,0,0.8), 
                0 0 10px rgba(100, 150, 255, 0.05);
    position: relative;
    overflow: hidden;
    transition: border-color 0.3s ease;
  }

  .glass-tube.active {
    border-color: rgba(100, 200, 255, 0.6);
    box-shadow: inset 0 0 15px rgba(0,0,0,0.8), 
                0 0 20px rgba(100, 200, 255, 0.2);
  }

  /* Cam parlaması efekti */
  .tube-glare {
    position: absolute;
    top: 2px;
    left: 5%;
    right: 5%;
    height: 10px;
    background: linear-gradient(to bottom, rgba(255,255,255,0.15) 0%, rgba(255,255,255,0) 100%);
    border-radius: 10px;
    z-index: 10;
    pointer-events: none;
  }

  /* Suyun kendisi (CSS Gradient ile akan bir sıvı hissiyatı) */
  .water-flow {
    position: absolute;
    top: 0;
    left: 0;
    height: 100%;
    background: linear-gradient(90deg, 
      rgba(0, 150, 255, 0.1) 0%, 
      rgba(0, 200, 255, 0.5) 50%, 
      rgba(0, 100, 255, 0.8) 100%);
    transition: width 0.5s cubic-bezier(0.175, 0.885, 0.32, 1.275), opacity 0.3s;
    border-radius: 20px;
  }

  /* Akıntı hissini veren çizgiler/dalgalar */
  .waves {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background-image: linear-gradient(
      -45deg, 
      rgba(255,255,255,0.1) 25%, 
      transparent 25%, 
      transparent 50%, 
      rgba(255,255,255,0.1) 50%, 
      rgba(255,255,255,0.1) 75%, 
      transparent 75%, 
      transparent
    );
    background-size: 30px 30px;
    animation: moveStripes 1s linear infinite;
    opacity: 0.3;
  }

  /* Suyun içinde sürüklenen veri parçacıkları */
  .data-particle {
    position: absolute;
    top: 50%;
    transform: translateY(-50%);
    width: 6px;
    height: 6px;
    background: white;
    border-radius: 50%;
    box-shadow: 0 0 8px white, 0 0 15px #00ffff;
    z-index: 5;
  }

  .telemetry-hud {
    display: flex;
    justify-content: space-between;
    margin-top: 10px;
    padding: 0 15px;
    color: rgba(255,255,255,0.5);
    font-size: 12px;
  }

  .hud-item {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .value {
    color: rgba(255,255,255,0.8);
    font-weight: bold;
  }
  
  .value.highlight {
    color: #00ffff;
    text-shadow: 0 0 5px rgba(0, 255, 255, 0.5);
  }

  @keyframes moveStripes {
    0% { background-position: 0 0; }
    100% { background-position: 30px 0; }
  }
  
  @keyframes flowAnim {
    0% { left: 0%; opacity: 0; }
    10% { opacity: 1; }
    90% { opacity: 1; }
    100% { left: 100%; opacity: 0; }
  }
</style>
