<!-- VAULT anahtar kilidi: süslü anahtar, açıkken 90° döner + yeşil halka. -->
<script lang="ts">
  export let unlocked: boolean;
  export let onToggle: () => void;
</script>

<button
  class="keylock {unlocked ? 'unlocked' : 'locked'}"
  aria-label="Vault key lock"
  aria-pressed={unlocked}
  on:click={onToggle}
  title={unlocked ? 'Kilit açık — kapatmak için çevir' : 'Kilitli — açmak için çevir'}
>
  <span class="disc">
    <span class="ring-text">LOCK · SECURE ·</span>
    <span class="hole"></span>
  </span>
  <span class="key">
    <span class="bow"></span>
    <span class="shaft"></span>
    <span class="teeth"></span>
  </span>
</button>

<style>
  .keylock {
    position: relative;
    width: 76px;
    height: 64px;
    background: transparent;
    border: none;
    cursor: pointer;
    padding: 0;
  }
  .disc {
    position: absolute;
    right: 2px;
    top: 6px;
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: radial-gradient(circle at 35% 30%, #d4af37 0%, #8a6332 55%, #3a220e 100%);
    border: 2px solid #ffe89e;
    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.75), inset 0 1px 2px rgba(255, 255, 255, 0.5);
    transition: box-shadow 0.2s;
  }
  .unlocked .disc {
    box-shadow: 0 0 14px rgba(16, 185, 129, 0.8), inset 0 0 8px rgba(16, 185, 129, 0.5);
    border-color: #7dfcd0;
  }
  .ring-text {
    position: absolute;
    inset: 4px;
    border-radius: 50%;
    border: 1px dashed rgba(20, 10, 2, 0.55);
  }
  .hole {
    position: absolute;
    left: 50%;
    top: 50%;
    width: 9px;
    height: 20px;
    transform: translate(-50%, -50%);
    background: #000;
    border-radius: 5px 5px 2px 2px;
    box-shadow: inset 0 2px 3px #000, 0 1px 0 rgba(255, 255, 255, 0.3);
  }
  .hole::before {
    content: '';
    position: absolute;
    left: 50%;
    top: -4px;
    width: 10px;
    height: 10px;
    transform: translateX(-50%);
    background: #000;
    border-radius: 50%;
  }
  .key {
    position: absolute;
    left: 0;
    top: 50%;
    width: 44px;
    height: 20px;
    margin-top: -10px;
    transform-origin: 40px 10px;
    transition: transform 0.25s cubic-bezier(0.34, 1.4, 0.64, 1);
  }
  .locked .key { transform: rotate(0deg); }
  .unlocked .key { transform: rotate(-90deg); }
  .bow {
    position: absolute;
    left: 0;
    top: 1px;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    border: 4px solid #a88428;
    box-shadow: 0 2px 3px rgba(0, 0, 0, 0.7), inset 0 1px 1px rgba(255, 255, 255, 0.5);
    background: transparent;
  }
  .shaft {
    position: absolute;
    left: 18px;
    top: 8px;
    width: 22px;
    height: 5px;
    background: linear-gradient(180deg, #e8cf7a, #8a6332);
    border-radius: 2px;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.7);
  }
  .teeth {
    position: absolute;
    left: 32px;
    top: 12px;
    width: 4px;
    height: 7px;
    background: #8a6332;
    box-shadow: 5px 0 0 #8a6332;
  }
</style>
