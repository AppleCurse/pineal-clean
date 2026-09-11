<!-- CANLI TARAYICI LCD'si: kokpit içinden gerçek Chromium görünümü.
     Kullanıcı Instagram girişini burada ELLE yapar (şifre / Google / 2FA);
     tuşlar doğrudan Instagram'a gider, parola backend'e asla ulaşmaz.
     Giriş bitince OTURUMU KAYDET yalnız `sessionid`'yi kasaya mühürler.
     Chromium yoksa dürüstçe TARAYICI YOK basar + manuel çerez yedeği sunar. -->
<script lang="ts">
  import { get } from 'svelte/store';
  import { clientId, apiFetch, logs } from '../../store';
  import { sysTelemetry } from '../../lib/telemetry';
  import { playClick } from '../../lib/consoleAudio';

  // Backend viewport sözleşmesi: 800x600 (browser_session.VIEWPORT_*).
  const VW = 800;
  const VH = 600;

  let live = false;
  let pageUrl = '';
  let pageTitle = '';
  let unavailable = false; // Chromium bu makinede yok
  let unavailMsg = '';
  let shotUrl: string | null = null;
  let shotEl: HTMLImageElement | null = null;
  let textBuf = '';
  let cookieFallback = ''; // manuel çerez yedeği (TARAYICI YOK iken)
  let busy = false; // tek uçuş kuralı
  let pollTimer: ReturnType<typeof setInterval> | null = null;

  function log(level: string, msg: string) {
    logs.update((l) => [...l, { ts: new Date().toLocaleTimeString(), level, msg }]);
  }

  async function post(path: string, body: Record<string, unknown>): Promise<Response> {
    return apiFetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  async function refreshState(): Promise<void> {
    try {
      const res = await apiFetch(`/api/browser/state?client_id=${get(clientId)}`);
      if (!res.ok) return;
      const st = await res.json();
      live = !!st.live;
      pageUrl = String(st.url || '');
      pageTitle = String(st.title || '');
    } catch {
      /* telemetri yokluğunda sessiz; ibreler park eder */
    }
  }

  async function refreshShot(): Promise<void> {
    if (!live || busy) return;
    try {
      const res = await apiFetch(`/api/browser/shot?client_id=${get(clientId)}&k=${Date.now()}`);
      if (!res.ok) {
        if (res.status === 409) { live = false; }
        return;
      }
      const blob = await res.blob();
      const next = URL.createObjectURL(blob);
      if (shotUrl) URL.revokeObjectURL(shotUrl);
      shotUrl = next;
    } catch {
      /* kare kaçarsa sonraki tur dener */
    }
  }

  function startPoll() {
    stopPoll();
    pollTimer = setInterval(() => {
      void refreshState().then(() => refreshShot());
    }, 2000);
  }

  function stopPoll() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = null;
  }

  async function act(label: string, fn: () => Promise<Response>): Promise<void> {
    if (busy) return;
    busy = true;
    playClick(280, 50);
    try {
      const res = await fn();
      if (res.status === 503) {
        const data = await res.json().catch(() => ({}));
        unavailable = true;
        unavailMsg = String(data?.error?.message || 'Chromium yok');
        live = false;
        log('ERROR', `TARAYICI YOK: ${unavailMsg.slice(0, 90)}`);
        return;
      }
      if (!res.ok) throw new Error('HTTP ' + res.status);
      unavailable = false;
      await refreshState();
      await refreshShot();
      playClick(420, 60);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      log('ERROR', `LCD ${label} HATASI: ${msg}`);
    } finally {
      busy = false;
    }
  }

  function openBrowser() {
    void act('aç', () => post('/api/browser/open', { client_id: get(clientId) }));
  }

  function closeBrowser() {
    void act('kapat', () => post('/api/browser/close', { client_id: get(clientId) }));
  }

  function goBack() { void act('geri', () => post('/api/browser/back', { client_id: get(clientId) })); }

  function pressKey(key: string) {
    void act(key, () => post('/api/browser/press', { client_id: get(clientId), key }));
  }

  function sendText() {
    const text = textBuf;
    if (!text) return;
    textBuf = '';
    // NOT: parola bu yoldan geçebilir; log satırına ASLA yazılmaz.
    void act('yaz', () => post('/api/browser/type', { client_id: get(clientId), text }));
  }

  function handleShotClick(e: MouseEvent) {
    if (!live || !shotEl) return;
    const r = shotEl.getBoundingClientRect();
    if (r.width < 1 || r.height < 1) return;
    const x = Math.round(((e.clientX - r.left) / r.width) * VW);
    const y = Math.round(((e.clientY - r.top) / r.height) * VH);
    void act('tık', () => post('/api/browser/click', { client_id: get(clientId), x, y }));
  }

  // Klavye: viewport odaktayken oklar/Enter/Tab/Escape Instagram'a gider.
  function handleViewportKey(e: KeyboardEvent) {
    if (!live) return;
    const map: Record<string, string> = {
      Enter: 'Enter', Tab: 'Tab', Escape: 'Escape', Backspace: 'Backspace', Delete: 'Delete',
      ArrowLeft: 'ArrowLeft', ArrowRight: 'ArrowRight', ArrowUp: 'ArrowUp', ArrowDown: 'ArrowDown',
    };
    const key = map[e.key];
    if (!key) return;
    e.preventDefault();
    pressKey(key);
  }

  async function saveSession() {
    if (busy) return;
    busy = true;
    playClick(280, 50);
    try {
      const res = await post('/api/browser/save', { client_id: get(clientId) });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      if (data.saved) {
        log('INFO', 'KASA: Canlı LCD oturumu mühürlendi (sessionid).');
        playClick(520, 70);
      } else {
        log('WARNING', `OTURUM YOK: ${data.hint || 'Instagram girişi tamamlanmamış.'}`);
      }
      await refreshState();
    } catch (e: unknown) {
      log('ERROR', `KAYIT HATASI: ${e instanceof Error ? e.message : e}`);
    } finally {
      busy = false;
    }
  }

  // Manuel çerez yedeği: TARAYICI YOK iken eski /api/vault yoluna mühürler.
  async function sealCookieFallback() {
    if (!cookieFallback.trim() || busy) return;
    busy = true;
    playClick(280, 50);
    const value = cookieFallback.trim();
    cookieFallback = '';
    try {
      const res = await post('/api/vault', { client_id: get(clientId), x_cookie: value });
      if (!res.ok) throw new Error('HTTP ' + res.status);
      log('INFO', 'KASA: Manuel çerez mühürlendi (yedek havuz).');
      playClick(420, 60);
    } catch (e: unknown) {
      log('ERROR', `KASA HATASI: ${e instanceof Error ? e.message : e}`);
    } finally {
      busy = false;
    }
  }

  // Bileşen yaşam döngüsü: açılırken bir kez yokla, sonra 2 sn nabız.
  import { onMount, onDestroy } from 'svelte';
  onMount(() => {
    void refreshState().then(() => refreshShot());
    startPoll();
  });
  onDestroy(() => {
    stopPoll();
    if (shotUrl) URL.revokeObjectURL(shotUrl);
  });
</script>

<div class="lcd-bezel">
  <div class="lcd-head">
    <span class="lcd-title">CANLI TARAYICI</span>
    <span class="lcd-dot" class:on={live} class:off={!live}></span>
  </div>

  {#if unavailable && !live}
    <div class="lcd-noavail">
      <div class="lcd-noavail-big">TARAYICI YOK</div>
      <div class="lcd-noavail-msg" title={unavailMsg}>{unavailMsg.slice(0, 110) || 'Chromium kurulu değil.'}</div>
      <button type="button" class="lcd-btn" on:click={openBrowser} disabled={busy}>YENİDEN DENE</button>
    </div>
  {:else if !live}
    <div class="lcd-idle">
      <div class="lcd-idle-msg">Tarayıcı kapalı — açıp Instagram'a elle giriş yap.</div>
      <button type="button" class="lcd-btn lcd-btn-big" on:click={openBrowser} disabled={busy}>TARAYICIYI AÇ</button>
    </div>
  {:else}
    <!-- svelte-ignore a11y-no-noninteractive-tabindex a11y-no-noninteractive-element-interactions --
        Uzak masaüstü viewport'u: role=application + tam klavye kontrolü (oklar/Enter/Tab/Escape) bilinçli seçimdir. -->
    <div
      class="lcd-viewport"
      role="application"
      tabindex="0"
      aria-label="Canlı tarayıcı görünümü. Fareyle tıklayın, ok tuşları ve Enter klavyeden çalışır."
      on:click={handleShotClick}
      on:keydown={handleViewportKey}
    >
      {#if shotUrl}
        <img
          bind:this={shotEl}
          src={shotUrl}
          alt="Canlı tarayıcı"
          class="lcd-shot"
          draggable={false}
        />
      {:else}
        <div class="lcd-loading">GÖRÜNTÜ ALINIYOR…</div>
      {/if}
    </div>
    <div class="lcd-url" title={pageTitle || pageUrl}>{pageUrl ? pageUrl.slice(0, 52) : '—'}</div>

    <div class="lcd-row">
      <input
        class="lcd-input"
        type="text"
        placeholder="metin yaz… (şifre buraya, loga düşmez)"
        bind:value={textBuf}
        on:keydown={(e) => { if (e.key === 'Enter') sendText(); }}
        disabled={busy}
        autocomplete="off"
        spellcheck={false}
      />
      <button type="button" class="lcd-btn" on:click={sendText} disabled={busy || !textBuf}>YAZ</button>
    </div>

    <div class="lcd-row lcd-keys">
      <button type="button" class="lcd-btn lcd-mini" on:click={() => pressKey('Tab')} disabled={busy}>TAB</button>
      <button type="button" class="lcd-btn lcd-mini" on:click={() => pressKey('Enter')} disabled={busy}>ENTER</button>
      <button type="button" class="lcd-btn lcd-mini" on:click={() => pressKey('Escape')} disabled={busy}>ESC</button>
      <button type="button" class="lcd-btn lcd-mini" on:click={() => pressKey('Backspace')} disabled={busy}>⌫</button>
      <button type="button" class="lcd-btn lcd-mini" on:click={goBack} disabled={busy}>← GERİ</button>
    </div>

    <div class="lcd-row">
      <span class="lcd-x-Disabled" title="B4: X kazıması devre dışıdır">X: KAPALI</span>
      <button type="button" class="lcd-btn lcd-save" on:click={saveSession} disabled={busy}>OTURUMU KAYDET</button>
      <button type="button" class="lcd-btn lcd-mini" on:click={closeBrowser} disabled={busy}>KAPAT</button>
    </div>
  {/if}

  {#if unavailable && !live}
    <details class="lcd-fallback">
      <summary>Manuel çerez yedeği</summary>
      <div class="lcd-row">
        <input
          class="lcd-input"
          type="password"
          placeholder="sessionid çerezi yapıştır…"
          bind:value={cookieFallback}
          disabled={busy}
          autocomplete="off"
          spellcheck={false}
        />
        <button type="button" class="lcd-btn" on:click={sealCookieFallback} disabled={busy || !cookieFallback}>MÜHÜRLE</button>
      </div>
    </details>
  {/if}

  <div class="lcd-foot">
    <span>OTURUM: {$sysTelemetry.instagramSession ? 'KAYITLI' : 'YOK'}</span>
    <span>KASA: {$sysTelemetry.vault ? 'DOLU' : 'BOŞ'}</span>
  </div>
</div>

<style>
  .lcd-bezel {
    width: 330px;
    background: #101408;
    border: 2px solid #3a3f2a;
    border-radius: 8px;
    padding: 8px;
    font-family: 'Courier New', monospace;
    color: #c8d47a;
    box-shadow: inset 0 0 24px rgba(0, 0, 0, 0.75);
  }
  .lcd-head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
  }
  .lcd-title { font-size: 11px; letter-spacing: 2px; color: #e0e8a0; }
  .lcd-dot { width: 9px; height: 9px; border-radius: 50%; background: #4a4a3a; }
  .lcd-dot.on { background: #9dff57; box-shadow: 0 0 6px #9dff57; }
  .lcd-viewport {
    width: 100%;
    aspect-ratio: 4 / 3;
    background: #050604;
    border: 1px solid #2c3120;
    border-radius: 3px;
    overflow: hidden;
    cursor: crosshair;
    outline: none;
  }
  .lcd-viewport:focus { border-color: #9dff57; }
  .lcd-shot { width: 100%; height: 100%; object-fit: fill; display: block; }
  .lcd-loading {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 11px;
    letter-spacing: 2px;
    color: #7a8455;
  }
  .lcd-url {
    font-size: 10px;
    color: #8b9560;
    margin: 4px 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }
  .lcd-row { display: flex; gap: 5px; margin-top: 5px; align-items: center; }
  .lcd-input {
    flex: 1;
    min-width: 0;
    background: #050604;
    border: 1px solid #2c3120;
    color: #e0e8a0;
    font-family: inherit;
    font-size: 11px;
    padding: 5px 6px;
    border-radius: 3px;
  }
  .lcd-input:focus { border-color: #9dff57; outline: none; }
  .lcd-btn {
    background: #232818;
    border: 1px solid #4a5232;
    color: #d8e49a;
    font-family: inherit;
    font-size: 10px;
    letter-spacing: 1px;
    padding: 5px 9px;
    border-radius: 3px;
    cursor: pointer;
    white-space: nowrap;
  }
  .lcd-btn:hover:not(:disabled) { background: #313823; border-color: #9dff57; }
  .lcd-btn:disabled { opacity: 0.45; cursor: default; }
  .lcd-btn-big { font-size: 12px; padding: 9px 14px; width: 100%; margin-top: 6px; }
  .lcd-mini { font-size: 9px; padding: 4px 6px; }
  .lcd-save { flex: 1; border-color: #6a7a35; color: #f0f5c8; }
  .lcd-keys { flex-wrap: wrap; }
  .lcd-idle, .lcd-noavail { text-align: center; padding: 10px 4px; }
  .lcd-idle-msg, .lcd-noavail-msg { font-size: 10px; color: #8b9560; margin-bottom: 4px; }
  .lcd-noavail-big { font-size: 16px; letter-spacing: 3px; color: #ff9d5c; margin-bottom: 4px; }
  .lcd-x-Disabled { font-size: 9px; color: #6a5a4a; letter-spacing: 1px; white-space: nowrap; }
  .lcd-fallback { margin-top: 6px; font-size: 10px; }
  .lcd-fallback summary { cursor: pointer; color: #8b9560; }
  .lcd-foot {
    display: flex;
    justify-content: space-between;
    margin-top: 7px;
    padding-top: 5px;
    border-top: 1px solid #2c3120;
    font-size: 9px;
    letter-spacing: 1px;
    color: #7a8455;
  }
</style>
