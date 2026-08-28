# 22 madde × mevcut HEAD yeniden sorgulama

**HEAD:** `9df180a` (`feat: add real LLM cost tracker based on token usage`)  
**Branch:** `arena/01a03956-pineal-clean`  
**Not:** Önceki oturumdaki `c743ec1` / `8b38919` bu checkout’ta yok. Karşılaştırma **bu** çalışma ağacına karşı.

---

## Karne

| # | Madde | Durum |
|---|---|---|
| 1 | Vision hardcode | ✅ env-driven (`OPENROUTER_VISION_MODEL`, `google/gemini-3.7-flash`) |
| 2 | Vision sahte fallback | ✅ `aesthetic_style="UNAVAILABLE"`, `data_confidence=False` |
| 3 | OSINT / PassionMapper sahte skor | ✅ UNAVAILABLE / `data_confidence=False` yolları var |
| 4 | Claude / DeepSeek-chat / Llama zincirleri | ✅ ekonomik filo + `OPENROUTER_CHAIN_*` |
| 5 | Friction / cognitive / authenticity / depth sahte skor | ✅ P1.1 UNAVAILABLE sözleşmesi + testler |
| 6 | Test sayısı doküman | 🟡 README/RUNBOOK **218** yazıyor; `def test_` sayısı **223** |
| 7 | HEAD için CI kanıtı | 🟡 workflow var; bu oturumda yeni CI koşusu yok |
| 8 | `data_confidence=False` → suspicious/NO_EVIDENCE | 🟡 davranış: confidence düşer → eşik halt; etiket hâlâ `is_suspicious=False`, reason=`Fallback modu devrede.` |
| 9 | Rust / Tauri dürüstlük | 🟡 doküman “bağlı değil / CI’da derlenmiyor”; `rust_core/Cargo.toml:44` hâlâ `tauri = "2"` |
| 10 | Interpreter `auto_run` | 🟡 `auto_run=False` zorlanıyor; `/api/experimental/interpreter/execute` açık |
| 11 | PillarOrchestrator executor’a bağlı değil | ❌ **inceleme yanlıştı** — `task_executor.py:227-278` bağlı ve çalışıyor |
| 12 | DecisionEngine 7-Pillar’ı karara almıyor | 🔴 `make_decision` yalnız `failed/halted` ajanlara bakıyor; pillar çıktısı karar ağacında yok |
| 13 | 7-Pillar sıralaması (ajanlardan önce) | 🔴 pillar ajan rotasından **önce** koşuyor |
| 14 | ALF recursion | 🔴 `stealth_fetch` hata/non-200’de `profile_id+1` ile sınırsız özyineleme |
| 15 | ReflectionLoop Q-update yok | 🔴 `log_action` yazar; `decision_weights` güncellenmez |
| 16 | dp2p noise opsiyonel | 🔴 `import noise` yoksa protokol `None` |
| 17 | PIL spaCy bağımlılığı | 🔴 model yoksa stub string |
| 18 | Gerçek Model Router (capability registry) | 🔴 yok — `CognitiveRouter` kural tabanlı sabit liste |
| 19 | P0.2 senkron (local vs GitHub) | ✅ bu checkout’ta local = `origin/arena/01a03956-pineal-clean` = `9df180a`, tree temiz |
| 20 | LLMGateway vision | ✅ görsel istekte env vision modeli |
| 21 | Uncertainty halt (confidence 0.0) | 🟡 P0/P1 ajanları 0.0 verebilir → `min_llm_confidence` halt; semantik bayrak eksik |
| 22 | Phase-7 dörtlüsü ürün akışında | 🔴 ALF / Reflection / dp2p / PIL executor rotasında yok |

---

## Kanıt notları

### İncelemede yanlış olan (madde 11)
`PinealExecutor.execute_task` içinde 7-pillar bloğu ajan döngüsünden önce:

```227:232:agent_core/task_executor.py
        pillar_start = datetime.now(timezone.utc)
        self._log("INFO", f"[{task_id}] 7-PILLAR analizi başlatılıyor...")
        try:
            from agent_core.engines.pillar_orchestrator import PillarOrchestrator
            pillar_fields = await PillarOrchestrator().run(input_data)
```

Bağlantı sorunu değil. Asıl açıklar: **sıralama** (ajan kanıtı olmadan pillar), **DecisionEngine’in pillar’ı yok sayması**, pillar’ın LLM’siz/deterministik kalması.

### DecisionEngine (madde 12)
```17:36:agent_core/services/decision_engine.py
    def make_decision(self, agent_runs: Dict[str, Any]) -> PipelineStatus:
        failed_runs = {name: run for name, run in agent_runs.items() if run.status in ("failed", "halted")}
        if not failed_runs:
            return PipelineStatus.COMPLETED
        ...
```
`frequency_map` / `key_matrix` / pillar güveni okunmuyor.

### Uncertainty semantik boşluk (8, 21)
```155:163:agent_core/services/uncertainty_engine.py
        if not data_conf_flag:
            return UncertaintyReport(
                is_suspicious=False, 
                confidence=combined_confidence, 
                reason="Fallback modu devrede.",
```

### Model Router yok (18)
`CognitiveRouter.analyze` yalnızca `has_target` / `has_user` / `visual_evidence` bayraklarıyla sabit ajan listesi üretir. Capability, maliyet, latency, model-ajan eşlemesi yok.

### Phase-7
- ALF: `return await self.stealth_fetch(url, profile_id + 1)` — taban durum yok.
- ReflectionLoop: Q-tablosu okunur, `log_action` Q yazmaz.
- DP2P: `noise` import opsiyonel.
- PIL: spaCy yüklenemezse şablon cümle.

---

## Önerilen sıra

1. **Model Router P0** — ajan/model capability registry (maliyet, vision, JSON, fallback).
2. DecisionEngine’e pillar + `data_confidence` semantiği.
3. ALF özyineleme tavanı.
4. ReflectionLoop Q-update veya “öğrenmiyor” dokümanı.
5. `Cargo.toml` tauri satırını `src-tauri` ile hizala veya optional feature.

**Onay beklenen:** madde 18 (Model Router).
