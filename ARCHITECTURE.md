# MİMARİ (koddan doğrulanmış çalışma zamanı grafiği)

> Bu belge röntgen (adli analiz) sonrası gerçek mimariyi anlatır — README iddiaları değil.

## Bileşen haritası

| Katman | Konum | Sorumluluk |
|---|---|---|
| UI | `frontend/` (Svelte 5 + Vite) | Vault, görev başlatma, Aspasia sohbeti, agent deck, 360° panel |
| API | `backend/api.py` (FastAPI) | Oda yönetimi, WebSocket, scraping orkestrasyonu, auth/limit |
| Orchestrator | `agent_core/task_executor.py` | Görev durum makinesi + ajan zinciri + kanıt biriktirme |
| Router | `agent_core/services/cognitive_router.py` | Girdiye göre ajan rotası (kural tabanlı, LLM'siz) |
| Ajanlar | `agent_core/agents/*` | 10 kayıtlı ajan (8'i LLM'li; `resonance_calc` saf numpy) |
| LLM | `agent_core/services/llm_gateway.py` | OpenRouter/Ollama; tier'lar, retry, circuit breaker, JSON tamiri, vision |
| Bellek | `agent_core/services/canonical_memory.py` | Görev başına `memory/<task_id>.json` (bilinçli: DB yok) |
| Telemetri | `agent_core/schemas/telemetry.py` + api.py kuyruğu | Pydantic event şemaları → FIFO → WebSocket |
| Aspasia | `agent_core/aspasia/aspasia_chief.py` | Gözlemci persona; telemetri özeti + sohbet (karar verici DEĞİL) |
| Scraper | `scraper.py` (X), `agent_core/scraper/instagram_ghost.py` (IG) | Playwright+stealth; Pydantic V2 şema; kanıt yoksa HALT |

## Çalışma zamanı zincirleri

### 1) Analiz akışı
```
UI (apiFetch) ──POST /api/initiate──► FastAPI run_mission
   └─ (url varsa) Playwright+stealth scrape ─► target_profile
PinealExecutor.execute_task [processing]
   ├─ CognitiveRouter.analyze → rota
   ├─ her ajan: execute → UncertaintyEngine (güven<0.6 → halted_evidence)
   │            resonance<0.70 → halted_frequency
   ├─ kanıt → evidence_chain + CanonicalMemory (json)
   └─ 360° HolisticProfile (passions+frictions+cognitive+bridge)
Telemetry: _emit → asyncio.Queue (FIFO) → _room_sender → WebSocket
UI: snapshot_update / event / result → paneller
```

### 2) Durum makinesi (Python — Rust yok, 4C kararı)
`initialized → processing → completed | failed | halted_evidence | halted_frequency`

### 3) Aspasia akışı
```
UI ──POST /api/aspasia/chat──► room.aspasia.chat(msg, room, model?, image?)
   ├─ build_telemetry_summary(room.active_tasks)  ← canlı snapshot'lar
   └─ LLMGateway.query(system=ASPASIA_PERSONA, images?) ─► yanıt / zarif fallback
```

## Alınan mimari kararlar (ADR özeti)
| Karar | Neden |
|---|---|
| **4C: Rust/Tauri kapatıldı** | 0 satır Rust vardı; ölü köprü ve karşılıksız invoke silindi; web yeterli |
| **SQLite reddedildi** | Tek kullanıcılı istasyon; FIFO kuyruk yarışmayı çözdü, disk I/O gereksizdi |
| **LIVE_LLM_E2E kapısı** | Anahtarsız/halüsinasyonlu koşular kodda reddedilir (bilinçli tasarım) |
| **D5: deneysel API'ler** | shadow/chat/interpreter → `/api/experimental/*` (UI çağrıcısı yok) |
| **Manipülasyon motorları silindi** | 8 modül (~840 satır) hiçbir execution path'ine bağlı değildi; ürün kimliği "sahici köprü" |

## Güvenlik yüzeyi
`PINEAL_TOKEN` (X-API-Key / ?token=) · CORS localhost kümesi · rate limit (initiate 5/dk, aspasia 20/dk) · `{error:{code,message}}` · sırlar yalnız gateway belleğinde (log yasağı testli) · retention: `DELETE /api/tasks/{id}`
