<script lang="ts">
  export let frequencyMap:any=null; export let seismosEvents:any=null; export let voidMap:any=null;
  export let strataMap:any=null; export let gravityMap:any=null; export let pulseMap:any=null; export let keyMatrix:any=null;
  $: waveform=frequencyMap?.waveform||[]; $: maxE=Math.max(1,...waveform);
</script>
{#if frequencyMap || seismosEvents || voidMap || strataMap || gravityMap || pulseMap || keyMatrix}
<section class="shell">
 <header><b>◈ PINEAL 7-PILLAR</b><small>FREQUENCY · SEISMOS · VOID · STRATA · GRAVITY · PULSE · KEY</small></header>
 {#if waveform.length}<article><h4>∿ FREQUENCY</h4><div class="wave">{#each waveform as v}<i style={`height:${Math.max(2,v/maxE*52)}px`}></i>{/each}</div><p>μ {frequencyMap.energy_mean?.toFixed(2)} · σ {frequencyMap.energy_std?.toFixed(2)} · night {((frequencyMap.night_energy_share||0)*100).toFixed(0)}%</p></article>{/if}
 {#if seismosEvents?.events?.length}<article><h4>⚡ SEISMOS</h4>{#each seismosEvents.events.slice(0,4) as e}<p><b>{e.kind}</b> · {Number(e.intensity).toFixed(1)} — {e.observables?.[0]}</p>{/each}</article>{/if}
 {#if voidMap?.signals?.length}<article><h4>◎ VOID</h4>{#each voidMap.signals.slice(0,5) as v}<p>{v.topic} <meter min="0" max="1" value={v.absence_score}></meter> {(v.absence_score*100).toFixed(0)}%</p>{/each}</article>{/if}
 {#if strataMap?.fossils?.length || strataMap?.drifts?.some((d:any)=>d.is_significant)}<article><h4>⛏ STRATA</h4>{#each strataMap.fossils?.slice(0,3)||[] as f}<p>🦴 {f.topic} · {(f.extinction_confidence*100).toFixed(0)}%</p>{/each}</article>{/if}
 {#if gravityMap?.wells?.length}<article><h4>⊛ GRAVITY</h4>{#each gravityMap.wells.slice(0,5) as w}<p>{w.anchor} · ×{w.pull.toFixed(1)} {w.is_black_hole?'●':''}</p>{/each}</article>{/if}
 {#if pulseMap?.signals?.length}<article><h4>♡ PULSE · {pulseMap.rhythm_signature}</h4>{#each pulseMap.signals as s}<p>{s.label||s.signal_type} · z={s.z_score.toFixed(1)}</p>{/each}</article>{/if}
 {#if keyMatrix && keyMatrix.status!=='INSUFFICIENT_DATA'}<article class="key"><h4>🔑 RESONANCE KEY · {((keyMatrix.confidence||0)*100).toFixed(0)}%</h4><p>{keyMatrix.gate_key}</p><p>{keyMatrix.rhythm_note}</p></article>{/if}
</section>{/if}
<style>
.shell{border:1px solid #3d2b17;padding:12px;background:#0a0705;border-radius:6px;display:grid;gap:8px}header{display:flex;justify-content:space-between;color:#d4af37}header small{font-size:8px;color:#a3e635}article{border:1px solid #334155;padding:8px;background:#070c10}h4{margin:0 0 6px;color:#67e8f9;font-size:11px}p{margin:4px 0;color:#cbd5e1;font-size:10px}.wave{height:56px;display:flex;align-items:flex-end;gap:2px}.wave i{width:5px;background:#22d3ee}.key{border-color:#d4af37}meter{width:100px}
</style>
