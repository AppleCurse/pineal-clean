<!-- KASA GİRİŞ LCD'si: Instagram çerez havuzu mühürleme (GERÇEK /api/vault).
     X satırı B4 ile devre dışıdır — dürüstçe öyle yazar, sahte giriş yok.
     Çerez değeri asla loglanmaz ve mühür sonrası girdiden silinir. -->
<script lang="ts">
  import { clientId, apiFetch, logs } from '../../store';
  import { sysTelemetry } from '../../lib/telemetry';
  import { playClick } from '../../lib/consoleAudio';

  let cookie = '';
  let sealing = false;

  // Sunucuda kasa okuma ucu yok (secret'lar geri verilmez); bu istemciden
  // mühürleme yapıldığı bilgisi yalnızca yerel hatırlanır.
  const SEAL_KEY = 'pineal_vault_cookie_sealed';
  function readSeal(): string {
    try { return localStorage.getItem(SEAL_KEY) || ''; } catch { return ''; }
  }
  let sealedAt = readSeal();

  async function seal() {
    if (!cookie.trim() || sealing) return;
    sealing = true;
    playClick(280, 50);
    try {
      const res = await apiFetch('/api/vault', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ client_id: $clientId, x_cookie: cookie.trim() }),
      });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const now = new Date().toLocaleString();
      try { localStorage.setItem(SEAL_KEY, now); } catch { /* bellek yetmezse oturumluk kalır */ }
      sealedAt = now;
      cookie = '';
      playClick(420, 60);
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'INFO', msg: 'KASA: IG çerez havuzu mühürlendi (rotasyon hazır)' }]);
    } catch (e: any) {
      logs.update(l => [...l, { ts: new Date().toLocaleTimeString(), level: 'ERROR', msg: `KASA HATASI: ${e?.message || e}` }]);
    } finally {
      sealing = false;
    }
  }

  function forgetSeal() {
    try { localStorage.removeItem(SEAL_KEY); } catch { /* ignore */ }
    sealedAt = '';
    playClick(140, 40);
  }
</script>

<div class="lcd-bezel">
  <div class="lcd-scan"></div>
  <div class="lcd-head">
    <span class="lcd-title">KASA · GİRİŞ</span>
    <span class="lcd-title-tr">VAULT · LOGIN</span>
  </div>

  <!-- INSTAGRAM: gerçek çerez havuzu girişi -->
  <div class="lcd-row">
    <div class="lcd-line">
      <span class="lcd-net">INSTAGRAM</span>
      <span class="lcd-led {sealedAt ? 'on' : 'off'}" title={sealedAt ? `Mühürlendi: ${sealedAt}` : 'Henüz mühür yok'}></span>
    </div>
    <textarea
      class="lcd-input"
      rows="2"
      bind:value={cookie}
      placeholder="sessionid çerezi · cookie"
      spellcheck={false}
      disabled={sealing}
    ></textarea>
    <div class="lcd-line">
      <button class="lcd-btn" on:click={seal} disabled={sealing || !cookie.trim()}>
        {sealing ? 'MÜHÜRLENİYOR…' : 'MÜHÜRLE (SEAL)'}
      </button>
      {#if sealedAt}
        <button class="lcd-mini" on:click={forgetSeal} title="Yerel mühür notunu unut">UNUT</button>
      {/if}
    </div>
    <div class="lcd-note">{sealedAt ? `Mühürlü: ${sealedAt}` : 'Havuzu değiştirir · Replaces pool'}</div>
  </div>

  <!-- X: B4 ile devre dışı — giriş yok, bilgi var -->
  <div class="lcd-row lcd-x">
    <div class="lcd-line">
      <span class="lcd-net">X (TWITTER)</span>
      <span class="lcd-led off-red"></span>
    </div>
    <div class="lcd-off">DEVRE DIŞI · B4 (DISABLED)</div>
    <div class="lcd-note">X kazıması kapalı; havuz IG rotasyonunda kullanılır</div>
  </div>

  <div class="lcd-foot">
    <span>KASA: {$sysTelemetry.ok ? ($sysTelemetry.vault ? 'DOLU' : 'BOŞ') : '—'}</span>
    <span>BROWSER: {$sysTelemetry.ok ? ($sysTelemetry.browser ? 'VAR' : 'YOK') : '—'}</span>
  </div>
</div>

<style>
  .lcd-bezel {
    position: relative;
    width: 248px;
    background: linear-gradient(180deg, #1c1408 0%, #0d0903 100%);
    border: 2px solid #8a6332;
    border-radius: 6px;
    padding: 8px 10px;
    box-shadow: inset 0 0 22px rgba(0, 0, 0, 0.9), 0 4px 10px rgba(0, 0, 0, 0.7);
    overflow: hidden;
  }
  .lcd-scan {
    position: absolute;
    inset: 0;
    pointer-events: none;
    background: repeating-linear-gradient(180deg, rgba(255, 255, 255, 0.025) 0 1px, transparent 1px 3px);
  }
  .lcd-head {
    display: flex;
    flex-direction: column;
    align-items: center;
    border-bottom: 1px solid #3d2b17;
    padding-bottom: 5px;
    margin-bottom: 6px;
  }
  .lcd-title {
    font-family: 'Cinzel', serif;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1.5px;
    color: #ffb000;
    text-shadow: 0 0 8px rgba(255, 176, 0, 0.6);
  }
  .lcd-title-tr {
    font-family: 'JetBrains Mono', monospace;
    font-size: 7px;
    letter-spacing: 1px;
    color: #8a6a2a;
  }
  .lcd-row {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 5px 0;
  }
  .lcd-x {
    border-top: 1px dashed #3d2b17;
    margin-top: 2px;
  }
  .lcd-line {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 6px;
  }
  .lcd-net {
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1px;
    color: #ffcf6e;
  }
  .lcd-led {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    border: 1px solid #000;
    flex-shrink: 0;
  }
  .lcd-led.on { background: #10b981; box-shadow: 0 0 8px #10b981; }
  .lcd-led.off { background: #2a1a08; box-shadow: inset 0 1px 2px #000; }
  .lcd-led.off-red { background: #3a1512; box-shadow: inset 0 1px 2px #000; }
  .lcd-input {
    background: #050302;
    border: 1px solid #5a3d1c;
    color: #ffb000;
    font-family: 'JetBrains Mono', monospace;
    font-size: 9px;
    border-radius: 3px;
    padding: 4px 6px;
    width: 100%;
    resize: none;
    outline: none;
    box-shadow: inset 0 0 8px #000;
  }
  .lcd-input:focus { border-color: #ffb000; }
  .lcd-input::placeholder { color: #6b4e1e; }
  .lcd-btn {
    flex: 1;
    background: linear-gradient(180deg, #d4af37, #8a6332);
    border: 1px solid #ffe89e;
    color: #120904;
    font-family: 'Cinzel', serif;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 0.8px;
    border-radius: 3px;
    padding: 4px 8px;
    cursor: pointer;
  }
  .lcd-btn:disabled { opacity: 0.45; cursor: not-allowed; }
  .lcd-mini {
    background: transparent;
    border: 1px solid #5a3d1c;
    color: #8a6a2a;
    font-family: 'JetBrains Mono', monospace;
    font-size: 7px;
    border-radius: 3px;
    padding: 3px 6px;
    cursor: pointer;
  }
  .lcd-note {
    font-family: 'JetBrains Mono', monospace;
    font-size: 6.5px;
    color: #8a6a2a;
    line-height: 1.3;
  }
  .lcd-off {
    font-family: 'JetBrains Mono', monospace;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 1px;
    color: #5a3a30;
  }
  .lcd-foot {
    display: flex;
    justify-content: space-between;
    border-top: 1px solid #3d2b17;
    margin-top: 4px;
    padding-top: 5px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 7.5px;
    font-weight: 700;
    letter-spacing: 0.6px;
    color: #ffcf6e;
  }
</style>
