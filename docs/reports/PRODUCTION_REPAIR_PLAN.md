# PINEAL-CLEAN — GERÇEK DÜZELTME PLANI

> Amaç: Projeyi parça parça “çalışıyor” ilan etmek yerine, bütün stack'i tek bir doğrulanabilir release gate altında üretime hazır hale getirmek.
>
> Hedef branch: `hardening/production-proof`
> Durum: UYGULAMA PLANI — production sertifikası değildir.

## 0. Değişmez kurallar

1. `main` doğrudan değiştirilmez; bütün düzeltmeler hardening dalında ilerler.
2. Bir test/build çıktısı yalnızca kendi kapsamını kanıtlar.
3. Unit test PASS, canlı entegrasyon PASS sayılmaz.
4. Kanıtı olmayan özellik “aktif/çalışıyor” diye raporlanmaz.
5. Kritik CI adımları fail-closed olur; `|| true`, sessiz exception ve kritik `continue-on-error` yasaktır.
6. Her P0/P1 düzeltmesinin kalıcı regression testi olur.
7. Her LLM çıktısı çağrıya özgü provenance taşır; global “son çağrı” bilgisi kanıt olarak kullanılamaz.
8. Bozuk memory ile boş memory aynı durum değildir.

---

# FAZ 1 — RELEASE BASELINE VE CI KİLİDİ

### Hedef
Repository'nin hangi committen üretime aday olduğu ve CI'nin gerçekten hangi kapıları zorunlu tuttuğu kesinleştirilecek.

### İşler
- [ ] `hardening/production-proof` temiz baseline olarak kaydedilecek.
- [ ] Python: lint + test + coverage kapısı.
- [ ] Frontend: type/check + build kapısı.
- [ ] Rust: `cargo check` + `cargo test`.
- [ ] Android: canonical JDK/Gradle/AGP/Kotlin/KSP kombinasyonu belirlenecek; `gradlew` yoksa CI buna göre düzenlenecek.
- [ ] Android: lint + unit test + assemble.
- [ ] Smoke test zorunlu kapı yapılacak.
- [ ] Kritik adımlarda hata yutma kaldırılacak.

### Kabul kriteri
Tek CI run'ında backend + frontend + Rust + Android + smoke kapılarının tamamı PASS.

---

# FAZ 2 — ANDROID GERÇEK DERLEME ONARIMI

### Hedef
Gemini'nin yerel “build başarılı” iddiası ile GitHub repository/CI gerçeğini tek kaynağa indirmek.

### İncelenecek dosyalar
- `app/build.gradle.kts`
- `PinealAnalyzerEngine.kt`
- `PinealAnalyzerEngineTest.kt`
- `ForensicReconEngine.kt`
- `PinealViewModel.kt`
- `HolisticProfileCard.kt`
- `ReconInputCard.kt`

### İşler
- [ ] Gemini'nin bildirdiği değişikliklerin repository diff'i doğrulanacak.
- [ ] Duplicate import / eksik test parametresi gibi düşük riskli düzeltmeler alınacak.
- [ ] Kotlin compile hataları gerçek CI çıktısından tek tek kapatılacak.
- [ ] JDK/Gradle/AGP/Kotlin uyumu tek canonical yapılandırmaya sabitlenecek.
- [ ] `lintDebug` PASS.
- [ ] `testDebugUnitTest` PASS.
- [ ] `assembleDebug` PASS.

### Kabul kriteri
Android build aynı repository commitinden temiz CI runner'da yeniden üretilebilir.

---

# FAZ 3 — LLM PROVENANCE'IN KESİNLEŞTİRİLMESİ (P0)

### Mevcut risk
`agent_core/task_executor.py` içinde provenance üretimi `LLMGateway.last_call_meta` bilgisine dayanıyor. Paralel çağrılarda global son çağrı bilgisi başka bir ajanın çağrısıyla karışabilir.

### Hedef sözleşme
Her LLM çağrısı:
- `call_id`
- `task_id`
- `agent_id`
- `model`
- `provider`
- `attempt`
- `cache_hit`
- `prompt_tokens`
- `completion_tokens`
- `cost_usd`
- `started_at`
- `finished_at`
- `error`
alanlarını taşır.

### İşler
- [ ] `agent_core/services/llm_gateway.py`: call_id üretimi.
- [ ] `query()` ve retry zincirinde call record korunacak.
- [ ] `task_executor.py`: ajan çalışmasının başında/sonunda call-log slice yerine call_id ilişkisi kullanılacak.
- [ ] `_provenance_for()` global `last_call_meta` bağımlılığından çıkarılacak.
- [ ] `EvidenceRecord` ilgili call_id'yi taşıyacak.
- [ ] Parallel provenance regression testi eklenecek.

### Kabul kriteri
Aynı anda iki ajan iki farklı model çağırdığında her evidence kaydı doğru model/provider/call_id ile eşleşir.

---

# FAZ 4 — CONCURRENT COST / SPEND CAP (P0)

### Mevcut risk
`spend_usd` ve `total_cost` instance state'i çağrılar arasında paylaşılır. Budget kontrolü ile harcama muhasebesi yarış koşuluna açık olmamalıdır.

### İşler
- [ ] Budget reservation mekanizması tanımlanacak.
- [ ] Reservation + approval atomik sınırlandırılacak.
- [ ] Başarısız/retry/cancel durumunda reservation serbest bırakılacak veya doğru muhasebeleştirilecek.
- [ ] Cache hit için maliyet sıfır/önceden hesaplanmış ise açık sözleşme uygulanacak.
- [ ] Fiyatı bilinmeyen model production'da varsayılan olarak reddedilecek.
- [ ] 10/50/100 paralel çağrı regression testleri.

### Kabul kriteri
Concurrent yük altında `OPENROUTER_MAX_SPEND_USD` aşılmaz; reddedilen çağrılar açık provenance + telemetry kaydı bırakır.

---

# FAZ 5 — CANONICAL MEMORY CORRUPTION SEMANTICS (P0)

### Hedef
Bozuk dosyanın `{}` ile “boş memory” gibi görünmesini engellemek.

### İşler
- [ ] Corrupt JSON → `MEMORY_CORRUPTED` durumu.
- [ ] Bozuk kaynak korunacak; sessiz overwrite yok.
- [ ] Read path corrupt durumda normal analiz akışını sürdürmemeli veya açık degraded mode'a geçmeli.
- [ ] Empty memory ile corrupt memory için ayrı telemetry/event.
- [ ] Recovery prosedürü tanımlanacak.
- [ ] Corrupt JSON regression testi.

### Kabul kriteri
Bozuk memory hiçbir koşulda “memory yok” şeklinde sessizce yorumlanmaz.

---

# FAZ 6 — FALLBACK VE HATA SINIFLANDIRMASI (P1)

### Hedef
Gerçek runtime hatalarının optional dependency eksikliği gibi maskelenmesini engellemek.

### İşler
- [ ] Geniş `except Exception` import fallback'leri daraltılacak.
- [ ] Beklenen `ModuleNotFoundError` ile dependency içi runtime exception ayrılacak.
- [ ] Startup health check zorunlu dependency hatasını açık kodla raporlayacak.
- [ ] Experimental modüller kapalıyken ana pipeline davranışı değişmeyecek.

### Kabul kriteri
Zorunlu bir modül bozuk olduğunda sistem sessiz fallback yapmaz; makine-okunur failure üretir.

---

# FAZ 7 — TELEMETRY + TASK LIFECYCLE (P1)

### İşler
- [ ] Event schema: `task_id`, `run_id`, `sequence`, `event_type`, timestamp.
- [ ] Sequence monotonicity testi.
- [ ] Duplicate event testi.
- [ ] Terminal state sonrası mutation testi.
- [ ] `halt/cancel` idempotency testi.
- [ ] Queue overflow davranışı açık hale getirilecek: backpressure veya görünür degraded mode.
- [ ] Drop edilen event sayısı telemetry'ye yazılacak.

### Kabul kriteri
Task lifecycle deterministik; telemetry kaybı varsa sessiz değildir.

---

# FAZ 8 — API / AUTH / SSRF / SECRET HARDENING (P1)

### İşler
- [ ] Production auth fail-closed.
- [ ] Development auth kapalıysa startup bunu açıkça belirtmeli; production profili reddetmeli.
- [ ] SSRF: private IP / loopback / redirect / DNS rebinding kontrolleri.
- [ ] Path traversal kontrolleri.
- [ ] Secret redaction testleri.
- [ ] Rate limit + timeout + retry sınırları.

### Kabul kriteri
Production konfigürasyonu yanlışlıkla güvenlik kapalı halde ayağa kalkamaz.

---

# FAZ 9 — RUST CORE GERÇEK ENTEGRASYON KARARI (P0)

README mevcut durumda Rust katmanının Python ürün runtime'ına bağlı olmadığını açıkça belirtmektedir. Bu nedenle iki seçenekten biri seçilecek:

### A — Ürünün zorunlu parçası
- [ ] Gerçek runtime çağrısı kurulacak.
- [ ] API/pipeline üzerinden Rust fonksiyonu çağrılacak.
- [ ] Çıktının ürün kararına etkisi E2E ile kanıtlanacak.

### B — Deneysel / optional parça
- [ ] README ve runtime dokümantasyonu buna göre netleştirilecek.
- [ ] CI compile/test kapısı korunacak.
- [ ] “Ürün özelliği devrede” şeklinde raporlanmayacak.

### Kabul kriteri
Rust'ın statüsü belirsiz kalmayacak.

---

# FAZ 10 — GERÇEK CROSS-STACK E2E (P0)

### Kritik senaryo
`API → Task → Executor → Agent → LLM Gateway → Evidence → Memory → Telemetry → UI`

### İşler
- [ ] Mock'suz kritik happy path.
- [ ] LLM yok senaryosu.
- [ ] LLM 429 senaryosu.
- [ ] LLM timeout/retry senaryosu.
- [ ] Spend cap senaryosu.
- [ ] Corrupt memory senaryosu.
- [ ] Cancellation/halt senaryosu.
- [ ] Provenance doğrulaması.
- [ ] Telemetry sequence doğrulaması.

### Kabul kriteri
Kritik zincir tek testte uçtan uca doğrulanabilir ve failure durumlarında yanlış başarı üretilmez.

---

# FAZ 11 — REGRESSION + RELEASE CANDIDATE

Her kapatılan P0/P1 için:
- [ ] Kod düzeltmesi.
- [ ] Unit/regression testi.
- [ ] Entegrasyon testi gerekiyorsa ek test.
- [ ] CI PASS.
- [ ] Değişiklik günlüğü.

Release candidate yalnızca:
- [ ] tüm CI kapıları PASS,
- [ ] tüm P0 kapalı,
- [ ] P1'ler kapalı veya açıkça risk kabul kaydıyla belgelenmiş,
- [ ] cross-stack E2E PASS,
- [ ] security checks PASS,
- [ ] provenance/cost/memory/lifecycle invariants PASS
olduğunda oluşturulacak.

---

# ÇALIŞMA SIRASI — TEK SATIRLIK TAKİP

`CI baseline → Android → provenance → cost → memory → fallback → telemetry/lifecycle → security → Rust decision → E2E → regression → release candidate`

# PRODUCTION KARARI

**Şu an:** NOT READY.

**Üretime geçiş şartı:** Bu belgedeki P0 zincirlerinin tamamı ve final E2E/CI kapılarının tek bir release candidate üzerinde kanıtlanması.

**Kanıt standardı:** “Gemini build etti”, “lokalde test geçti” veya “README'de aktif yazıyor” tek başına kabul kriteri değildir. Repository + CI + test artifact + runtime/E2E birlikte kanıt oluşturur.
