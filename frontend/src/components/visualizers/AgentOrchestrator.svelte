<script lang="ts">
  import WaterHoseVisualizer from './WaterHoseVisualizer.svelte';
  
  // Örnek Telemetri State'i (Gerçek backend'den websocket ile beslenecek)
  let agents = [
    { name: "Router", status: "idle", pressure: 0 },
    { name: "LLM (DeepSeek)", status: "idle", pressure: 0 },
    { name: "Crawl4AI", status: "idle", pressure: 0 }
  ];

  let isRunning = false;

  function simulateAgentWork() {
    isRunning = true;
    
    // 1. Router karar veriyor
    agents[0].status = "active";
    agents[0].pressure = 30;
    
    setTimeout(() => {
      agents[0].status = "idle";
      agents[0].pressure = 0;
      
      // 2. Crawl4AI web sayfasını çekiyor (Yüksek basınç/veri akışı)
      agents[2].status = "active";
      agents[2].pressure = 90;
      
      setTimeout(() => {
        agents[2].status = "idle";
        agents[2].pressure = 0;
        
        // 3. LLM veriyi işliyor ve sonuç üretiyor
        agents[1].status = "active";
        agents[1].pressure = 60;
        
        setTimeout(() => {
          agents[1].status = "idle";
          agents[1].pressure = 0;
          isRunning = false;
        }, 3000);
      }, 2500);
    }, 1000);
  }
</script>

<div class="orchestrator">
  <div class="header">
    <h3>PINEAL TELEMETRY</h3>
    <button on:click={simulateAgentWork} disabled={isRunning} class="trigger-btn">
      {isRunning ? 'Processing...' : 'Simulate Request'}
    </button>
  </div>

  <div class="pipelines">
    {#each agents as agent}
      <div class="pipeline-row">
        <WaterHoseVisualizer 
          currentAgent={agent.name}
          isActive={agent.status === "active"}
          pressure={agent.pressure}
        />
      </div>
    {/each}
  </div>
</div>

<style>
  .orchestrator {
    background: #050a15;
    border: 1px solid rgba(100, 150, 255, 0.2);
    border-radius: 12px;
    padding: 24px;
    color: white;
    font-family: 'Inter', sans-serif;
  }

  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 30px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    padding-bottom: 15px;
  }

  h3 {
    margin: 0;
    color: #00ffff;
    letter-spacing: 2px;
    font-size: 14px;
  }

  .trigger-btn {
    background: rgba(0, 150, 255, 0.2);
    border: 1px solid #00ffff;
    color: #00ffff;
    padding: 6px 12px;
    border-radius: 4px;
    cursor: pointer;
    font-family: monospace;
    transition: all 0.2s;
  }

  .trigger-btn:hover:not(:disabled) {
    background: rgba(0, 150, 255, 0.4);
    box-shadow: 0 0 10px rgba(0, 255, 255, 0.3);
  }

  .trigger-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    border-color: gray;
    color: gray;
  }

  .pipeline-row {
    margin-bottom: 15px;
  }
</style>
