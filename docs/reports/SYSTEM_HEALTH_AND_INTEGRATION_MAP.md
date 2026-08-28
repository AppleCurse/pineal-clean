# Pineal — Sistem Sağlığı ve Entegrasyon Haritası

**Durum tarihi:** 2026-08-25  
**Branch:** `arena/01a039cb-pineal-clean`  
**Amaç:** Sistemin neyi gerçekten çalıştırdığını, hangi bileşenin hangi girdiye bağlı olduğunu, hangi entegrasyonun canlı doğrulama gerektirdiğini ve hangi alanların hâlâ incelenmesi gerektiğini tek yerde göstermek.

> Bu belge README veya test sayısını gerçeklik kanıtı saymaz. `Yeşil` yalnızca kod yolu, sözleşme ve test kapsamı anlamına gelir; canlı provider doğruluğu için ayrıca live-provider run gerekir.

## 1. Kullanıcıdan Sonuca Çalışma Haritası

```text
Svelte UI
  ↓ HTTP / WebSocket
FastAPI backend/api.py
  ├─ vault / room / rate-limit / telemetry
  ├─ URL platform tespiti
  ├─ Instagram scrape veya X authorization isteği
  └─ PinealExecutor
       ├─ deterministic forensics
       ├─ 7-Pillar bundle
       ├─ CognitiveRouter
       ├─ specialist agents
       ├─ uncertainty + evidence chain
       ├─ CanonicalMemory
       └─ DecisionEngine
  ↓
TaskSnapshot / WebSocket events / Aspasia
```

### X özel akışı
```text
X URL
  ↓
Direct scraper unsupported
  ↓
awaiting_authorization (executor çalışmaz)
  ↓
POST /api/scraper/authorize-alternative {alternative: public_web_search, approved: true}
  ↓
_run_public_web_research: mevcut SearchEngine ile gerçek arama
  ↓
Subject matching (handle URL/içerikte geçmeli) + source attribution
  ↓
room['web_research'] + WS log; sonuç yoksa dürüst no_results/no_subject_match
```

**Not:** Alternatif akış PSİKOLOJİK PROFİL ÜRETMEZ: yalnızca kaynak
attribution'lı gerçek arama kayıtları döner (biyografi/gönderi uydurma
yasak). Sağlayıcı çökerse available=False; hedef handle ile eşleşmeyen
sonuçlar düşürülür. Frontend henüz bu sonucu tüketmiyor (uyumluluk kırılmadı).

## 2. Sağlık Sınıfları

| Etiket | Anlamı |
|---|---|
| **WIRED** | Production path’te çağrılıyor |
| **CONTRACTED** | Typed input/output ve failure semantiği var |
| **LIVE-UNVERIFIED** | Kod bağlı ama canlı provider/platform koşusu ayrıca doğrulanmadı |
| **EXPERIMENTAL** | API veya repo içinde var, ana kullanıcı akışının parçası değil |
| **PENDING DESIGN** | Gerçek ihtiyacı var; ekleme yapmadan önce sözleşme tasarımı gerekli |

## 3. Entegrasyon Haritası

| Katman | Bileşen | Durum | Girdi → çıktı | Sağlık notu |
|---|---|---|---|---|
| UI | `frontend/src/*` | WIRED | Form/WebSocket → API | Build doğrulanmış; production browser E2E ayrı |
| API | `backend/api.py` | WIRED | Request → room/task | X için authorization gate eklendi |
| Orchestrator | `task_executor.py` | WIRED | payload → TaskSnapshot | Evidence/uncertainty ve critical policy var |
| Routing | `cognitive_router.py` | CONTRACTED | readiness → RoutePlan | Empty profile route etmiyor |
| LLM | `llm_gateway.py` | WIRED | agent/task → structured output | Agent policy var; canlı model sağlık testi bekliyor |
| Search | `search_engine.py` | CONTRACTED | query → SearchOutcome | Timeout/auth/rate-limit/no-result ayrıldı |
| Memory | `canonical_memory.py` | CONTRACTED | evidence → JSON memory | Corrupt recovery + conflict marking var |
| 7-Pillar | `pillar_orchestrator.py` | CONTRACTED | profile → bundle | İç component failure artık maskelenmiyor |
| Aspasia | `aspasia_chief.py` | WIRED | telemetry → doğal dil açıklama | Sıcak/uygulanabilir üslup policy’si var |
| Rust core | `rust_core/` | EXPERIMENTAL | ayrı Rust path | Python runtime’a bağlı değil; build/run doğrulanmalı |

## 4. Agent Haritası

| Agent / servis | Ana görev | Execution sahipliği | Model / provider | Failure davranışı | Durum |
|---|---|---|---|---|---|
| `MirrorOfTruth` | Kullanıcı bağlamını structured reflection’a çevirir | Router | LLMGateway `query_json` | `confidence=0`, `data_confidence=False` | WIRED, LIVE-UNVERIFIED |
| `AutonomousVerifier` | Bio claim çıkarır, SearchOutcome ile web teyidi yapar | Router | fast chain + Tavily/SerpAPI/Exa/DDG | Kanıt/provider yok → `UNVERIFIED`, score/confidence 0 | CONTRACTED |
| `HumanBehaviorAnalyzer` | Metin/görsel observable sinyal çıkarır | Router | LLM + deterministic extraction | model-level contract: LLM yoksa interpretation_unavailable + data_confidence=False; gözlem yoksa LLM çağrılmaz | WIRED, CONTRACTED |
| `PassionMapper` | Kanıtlı ilgi/tutku alanları | Router | primary DeepSeek V4 Pro | LLM yok → explicit unavailable | WIRED, LIVE-UNVERIFIED |
| `FrictionDetector` | Sınır/hassasiyet evidence extraction | Router | primary Ling 3 Flash | LLM yok → explicit unavailable | WIRED, LIVE-UNVERIFIED |
| `CognitiveProfiler` | İletişim/bilişsel style | Router | primary Solar Pro 4 | LLM yok → explicit unavailable | WIRED, LIVE-UNVERIFIED |
| `ResonanceCalculator` | İki explicit vector için cosine similarity | Router | deterministic numpy | Vector yok → error; text/achilles türetimi yok | CONTRACTED |
| `PatternInterrupt` | Evidence-bound ilk mesaj taslağı | Deferred router agent | LLM `query_json` | Evidence yok → UNAVAILABLE | CONTRACTED |
| `ResonanceSynthesizer` | Ortak değer üzerinden iletişim köprüsü | Deferred router agent | specialist policy | LLM yok → explicit unavailable | WIRED, LIVE-UNVERIFIED |
| `AuthenticityAuditor` | Görsel/tutarlılık denetimi | Router, visual evidence varsa | LLMGateway | fallback semantics ayrıca live review ister | WIRED, REVIEW |
| `OSINTInvestigator` | Public provider OSINT footprint | Forensic stamp, tek çağrı | osint.industries | Typed provider error + measured coverage | CONTRACTED, LIVE-UNVERIFIED |
| `ShadowExecutor` | NLP/deterministic forensic bundle | Forensic stamp | internal + LLM subcalls | failure agent run’a yazılır | WIRED, REVIEW |
| `DepthAnalyst` | Evidence chain üzerinde quote-guardlı derinlik raporu | Post-profile phase | depth chain | hata loglanıp atlanıyor | WIRED, REVIEW |
| `VisionAnalyzer` | URL görsellerinde multimodal evidence | Pre-route | Gemini vision chain | download/model failure typed fallback | WIRED, LIVE-UNVERIFIED |
| `InterpreterAgent` | Experimental code execution | Experimental endpoint | interpreter | default disabled | EXPERIMENTAL |
| `ReflectionLoop` | Q-learning prototype (kendi reflection.db) | Hiçbiri | — | kimse import etmiyor | ORPHAN (silme yok; ürün kararı gerekli) |
| `AspasiaChief` | Telemetry/model/agent durumunu kullanıcı diline çevirir | Chat endpoint | LLMGateway | provider hata → dürüst connection mesajı | WIRED, LIVE-UNVERIFIED |

## 5. Specialist Model Policy

| Agent | Primary | Bounded fallback |
|---|---|---|
| CognitiveProfiler | `upstage/solar-pro4` | DeepSeek V4 Pro → GLM 5.2 |
| FrictionDetector | `inclusionai/ling-3.0-flash` | DeepSeek V4 Flash |
| PassionMapper | `deepseek/deepseek-v4-pro` | Solar Pro 4 → GLM 5.2 |
| ResonanceSynthesizer | `upstage/solar-pro4` | DeepSeek V4 Pro |
| VisionAnalyzer | `google/gemini-3.7-flash` | Şu an fallback yok; tasarım kararı gerekli |
| AutonomousVerifier | `deepseek/deepseek-v4-flash` | Ling 3 Flash |

**Durum:** Model/provider/attempt metadata artık evidence chain’e yazılıyor (llm_calls: kind, model, provider, attempts, duration_ms, token, error; cache hit → provider='cache'). UNAVAILABLE/REAL_LLM_CALL_NOT_EXECUTED denemeleri de loglanır.

## 6. Failure Semantics Haritası

| Olay | Doğru sonuç |
|---|---|
| Input yok | `SKIPPED_NO_INPUT` / route dışı |
| Vector yok | resonance hesaplanmaz |
| Web provider yok | `UNVERIFIED`, score 0 |
| Search timeout/auth/rate limit | typed SearchOutcome, empty result değil |
| LLM tüm zincirde yok | `data_confidence=False`, confidence 0 veya UNAVAILABLE |
| 7-pillar component hata | critical failure, evidence kaydı |
| X direct scraping unsupported | `awaiting_authorization`, executor çalışmaz |
| Alternatif kaynak yetkisi yok | alternatif provider çağrılmaz |
| Evidence çelişkisi | kayıtlar korunur, `CONTRADICTED` işaretlenir |

## 7. Sağlık Kontrolü — Şimdi Ne Kanıtlandı / Ne Kanıtlanmadı

### Kod ve regression seviyesinde kanıtlanan

```text
- Sahte resonance vector fallback engeli
- Empty profile routing engeli
- OSINT’in çift çalışması engeli
- Intervention safety bypass engeli
- 7-pillar exception masking engeli
- ALF bounded retry
- CanonicalMemory corrupt recovery
- CanonicalMemory conflict preservation
- PatternInterrupt evidence gate
- Search failure semantics
```

### Canlı ortamda ayrıca doğrulanması gereken

```text
- Her OpenRouter specialist model zinciri
- Tavily / SerpAPI / Exa gerçek auth, rate-limit ve timeout path’i
- osint.industries gerçek response schema’sı
- Instagram Playwright canlı/profile/private account yolu
- Vision model gerçek image URL ve multimodal schema yolu
- X alternatif authorization sonrası gerçek public-web retrieval tasarımı
- Rust build + test + Python runtime bridge
```

## 8. Şu An Yeni Kod Yazmadan Önce İncelenecek Başlıklar

1. ~~X alternatif retrieval sözleşmesi~~ → `a002b20`: source attribution + subject matching + evidence formatı uygulandı (sahte profil üretilmiyor; frontend tüketimi ayrı iş).
2. ~~LLM evidence metadata~~ → `a002b20`: model/provider/attempt/token/error evidence kaydında (`llm_calls`).
3. ~~HumanBehavior sınırı~~ → `a002b20`: model seviyesinde netleştirildi (data_confidence/fallback_reason + interpretation_unavailable).
4. **Vision policy:** Gemini tek model olduğu için gerçek fallback stratejisi veya açık UNAVAILABLE policy kararlaştırılmalı.
5. **Rust karar kaydı:** Rust core ürün runtime’ına alınacak mı, ayrı deneysel modül mü kalacak? ADR gerekli.

## 9. Aspasia Sağlık Rolü

Aspasia yeni feature üretmez. Görevi bu haritayı kullanıcı diline çevirmektir:

```text
Teknik state:
  SearchOutcome(status=UNAVAILABLE, error=RATE_LIMITED)

Aspasia açıklaması:
  “Arama sağlayıcısı şu an istek sınırına takıldı. Sonuç yok demiyorum;
  arama yapamadık. İstersen biraz sonra tekrar deneyebilir veya izin verirsen
  başka bir public kaynakla devam edebiliriz.”
```

Bu, kullanıcıyı telemetry, provider adı ve model jargonunu ayrıca tercüme etmek zorunda bırakmayan hedef davranıştır.
