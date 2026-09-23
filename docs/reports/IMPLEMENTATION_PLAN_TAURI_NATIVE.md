# PINEAL-HERETIC v5.0 - TAURI NATIVE + AGENT RACK + ORGANIK IRIS + VAULT PLANI
Tarih: 2026-09-22

## DURUM TESPITI (mevcut)

- **rust_core/src-tauri/tauri.conf.json**: minimal 800x600, identifier com.tauri.dev, devUrl localhost:5173, beforeDevCommand npm run dev (hatali path), csp null
- **rust_core/src-tauri/src/lib.rs**: 6 komut (create_vault, open_vault, set/get_credentials, query_aspasia, start_analysis), CoreState tek, telemetry bridge var
- **rust_core/src/tauri_bridge.rs**: sadece CoreState + telemetry bridge, vault yolu default_vault_path tek kaynak
- **frontend**: Svelte 5 + Vite 6, App.svelte WS ile backend'e bagli, AtlasPinealCockpit.svelte 16:9 sasi + yasayan goz (lazer değil, translate/scale), store.ts API_BASE + WS_BASE tek kaynak, localStorage token
- **backend/api.py**: FastAPI + WS /ws/{client_id}, task executor, rate limit, body limit, vault interlock yok, redis yok
- **docker-compose.yml**: tek servis pineal (8000), 3 volume, replica 1
- **functions/ws/[[path]].ts**: Cloudflare WS proxy, BACKEND_ORIGIN env, WebSocketPair pompa
- **agent_core**: 12+ ajan (mirror_truth, autonomous_verifier, human_behavior, passion_mapper, friction_detector, cognitive_profiler, resonance_calc, pattern_interrupt, osint_investigator, authenticity_auditor, depth_analyst, interpreter_agent, vb), pillar_orchestrator 7 pillar, event_bus.rs broadcast channel
- **Vault**: StealthVault age+argon2, default_vault_path $PINEAL_VAULT_DIR veya $HOME/.pineal_vault/vault.json
- **Aspasia**: aspasia_chief.py + dialogue_manager.py ayri, UI'den /api/aspasia/chat ve /api/aspasia/command ile tetikleniyor

## YAPILACAKLAR - 4 ANA GÖREV

### GÖREV 1: Svelte arayüzünü Tauri native pencereye oturtma (GPU hızlandırma)

**Hedef:** Tarayici sekmesinden çıkıp doğrudan GPU hızlandırmalı native pencere.

**Adimlar:**
1. `rust_core/src-tauri/tauri.conf.json` güncelle:
   - productName: "ATLAS PINEAL" / "PINEAL-HERETIC"
   - version: 5.0.0 (VERSION dosyasindan)
   - identifier: com.pineal.heretic
   - build.frontendDist: ../../frontend/dist (ayni)
   - build.devUrl: http://localhost:1420 (Tauri default) + 5173 fallback
   - build.beforeDevCommand: npm run dev --prefix ../../frontend -- --host 0.0.0.0 --port 1420 --strictPort
   - build.beforeBuildCommand: npm run build --prefix ../../frontend
   - app.windows[0]: label main, title "ATLAS PINEAL OBSERVATORY - HERETIC v5.0", width 1920, height 1080, minWidth 1280, minHeight 720, resizable true, fullscreen false, center true, decorations true, transparent false, visible true, focus true
   - app.security.csp: null kalabilir ama asset protokol icin genislet
   - bundle.active true, targets all, icon list, resources []

2. `frontend/vite.config.ts` güncelle:
   - server.port 1420, strictPort true, host 0.0.0.0, allowedHosts true
   - server.hmr.port 1421 (Tauri icin)
   - clearScreen false
   - envPrefix ["VITE_", "TAURI_"]
   - proxy /api ve /ws hala 127.0.0.1:8000

3. `rust_core/src-tauri/Cargo.toml` ve `src-tauri/src/lib.rs`:
   - lib.rs'te window olusturma, setup closure'da telemetry bridge zaten var
   - capabilities/default.json'a "core:window:allow-start-dragging", "core:window:allow-set-size" vb ekle veya shell:allow-open

4. Frontend Tauri entegrasyonu:
   - `frontend/src/lib/tauriBridge.ts` yeni: isTauri() detection, listen pineal-telemetry, invoke vault komutlari
   - `frontend/src/App.svelte` güncelle: eger Tauri ise WS yerine Tauri event dinle, degilse WS
   - `frontend/src/store.ts` güncelle: tauriInvoke wrapper, vaultLocked store
   - `frontend/package.json` ve `frontend/src-tauri` icin @tauri-apps/api ekle (frontend/package.json'a devDependency)

5. GPU hizlandirma:
   - Tauri wry webview zaten GPU kullanir, ama CSS'te will-change, transform3d, backface-visibility hidden ile zorla
   - `app.css` ve `AtlasPinealCockpit.svelte` içinde .living-eye-disk vb için translate3d kullan

### GÖREV 2: Ajanlari Docker Compose bağımsız servis + Redis Pub/Sub + canlı WS köprüsü

**Hedef:** 12 ajan arkada bağımsız, Agent Rack slotları Ready/Active/Wait anlık değişsin.

**Adimlar:**
1. `agent_core/services/redis_bus.py` yeni:
   - Redis client (redis-py), publish agent_status, subscribe
   - Fallback: redis yoksa in-memory dict (graceful degrade)
   - Channel: "pineal:agent:status", "pineal:telemetry", "pineal:events"

2. `agent_core/services/agent_status_tracker.py` yeni:
   - 12 ajan listesi: mirror_truth, autonomous_verifier, human_behavior, passion_mapper, friction_detector, cognitive_profiler, resonance_calculator, pattern_interrupt, osint_investigator, authenticity_auditor, depth_analyst, interpreter_agent
   - Status enum: Ready, Active, Wait, Error, Done
   - update_status(agent_id, status, metadata) -> redis publish + in-memory
   - get_all_statuses() -> dict

3. `backend/api.py` güncelle:
   - lifespan içinde redis_bus init
   - WS endpoint'e agent_status_update mesajları ekle
   - PinealExecutor her ajan başlangıcında tracker.update_status(active), bitişte done
   - Yeni endpoint GET /api/agents/status -> tüm ajan durumları

4. `docker-compose.yml` güncelle:
   - redis: image redis:7-alpine, port 6379, volume pineal_redis
   - pineal-api: build ., depends_on redis, env REDIS_URL=redis://redis:6379, port 8000
   - pineal-worker: same build, command python -m agent_core.task_executor (veya custom worker), depends_on redis
   - pineal-agent-orchestrator: agent status publisher service
   - volumes: pineal_memory, pineal_cache, pineal_vault, pineal_redis
   - network: pineal-net

5. `functions/ws/[[path]].ts` güncelle:
   - Mevcut proxy koru, ama ek olarak agent_status channel'i için JSON mesaj tipi "agent_status_update" forward et
   - BACKEND_ORIGIN yoksa 502

6. `rust_core/src/event_bus.rs` + yeni `redis_bridge.rs`:
   - event_bus.rs'a RedisBridge trait ekle veya yeni modül
   - Cargo.toml'a redis feature (optional)
   - Tauri bridge üzerinden de agent status emit et: app_handle.emit("agent-status", payload)

7. Frontend AgentRack:
   - `frontend/src/components/AgentRack.svelte` yeni: 12 slot, her biri renk, glyph, status (Ready yeşil, Active sarı pulse, Wait gri, Error kırmızı)
   - `frontend/src/store.ts` agentStatuses writable
   - `App.svelte` WS onmessage içinde type==="agent_status_update" ise agentStatuses update
   - `AtlasPinealCockpit.svelte` veya `UnifiedCompactPanel.svelte` içinde sağ tarafa AgentRack yerleştir

### GÖREV 3: Merkez organik iris + Canvas optik katman + holografik tel kafes

**Hedef:** Untitled_2.jpg (mevcut eye.jpg/living_pineal_disk.png) merkeze, mouse tracking mikro, nefes alma, yeşil holografik tel kafes.

**Adimlar:**
1. Asset kontrol: frontend/src/assets/eye.jpg (228k), living_pineal_disk.png (103k), cockpit-v10-reference.png (2.8MB master sasi). Untitled_2.jpg yok, eye.jpg yüksek çözünürlüklü organik iris olarak kullanılacak.

2. `frontend/src/lib/irisRenderer.ts` yeni:
   - Canvas 2D veya WebGL? 2D yeterli, GPU için will-change
   - Sınıf IrisRenderer: constructor(canvas, irisImageSrc)
   - mouse tracking: window mousemove -> targetX/Y normalize (-1..1), lerp 0.04 ile mikro kayma (±4.5px)
   - breathing: sin(elapsed*0.5)*0.012 scale, processing sırasında sin*3.5*0.6 flutter
   - render loop: requestAnimationFrame, iris drawImage with transform, pupil scale
   - nefes: isProcessing true ise daha hızlı ve geniş

3. `frontend/src/components/OrganikIrisCanvas.svelte` yeni:
   - <canvas> + <img> fallback
   - Props: size, scanning (isProcessing), irisSrc
   - onMount: IrisRenderer init, mouse listener, resize observer
   - onDestroy: cancelAnimationFrame
   - CSS: border-radius 50%, overflow hidden, box-shadow iç gölge, GPU: transform translateZ(0)

4. `frontend/src/components/HolographicResonanceMesh.svelte` yeni:
   - Canvas overlay, yeşil #38ef7d tel kafes
   - Çizim: 3 katman - dış çember, iç rezonans ağı (Delaunay benzeri), dönen noktalar
   - Animasyon: rotation slow, pulse sin, processing sırasında hız artışı
   - Props: active (bool), intensity (0..1)

5. `frontend/src/components/AtlasPinealCockpit.svelte` güncelle:
   - living-eye-viewport içindeki <img> yerine OrganikIrisCanvas kullan
   - Üzerine HolographicResonanceMesh overlay
   - Mevcut eyeX/eyeY/targetEyeX logic'i IrisRenderer içine taşı, ama Svelte tarafında da tut (iki katman: Svelte state + Canvas micro)
   - isProcessing store'a bağlı breathing

6. Performans:
   - Canvas'ta will-change: transform, backface-visibility hidden
   - requestAnimationFrame tek loop, iki canvas aynı loop'ta çizilebilir
   - ResizeObserver ile DPR (devicePixelRatio) dikkate al

### GÖREV 4: Vault kilit mandalı + Aspasia terminal -> dialogue_manager zinciri

**Hedef:** Sol alttaki Vault kilit mandalı yerel şifreli kasa yöneticisine (vault.rs) bağlı, anahtar çevrilmeden OSINT/Scraper çıkmayacak, Aspasia terminal komutları dialogue_manager üzerinden otonom ajan zincirine paslanacak.

**Adimlar:**
1. Rust tarafı zaten hazır: vault.rs StealthVault, default_vault_path, create_vault/open_vault/set/get komutları lib.rs'te.

2. Tauri bridge güçlendirme:
   - `rust_core/src-tauri/src/lib.rs` içine yeni komut: check_vault_status -> bool (vault açık mı)
   - Yeni komut: lock_vault -> vault state None yap
   - Mevcut set_vault_credentials zaten var

3. Frontend Vault entegrasyonu:
   - `frontend/src/lib/tauriBridge.ts` içinde invokeVault(action, payload)
   - `frontend/src/store.ts` içine vaultLocked (true default), vaultStatus writable
   - `KeyLock.svelte` onToggle içinde:
     - eğer Tauri: invoke('open_vault' veya 'create_vault') + check_vault_status
     - değilse: mevcut store toggle + localStorage
   - `UnifiedCompactPanel.svelte` triggerAnalysis zaten $keyUnlocked kontrol ediyor, ama backend de kontrol etmeli

4. Backend vault interlock:
   - `backend/api.py` içine vault interlock middleware: eğer client_id'nin vault'u yoksa ve istek /api/experimental/* veya /api/scraper/* veya /api/initiate (scraper_type cross) ise 423 Locked dön
   - Yeni endpoint: POST /api/vault/unlock, POST /api/vault/lock, GET /api/vault/status
   - `agent_core/services/browser_session.py` ve `InstagramGhostScraper` içinde vault check

5. Aspasia terminal -> dialogue_manager:
   - `backend/api.py` /api/aspasia/chat zaten var, ama dialogue_manager'a bağlanmalı
   - Yeni akış: user_message -> AspasiaChief.chat() + DialogueManager.start_session/generate_response
   - Eğer mesaj "hedef @user analiz et" gibi komut içeriyorsa: CommandGateway üzerinden PinealExecutor'a pasla
   - `frontend/src/components/UnifiedCompactPanel.svelte` sendMessage içinde zaten /api/aspasia/command deniyor, sonra fallback chat. Bu akışı koru ama backend'de command gateway'in dialogue_manager ile konuşmasını sağla
   - `agent_core/chat/dialogue_manager.py` zaten session TTL + eviction var, bunu kullan

6. OSINT/Scraper blokajı:
   - `agent_core/services/platform_registry.py` ve `agent_core/scraper/instagram_ghost.py` içinde vault kontrolü
   - `backend/api.py` initiate endpoint'inde: eğer vault kapalıysa ve url dış dünyaya çıkacaksa, task'i başlatma, 423 + "VAULT kilitli" mesajı

## DOSYA DEĞİŞİKLİK LİSTESİ

Yeni dosyalar:
- frontend/src/lib/tauriBridge.ts
- frontend/src/lib/irisRenderer.ts
- frontend/src/components/OrganikIrisCanvas.svelte
- frontend/src/components/HolographicResonanceMesh.svelte
- frontend/src/components/AgentRack.svelte
- agent_core/services/redis_bus.py
- agent_core/services/agent_status_tracker.py
- rust_core/src/redis_bridge.rs

Güncellenecekler:
- rust_core/src-tauri/tauri.conf.json
- rust_core/src-tauri/capabilities/default.json
- rust_core/src-tauri/src/lib.rs
- rust_core/Cargo.toml (redis optional)
- rust_core/src/lib.rs (redis_bridge mod)
- frontend/vite.config.ts
- frontend/src/App.svelte
- frontend/src/store.ts
- frontend/src/components/AtlasPinealCockpit.svelte
- frontend/src/components/UnifiedCompactPanel.svelte
- docker-compose.yml
- backend/api.py
- functions/ws/[[path]].ts
- agent_core/task_executor.py (agent status tracker entegrasyonu)

## TEST PLANI

- Tauri: cargo check --manifest-path rust_core/Cargo.toml, cargo check --manifest-path rust_core/src-tauri/Cargo.toml (CI'da webkit yoksa optional)
- Frontend: npm --prefix frontend run check (svelte-check), npm --prefix frontend run build
- Backend: python -m pytest tests/ -k "vault or agent or ws" (varsa)
- Docker: docker compose config (validate)
- Manuel: Tauri penceresi 1920x1080 açılıyor mu, iris mouse tracking mikro mu, nefes alıyor mu, AgentRack Ready/Active/Wait değişiyor mu, Vault kilitliyken /api/initiate 423 dönüyor mu, Aspasia komutu agent zincirine paslanıyor mu

## RİSKLER

- Tauri beforeDevCommand path hatası: --prefix ile çöz
- Redis yoksa fallback in-memory
- eye.jpg yüksek çözünürlük değilse upscaling + filter contrast
- Vault age file truncated bug: test ignored, ama yeni kodda save_to_disk sonrası flush kontrolü
