<script lang="ts">
  import { invoke } from '@tauri-apps/api/core';
  import { scrapedUsername, scrapedBio, scrapedPosts, autoTriggerLLM } from '../store';
  
  let username = '';
  let bio = '';
  let posts: string[] = [];
  
  // Mağaza (store) güncellemelerini dinle
  $: {
    if ($scrapedUsername) username = $scrapedUsername;
    if ($scrapedBio) bio = $scrapedBio;
    if ($scrapedPosts && $scrapedPosts.length > 0) posts = [...$scrapedPosts];
    
    // Eğer otomatik tetikleme bayrağı kalktıysa ve kullanıcı adı varsa analizi baslat
    if ($autoTriggerLLM && username) {
        autoTriggerLLM.set(false); // Bayrağı indir
        setTimeout(() => {
            analyzeReal(); // Asenkron tetikle
        }, 500);
    }
  }

  let analysis: any = null;
  let loading = false;
  let error = '';

  async function analyzeReal() {
    loading = true;
    error = '';
    analysis = null;

    try {
      // GERÇEK analiz - şablon değil
      analysis = await invoke('analyze_target_real', {
        username,
        bio,
        posts
      });
    } catch (e: any) {
      error = e.toString();
    } finally {
      loading = false;
    }
  }

  function addPost() {
    posts = [...posts, ''];
  }

  function removePost(index: number) {
    posts = posts.filter((_, i) => i !== index);
  }
</script>

<div class="real-analysis-panel">
  <h2>🔴 GERÇEK ANALİZ (Şablon YOK)</h2>

  <div class="input-section">
    <label for="username">Kullanıcı Adı:</label>
    <input id="username" bind:value={username} placeholder="@hedef_kisi" />

    <label for="bio">Biyografi:</label>
    <textarea id="bio" bind:value={bio} placeholder="Hedefin biyografisi"></textarea>

    <label for="posts">Son Paylaşımlar:</label>
    {#each posts as post, i}
      <div class="post-input">
        <textarea id="posts" bind:value={posts[i]} placeholder="Paylaşım metni {i + 1}"></textarea>
        <button on:click={() => removePost(i)}>Sil</button>
      </div>
    {/each}
    <button on:click={addPost}>+ Paylaşım Ekle</button>
  </div>

  <button on:click={analyzeReal} disabled={loading || !username}>
    {loading ? '⏳ GERÇEK ANALİZ YAPILIYOR...' : '🔍 ANALİZ ET (LLM)'}
  </button>

  {#if error}
    <div class="error">{error}</div>
  {/if}

  {#if analysis}
    <div class="results">
      <h3>✅ GERÇEK ANALİZ SONUÇLARI</h3>
      
      <div class="result-item">
        <strong>Gerçek Arzu:</strong>
        <p>{analysis.real_desire}</p>
      </div>

      <div class="result-item">
        <strong>Spesifik Detay:</strong>
        <p>{analysis.specific_detail}</p>
      </div>

      <div class="result-item">
        <strong>Bağlanma Stili:</strong>
        <p>{analysis.attachment_style}</p>
      </div>

      <div class="result-item">
        <strong>Core Wound (Temel Yara):</strong>
        <p>{analysis.core_wound}</p>
      </div>

      <div class="result-item highlight">
        <strong>Önerilen İlk Mesaj (Claude Üretti):</strong>
        <p class="message">{analysis.first_message}</p>
        <small>Güven: {(analysis.confidence * 100).toFixed(0)}%</small>
      </div>
    </div>
  {/if}
</div>

<style>
  .real-analysis-panel {
    padding: 20px;
    background: #1a1a1a;
    border: 2px solid #ff0000;
    border-radius: 8px;
  }

  h2 {
    color: #ff0000;
    margin-bottom: 20px;
  }

  .input-section {
    margin-bottom: 20px;
  }

  label {
    display: block;
    margin-top: 10px;
    color: #fff;
  }

  input, textarea {
    width: 100%;
    padding: 8px;
    margin-top: 4px;
    background: #2a2a2a;
    border: 1px solid #444;
    color: #fff;
  }

  .post-input {
    margin-bottom: 10px;
  }

  button {
    padding: 10px 20px;
    background: #ff0000;
    color: #fff;
    border: none;
    cursor: pointer;
    margin-top: 10px;
  }

  button:disabled {
    background: #666;
    cursor: not-allowed;
  }

  .error {
    color: #ff0000;
    padding: 10px;
    background: #330000;
    margin-top: 10px;
  }

  .results {
    margin-top: 20px;
    padding: 15px;
    background: #0a0a0a;
    border: 1px solid #00ff00;
  }

  .result-item {
    margin-bottom: 15px;
  }

  .result-item strong {
    color: #00ff00;
  }

  .result-item p {
    margin: 5px 0;
    color: #fff;
  }

  .highlight {
    padding: 15px;
    background: #001a00;
    border-left: 4px solid #00ff00;
  }

  .message {
    font-style: italic;
    font-size: 1.1em;
  }
</style>
