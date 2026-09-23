# RAPOR KARŞILAŞTIRMA VE ÇAPRAZ DOĞRULAMA
## Independent Forensic Audit (Rapor A) ↔ Adli Yazılım İnceleme Raporu (Rapor B)

**Tarih:** 2026-08-29 · **Hedef:** `AppleCurse/pineal-clean` @ `fda9940`
**Yöntem:** Rapor B'deki Rapor A'da bulunmayan **her iddia tek tek yeniden kanıtlandı** (kod + çalışma zamanı + canlı katalog). Hiçbir tarafın raporu kabul kuralına göre kanıtsız benimsenmedi.

---

## 1. GENEL KARAR

| Soru | Cevap |
|---|---|
| Rapor B güvenilir mi? | **Evet, büyük ölçüde.** Test ettğim 9 benzersiz iddiasından 7'si birebir DOĞRULANDI, 2'si kısmen/nüanslı (bkz. §4). |
| İki rapor çelişiyor mu? | **Temel çelişki yok.** Aynı test sonuçları (347/345/2), aynı config hataları, aynı çelişkiler. Farklar **kapsam** farkı: B'nin bulduğu 6 gerçek kalem A'da eksikti; A'nın bulduğu ~8 kalem B'de yoktu. |
| Birleşik gerçeklik özeti | §6'daki birleşik tablo geçerli: **Orkestrasyon iskeleti çalışıyor; canlı LLM/kazıma vaatleri anahtarsız ortamda doğrulanamadı; 2 test + CI-yapılandırma hataları düzeltilmeli.** |

---

## 2. TAM UZLAŞMA (her iki raporda da, bağımsız kanıtla)

| # | Bulgu | A kanıtı | B kanıtı | Durum |
|---|---|---|---|---|
| 1 | 347 test toplandı; **345 PASS, 2 FAIL** | pytest koşusu | pytest koşusu | ✅ AYNI SONUÇ |
| 2 | Kırık testler: `test_linguistic_forensics` (contradiction+passive_voice bekler → kod `passive_voice_observation`/`linguistic` üretir), `test_analyze_visual_micro` (`tension` bekler → kod `visual_edge_density` üretir) | human_behavior.py:325,382 | aynı satırlar | ✅ Kök neden AYNI |
| 3 | `OPENROUTER_TIER_2_MODEL` env'i kod okumuyor | llm_gateway.py:36 | aynı | ✅ |
| 4 | Spend cap default 1.0$ ↔ .env.example "0=sınırsız" | telemetry çıktısı | aynı | ✅ |
| 5 | "Rust CI'da derlenmiyor" ↔ ci.yml `rust-core` job'u | ci.yml | aynı | ✅ CONTRADICTED |
| 6 | `litellm` doğrudan kullanılmıyor | 0 import | aynı | ✅ |
| 7 | Rate limit: 6. initiate → 429 | runtime | runtime | ✅ |
| 8 | Anahtarsız → `halted_evidence`; Aspasia fallback; interpreter 403; X → `awaiting_authorization`; memory json; Android bağımsız Gemini istemcisi | runtime | runtime/kod | ✅ |
| 9 | Test sayısı dokümanlarda 223 ↔ gerçek 347 | collect-only | collect-only | ✅ |
| 10 | Docker/cargo/Chromium/canlı-LLM bu ortamda NOT_EXECUTED | — | — | ✅ aynı sınır |

---

## 3. RAPOR B'DE DOĞRU OLUP RAPOR A'DA EKSİK OLANLAR — yeniden kanıtlandı, A kabul ediyor

| # | Rapor B bulgusu | A'nın bağımsız doğrulaması | Hüküm |
|---|---|---|---|
| 1 | **SERPAPI env uyumsuzluğu**: `api.py:199` → `SERPAPI_KEY`; `search_engine.py:31` + `.env.example` → `SERPAPI_API_KEY` | grep ile iki isim de teyit edildi | ✅ **GERÇEK HATA** — ancak etki nüansı: `SearchEngine()` constructor'ı env'den `SERPAPI_API_KEY`'i kendisi okur, yani .env yolu çalışır; bozulan kombinasyon, vault/telemetri bayrağının bu env ile senkronlanmaması. Rapor B'nin "kaçırabilir" ihtiyatlı ifadesi isabetli; **Ciddiyet: MEDIUM** |
| 2 | **PyYAML beyan edilmemiş**: `config_loader.py:3 import yaml`, requirements'ta yok | PyYAML 6.0.3 kurulunun gerektiren zinciri: **open-interpreter** (Requires listesinde pyyaml). Yani yalnızca open-interpreter sayesinde çalışıyor | ✅ **SAĞLAM RİSK** — open-interpreter kaldırılırsa/yalıtılırsa pipeline açılışta çöker (`yaml` import hatası). B'nin en değerli yakalamalarından |
| 3 | **aiohttp beyan edilmemiş**: `osint_investigator.py:3` | aiohttp 3.14.3 transitif kurulu; requirements'ta yok | ✅ Aynı sınıf risk |
| 4 | **android/gradlew repoda yok** → CI `chmod +x ./gradlew` başarısız → **android job bu revizyonda kırık** | `ls android/gradlew` → "No such file"; `gradle/` içinde yalnız `libs.versions.toml` (wrapper yok) | ✅ **GERÇEK CI HATASI** — A'nın raporunda Android için yalnız "NOT EXECUTED" vardı; B'nin "job kırık" tespiti daha keskin ve doğru |
| 5 | **`agent_core/p2p/` boş (0 byte) + `db/reflection.sql` hiç referanssız** | `wc -c` → 0; grep → 0 Python referansı | ✅ DEAD CODE teyit |
| 6 | **Frontend yalnız 4 uç çağırıyor** (initiate, vault, aspasia/chat, executor/intervene) + WS | `apiFetch` envanteri: `/api/initiate`, `/api/vault`, `'/api/aspasia/chat' : '/api/executor/intervene'` — tasks/override/telemetry-HTTP/authorize-alternative/experimental: 0 çağrı | ✅ A kısmen raporlamıştı (yalnız experimental=0); B'nin listesi tam ve doğru |
| 7 | DarkTriad TR-marker heuristiği zayıf; EN metinde 0 | **Çalışma zamanı:** açıkça manipülatif İngilizce metin → tümü 0.0; önceki Türkçe test de 0.0 verdi | ✅ Runtime ile teyit — "ML değil dar heuristik" nitelemesi doğru |
| 8 | Ortam sürümleri (fastapi 0.115.2, openai 3.6.0, playwright 1.62.0, numpy 2.4.6) | pip show ile birebir aynı | ✅ |

---

## 4. RAPOR B'DE DÜZELTİLEN / NÜANSLANAN IDDIALAR

| # | B iddiası | Bağımsız doğrulama sonucu | Hüküm |
|---|---|---|---|
| 1 | "Hindsight açılamaz — **[PROVEN ModuleNotFoundError]**" | `PINEAL_MEMORY_ENGINE=hindsight` ile `build_memory_from_env()` → **HindsightMemory örneği oluştu**, `merge_evidence` **başarılı**. `sentence_transformers` importu lazy (hindsight_memory.py:36→132); hata ancak embedding/gömme anında çıkar | ⚠️ **AŞIRI GENEL** — doğru hali: "kurulum ve kanıt yazma ML'siz çalışır; semantik arama kullanılırsa hata verir" |
| 2 | Interpreter ana rotada — **"CRITICAL risk"** (arbitrary code execution yüzeyi) | Kanıt: `cognitive_router.py:42` (has_user → route), interpreter_agent.py'de LIVE/spend kontrolü **0 eşleşme**. ANCAK: `auto_run=False` zorlanmış (kod üretir, kendi başına çalıştırmaz), HTTP ucu 403. **Rapor A'nın katkısıyla asıl keskin bulgu:** InterpreterAgent **kendi LLM istemcisiyle** çağrı yapar → `LIVE_LLM_E2E` kapısını, spend-cap'i ve pricing-guard'ı **atlar** (api.py:191 env anahtarını `unlock_live`siz kurar ama interpreter'a düz `api_key` geçilir) | ⚠️ **Ciddiyet MEDIUM-HIGH'a çekilmeli** (RCE değil; kapı-bütünlüğü/maliyet bypass'ı + gereksiz saldırı yüzeyi). Öneri (router'dan çıkarmak) iki raporda ortak |
| 3 | Branch adı `arena/01a04b6e-…` | Gerçek: `arena/01a04b6f-pineal-clean` (git) | ℹ️ Küçük yazım hatası; aynı commit `fda9940` |
| 4 | "Model registry: katalogda isim var ≠ erişilebilir; **canlı doğrulama yok**" | Rapor A canlı OpenRouter API'siyle **6/6 slug'ı + fiyat + uptime'ı doğruladı** (2026-08-29). `openai/gpt-5.6-sol-pro` (B'nin rapor etmediği `live_llm_gate.py` judge modeli) de canlı katalogda VAR | ℹ️ Bu madde artık B için de geçerli değil — **VERIFIED** |
| 5 | §5.7 "Vault fake key → gateway:true" | Tutarsız değil; ancak canlı çağrı olmadığından "gateway:true" yalnız anahtarın **kayıt** edildiğini gösterir, çalıştığını değil. İki rapor da bunu ayrıca vurgulamalıydı | ℹ️ Nüans |

---

## 5. RAPOR A'DA OLUP RAPOR B'DE EKSİK OLANLAR (A→B katkısı)

1. **Canlı OpenRouter katalog doğrulaması:** 6/6 model slug + 4/6 fiyat birebir; **`z-ai/glm-5.2` (0.10/0.10) ve `deepseek-v4-pro` (0.50/1.00) fiyat kayıtları katalog minimumlarının altında → spend cap gerçek maliyetin altında sayar** (B'de yok).
2. **USE_LOCAL_LLM env-clobber'ı:** `api.py get_room` `use_local`'ı vault'la ezerek env'i yok sayıyor — **çalışma zamanında ölçüldü** (env true → room gateway False). .env.example/RUNBOOK ile çelişen dördüncü config yalanı (B yalnız TIER_2/SERPAPI/spend-cap'i yakaladı).
3. **README/RUNBOOK model zinciri uydurması:** `laguna-s-2.1`, `minimax-m2.7`, `qwen3-235b-a22b-2507` kodda **0 geçiş**; gerçek CHAINS tamamen farklı (B'de yok).
4. **RUNBOOK X-hedefi çelişkisi:** "analiz boş hedefle sürer" ↔ gerçek davranış "analiz başlamaz, yetki bekler" (runtime kanıtlı; B davranışı doğru tarif etti ama çelişkiyi işaretlemedi).
5. **Ölü kod:** `AspasiaChief.preferred_model="muse-spark-1.2-xhigh"` + `set_preferred_model()` — çağıran yok (B'de yok).
6. **DELETE path-traversal canary testi:** `..%2F` ile canlı deneme → **405** (multi-segment eşleşmez), canary silinmedi; savunma derinliği önerisi (explicit regex whitelist) (B'de test yok).
7. **Tam e2e canlı-sağlayıcı koşusu:** Yerel OpenAI-uyumlu sağlayıcıyla Kasa→görev→**gerçek HTTP provider çağrısı**→3-model zincir failover (log'lu)→provenance damgaları→`partially_completed`. İki rapordan yalnız A'da var; "pipeline'ın canlı yolu çalışıyor" iddiasının en güçlü kanıtı bu.
8. Halüsinasyon kapısının **jenerik-içerik ret** davranışının runtime kanıtı (stub koşusunda 7 ajanın dürüstçe halt etmesi).

---

## 6. İKİ RAPORDAN BİRLEŞİK, DÜZELTİLMİŞ BULGU SETİ

### P0 — Bu revizyonda fiilen kırık / güvenlik
1. `tests/unit/test_human_behavior.py` 2 bayat assertion → **CI backend job kırmızı** [iki rapor + koşu]
2. **CI android job kırık:** repo'da `gradlew` yok [B + doğrulama]
3. **Interpreter rotası + kapı bypass'ı:** router'dan çıkar veya `ENABLE_INTERPRETER` kapısına bağla; open-interpreter'ın kendi LLM yolu LIVE/spend kapılarını atlıyor [B + A nüansı]
4. **SERPAPI env adı uyumsuzluğu** [B + doğrulama]
5. `OPENROUTER_TIER_2_MODEL` okunmuyor; spend-cap default 1.0 ↔ belge 0 [iki rapor]
6. **PyYAML + aiohttp requirements'a eklenmeli** (open-interpreter çıkarılırsa PyYAML kritik) [B + doğrulama]

### P1 — Belge↔kod çelişkileri (birleşik liste)
7. README/RUNBOOK model zincirleri uydurma [A]; "rust CI" ifadesi [iki rapor]; 223 test sayısı [iki rapor]; USE_LOCAL_LLM .env yolu API'de çalışmıyor [A]; X-hedefi davranış metni [A]; `.env.example` spend-cap notu [iki rapor]
8. `live_llm_gate.py` docstring'i `.github/workflows/live_llm_gate.yml`'e referans veriyor — **dosya yok** (yalnız ci.yml var). *Yeni mikro bulgu, iki raporda da yoktu.*

### P2 — Temizlik/ürün
9. litellm'i çıkar (veya gerçekten kullan); `p2p/` + `reflection.sql` sil; `muse-spark` ölü alanını sil; DarkTriad marker setini genişlet/dokümante et; frontend'e tasks/retention + telemetry HTTP görünümü ekle; MODEL_PRICING'i canlı katalogla güncelle.

---

## 7. SKOR VE SONUÇ UZLAŞMASI

- Rapor B'nin **62/100** skoru öznel ama metodolojisi açık; A skor vermedi. İki raporun nitel hükümleri **aynıdır**: *"Orkestrasyon iskeleti (API + UI + executor + bellek + güvenlik kapıları) çalışır durumda; vaat edilen canlı 360° LLM/kazıma/vision ürünü harici anahtar+binary olmadan doğrulanamadı; sistem bunu dürüstçe gizlemiyor, duruyor."*
- A'nın katkısı bu hükmün **canlı-sağlayıcı zinciriyle** sınanmış olması (yerel provider üzerinden tam koşu) ve harici katalog doğrulamasıdır; B'nin katkısı **bağımlılık beyanı boşlukları, gradlew/CI kırığı ve SERPAPI env hatası**dır.
- Birleşik düzeltilmiş tabloyla her iki raporun da "critical blocker" listesi §6 P0 ile değiştirilmelidir.

**Uzlaşılmış tek cümle:** Bu depo dürüst-duraklamalı, sağlam sertleştirilmiş bir **orkestrasyon iskeletidir**; iki bağımsız denetim de çekirdeğin çalıştığını kanıtlar, canlı zekâ vaadinin ise anahtar/binary olmadan sertifikalanamayacağını ve 2 test + 1 CI job + 3 config yalanının (TIER_2, SERPAPI, spend-cap) düzeltilmesi gerektiğini gösterir.
