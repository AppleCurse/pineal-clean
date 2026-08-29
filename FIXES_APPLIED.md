# UYGULANAN DÜZELTMELER — Denetim Sonrası Fix Pass

**Tarih:** 2026-08-29 · **Kapsam:** `INDEPENDENT_FORENSIC_AUDIT.md` + `REPORT_CROSS_VALIDATION.md` çıktısının P0/P1/P2 listesi
**Doğrulama:** Her madde, uygulama sonrası `ruff` + tam `pytest` + canlı HTTP/WS koşusuyla yeniden test edilmiştir (aşağıda).

## P0 — Fiilen kırık / güvenlik

| # | Düzeltme | Dosya | Kanıt |
|---|---|---|---|
| 1 | **2 bayat test güncel sözleşmeye hizalandı**: `passive_voice_observation`+`linguistic` ve `visual_edge_density` beklentileri; test artık kodun [057] yüz-gerekli omuzROI sözleşmesini doğruluyor | `tests/unit/test_human_behavior.py` | pytest FAIL→PASS |
| 2 | **CI android job onarıldı**: `./gradlew` bağımlılığı kaldırıldı | `.github/workflows/ci.yml` | ✅ **Upstream (PR #31) kendi düzeltmesini merge etti** (setup-gradle + `gradle` CLI). Bu oturumun GitHub bağlantısı `workflows` iznine sahip olmadığından bizim varyant pushlanamamıştı; uzak main'deki düzeltme yürürlükte. |

<details>
<summary>ci.yml android job patch'i (elle uygulanacak)</summary>

```diff
       - name: Setup Gradle
-        uses: gradle/gradle-build-action@v2
+        uses: gradle/actions/setup-gradle@v3
+        with:
+          gradle-version: '8.7'
       - name: Make gradlew executable
-        run: chmod +x ./gradlew
+        # [FIX] Repoda gradlew wrapper yoktu -> "chmod +x ./gradlew" kırılıyordu.
+        # setup-gradle, Gradle CLI'yi PATH'e kurar; komutlar onunla çalışır.
       - name: Check & Build Android App
         run: |
-          ./gradlew lintDebug || true
-          ./gradlew assembleDebug
+          gradle lintDebug || true
+          gradle assembleDebug
```
</details>
| 3 | **Interpreter ana pipeline'dan izole edildi**: router artık interpreter'ı planlamaz; registry'ye yalnız `ENABLE_INTERPRETER=true` ile girer; endpoint 403 kapısı korunur. Kapı bypass'ı (interpreter'ın kendi LLM istemcisinin LIVE/spend kapılarını atlaması) yalnız açık opt-in ile mümkün olur | `cognitive_router.py`, `task_executor.py`, yeni registry testleri | 3 yeni sözleşme testi |
| 4 | **SERPAPI env adı onarıldı**: `SERPAPI_API_KEY` birincil, `SERPAPI_KEY` geriye uyumluluk ikincili | `backend/api.py` (get_room) | grep + runtime |
| 5 | **`OPENROUTER_TIER_2_MODEL` artık okunuyor**: `os.getenv(..., ling_3_flash)` | `llm_gateway.py` | env set/ unset testi |
| 6 | **Spend-cap default `.env.example` ile hizalandı**: env tanımsızken 1.0 → **0.0 (sınırsız)**; belgelenen "0=kapalı" sözleşmesi | `llm_gateway.py` | telemetry `llm_spend_cap_usd: 0.0` |
| 7 | **Beyan açığı kapatıldı**: `PyYAML` + `aiohttp` requirements'a eklendi (config_loader/osint doğrudan import ediyor); **`litellm` doğrudan pin kaldırıldı** (0 doğrudan import; open-interpreter transitif çeker) | `requirements.txt` | pip install + import-grami |

## P1 — Belge↔kod çelişkileri giderildi

| # | Düzeltme | Dosya |
|---|---|---|
| 8 | Model zincirleri kodla senkronize edildi (depth `solar-pro4 → glm-5.2 → deepseek-v4-pro` · dialogue `solar-pro4 → deepseek-v4-flash` · fast `ling-3.0-flash → deepseek-v4-flash`); uydurma `laguna/minimax/qwen3` satırları silindi | `README.md`, `RUNBOOK.md` |
| 9 | "Rust CI'da derlenmiyor" ↔ ci.yml çelişkisi: rust-core job'u olduğu dürüstçe yazıldı (ürün çalışma zamanına bağlı olmadığı vurgusu korunarak) | `README.md`, `ARCHITECTURE.md` |
| 10 | "223 test" sabiti kaldırıldı; dinamik komut korundu | `README.md`, `RUNBOOK.md` |
| 11 | X-hedefi davranış metni gerçek davranışa uyarlandı: "analiz BAŞLATILMAZ, yetki beklenir (`awaiting_authorization`)" | `RUNBOOK.md` |
| 12 | `USE_LOCAL_LLM` env ↔ Kasa önceliği belgelendi (kod da artık env'e saygııyor: vault'ta seçim yoksa env default devreye girer) | `backend/api.py`, `RUNBOOK.md`, `.env.example` |
| 13 | `live_llm_gate.py` docstring'i var olmayan workflow dosyasına referansı kaldırıldı | `live_llm_gate.py` |

## P2 — Temizlik

| # | Düzeltme | Dosya |
|---|---|---|
| 14 | Ölü kod: `AspasiaChief.preferred_model ("muse-spark-1.2-xhigh")` + `set_preferred_model` kaldırıldı (çağıranı yoktu) | `aspasia_chief.py` |
| 15 | DEAD paketler silindi: `agent_core/p2p/` (0 byte) ve `agent_core/db/reflection.sql` (0 referans) | git rm |
| 16 | **MODEL_PRICING katalogla hizalandı**: `z-ai/glm-5.2` 0.10/0.10 → **0.50/1.50**, `deepseek-v4-pro` 0.50/1.00 → **0.75/1.50** (2026-08-29 canlı OpenRouter katalog denetimi; spend cap artık maliyeti olduğundan düşük saymaz) | `llm_gateway.py` |


## NOT — Upstream örtüşmesi (PR #31)

Bu fix pass sırasında uzak `main`'in (PR #31, `fix-static-findings-3`) ikinci denetim
raporundaki bulguların bir bölümünü zaten merge ettiği görüldü (TIER_2 env, SERPAPI,
USE_LOCAL_LLM, spend-cap 0.0, litellm/PyYAML/aiohttp, test hizalama, muse-spark,
reflection.sql, router'da interpreter kapısı, android CI). Commit, yeni main üzerine
rebase edildi; çakışmalarda **daha tam/daha dürüst taraf** seçildi:

| Dosya | Seçim | Gerekçe |
|---|---|---|
| llm_gateway MODEL_PRICING | **Bizimki** (glm-5.2 0.50/1.50, ds-v4-pro 0.75/1.50) | upstream katalog MIN'ini aldı; spend cap amaçlı muhafazakâr (min-üstü) değer daha güvenli |
| cognitive_router | **Bizimki** (interpreter rotaya hiç girmez) | upstream env-true'da rotaya ekliyor → kapı bypass yolu açık kalıyor; bizimki daha sıkı |
| task_executor registry kapısı | **Bizimki** (upstream'de yok) | interpreter varsayılan registry'de yok |
| live_llm_gate docstring | **Bizimki** (referans kaldırıldı) | upstream ci.yml'ye işaret ediyor ama ci.yml'de böyle bir job YOK |
| test_human_behavior | upstream (eşdeğer) + bizim no_face düzeltmesi | aynı sözleşme |
| README/RUNBOOK | **Bizimki** (zincirlerin TAMAMı + 223 + rust-CI + X davranışı) | upstream'in zincir düzeltmesi `fast` zincirinde eksik kaldı; upstream'in playwright-ZORUNLU notları korundu |
| backend/api | **Bizimki** (or-fallback) | işlevsel olarak eşdeğer, boş-string env'de daha sağlam |

## Bilinçli YAPILMAYANLAR (ürün kararı)

- Frontend'e tasks/retention/telemetry-HTTP UI eklenmesi (§P2 ürün işi) — ayrı iş paketi.
- Gradle wrapper commitlenmesi — `setup-gradle` çözümü yeterli; wrapper tercih edilirse ayrı eklenir.
- Docker/Rust/Android/canlı-LLM çalıştırma doğrulaması — bu ortamda imkânsız (bkz. denetim raporları).

## Yeniden doğrulama sonuçları

```
ruff check .          = PASS
pytest -q             = 349 collected, tümü PASS (önceden: 347'de 2 FAIL)
frontend check+build  = PASS
uvicorn + WS e2e      = PASS (interpreter artık planned_agents'ta YOK)
telemetry             = llm_spend_cap_usd: 0.0 (hizalanmış default)
vault + local provider e2e = PASS (pipeline canlı sağlayıcıyla çalışıyor)
```
