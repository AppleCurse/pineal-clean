<!-- Split-flap durum panosu: LATENCY · INTEGRITY · HAT.
     Tüm satırlar canlı ölçümdür; veri yoksa "—" basar.
     İki dilli: başlık + satır anahtarları + alt satır TR taşır. -->
<script lang="ts">
  export let title: string;
  export let titleTr: string = '';
  export let rows: Array<{ k: string; v: string; ktr?: string }>;
  export let foot: string;
  export let footTr: string = '';
  export let online: boolean;
</script>

<div class="splitflap">
  <div class="sf-title">{title}</div>
  {#if titleTr}<div class="sf-title-tr">{titleTr}</div>{/if}
  <div class="sf-rows">
    {#each rows as r}
      <div class="sf-row">
        <span class="sf-key">
          {r.k}
          {#if r.ktr}<span class="sf-key-tr">{r.ktr}</span>{/if}
        </span>
        <span class="sf-val">{r.v}</span>
      </div>
    {/each}
  </div>
  <div class="sf-foot">
    <span class="sf-foot-txt">{foot}{#if footTr}<span class="sf-foot-tr">{footTr}</span>{/if}</span>
    <span class="sf-led {online ? 'on' : 'off'}"></span>
  </div>
</div>

<style>
  .splitflap {
    background: linear-gradient(180deg, #241708 0%, #120b04 100%);
    border: 2px solid #8a6332;
    border-radius: 6px;
    padding: 8px 10px;
    min-width: 208px;
    box-shadow: inset 0 0 18px rgba(0, 0, 0, 0.85), 0 4px 10px rgba(0, 0, 0, 0.7);
  }
  .sf-title {
    font-family: 'Cinzel', serif;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1px;
    color: #120b04;
    background: linear-gradient(180deg, #d4af37, #8a6332);
    border: 1px solid #ffe89e;
    border-radius: 3px;
    text-align: center;
    padding: 2px 4px;
    margin-bottom: 2px;
  }
  .sf-title-tr {
    font-family: 'JetBrains Mono', monospace;
    font-size: 7px;
    font-weight: 700;
    letter-spacing: 0.6px;
    color: var(--text-muted);
    text-align: center;
    margin-bottom: 5px;
  }
  .sf-rows {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }
  .sf-row {
    display: flex;
    align-items: stretch;
    gap: 6px;
  }
  .sf-key {
    flex: 1;
    font-family: 'Cinzel', serif;
    font-size: 9px;
    font-weight: 700;
    color: var(--text-dim);
    display: flex;
    flex-direction: column;
    justify-content: center;
    letter-spacing: 0.5px;
    line-height: 1.2;
  }
  .sf-key-tr {
    font-family: 'JetBrains Mono', monospace;
    font-size: 7px;
    font-weight: 500;
    color: var(--text-muted);
    letter-spacing: 0.3px;
  }
  .sf-val {
    font-family: 'JetBrains Mono', monospace;
    font-size: 13px;
    font-weight: 800;
    color: #f5edd8;
    background: linear-gradient(180deg, #1c1c1c 0%, #1c1c1c 48%, #050505 52%, #101010 100%);
    border: 1px solid #3d3d3d;
    border-radius: 3px;
    padding: 2px 10px;
    min-width: 96px;
    text-align: right;
    letter-spacing: 1px;
    text-shadow: 0 0 5px rgba(245, 237, 216, 0.35);
    box-shadow: inset 0 0 6px #000;
    align-self: center;
  }
  .sf-foot {
    margin-top: 6px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 6px;
  }
  .sf-foot-txt {
    font-family: 'JetBrains Mono', monospace;
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 0.8px;
    color: var(--text-dim);
    display: flex;
    flex-direction: column;
    line-height: 1.3;
  }
  .sf-foot-tr {
    font-size: 7px;
    font-weight: 500;
    color: var(--text-muted);
    letter-spacing: 0.4px;
  }
  .sf-led {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    border: 1px solid #160d04;
    flex-shrink: 0;
  }
  .sf-led.on { background: #10b981; box-shadow: 0 0 9px #10b981; }
  .sf-led.off { background: #3a1512; box-shadow: inset 0 1px 2px #000; }
</style>
