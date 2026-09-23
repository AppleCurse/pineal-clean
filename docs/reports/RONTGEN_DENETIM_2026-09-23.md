# RÖNTGEN DENETİMİ — 2026-09-23

**Kapsam:** Kullanıcının sırayla istediği 7 adım — (1) LLM → iddia → kanıt → jüri → nihai rapor,
(2) kasa & ağ sınırları, (3) 12 ajanın kablolaması, (4) yedi motorun determinizmi,
(5) telemetri gerçekliği, (6) Rust katmanı, (7) Android katmanı.
**Yöntem:** Her adım için *gerçek yürütme yolu* ölçüldü (prob betikleri `/home/user/probe/`),
kusur kanıtlandı, düzeltildi ve **kilit test** yazıldı. Ölçülmeyen hiçbir iddia bu rapora
"tamamlandı" diye yazılmadı.
**Dürüstlük notu (2. tur):** Bu sandbox denetim sırasında SIFIRLANDI: `/home/user/probe/`
ve ilk `.venv` silindi, depo yeniden klonlandı (ilk tur commit'i `5b00351` geçmişten düştü);
tüm iş ağaçta commit'siz kaldı ve bu turda yeniden commit'lendi. Prob betikleri artık
yok — §10'daki ham prob komutları bu yüzden "yeniden üretilemez" olarak işaretlendi;
buna karşılık aynı ölçümler **kalıcı kilit testlere** taşındı (pytest ile her an
yeniden üretilebilir). Ortam bu turda CI'ın kurduğu ağacın KENDİSİYLE
(`requirements.lock`, `starlette==1.6.0` BadHost mührü dahil) yeniden kuruldu.
**Dal:** `arena/01a0cd94-pineal-epifiz`

---

## 0. ÖZET HÜKÜM

| # | Adım | Eski durum (ölçüldü) | Yeni durum | Kilit |
|---|---|---|---|---|
| 1 | İddia → kanıt → jüri → rapor | Uydurma kanıt URL'siyle `VERIFIED` → downstream "Güvenli 0.833"; hepsi BİLİNMİYOR → "Güvenli 0.70" (taban); `resonance_calc`'ta uydurma `max(0.75, skor)` tabanı | Kanıt kapısı (entailment) + kapalı oy sözlüğü + tabansız güven; kanıtsız → `UNVERIFIED 0.0`, `data_confidence=False`; **0.75 tabanı KALDIRILDI** → koşu `completed_no_decision` (§1.6) | `test_verifier_entailment_gate.py` (15), `test_verifier_jury_panel.py` (10), `test_uncertainty_data_confidence_gate.py` (5), `test_no_decision_run_status.py` (10) |
| 2 | Kasa & ağ | `.pineal_vault.json` **varsa** mandal açıktı (içi boş olsa bile); `@handle` → Instagram hedefi sayılıyordu | Anahtar malzemesi şartı + placeholder reddi + fail-closed; host'suz girdi çözümlenmez | `test_status_source_honesty.py` (kasa bölümü, 16), `tests/audit/*` (114 yeşil) |
| 3 | 12 ajan kablolaması | Rack slotları **ödünç** veriliyordu: 7-sütun motoru ve görsel analizi `PATTERN INTERRUPT` slotunu, shadow `DEPTH ANALYST` slotunu boyuyordu | Bire-bir eşleme; slotu olmayan adım hiçbir slotu boyamaz | `test_agent_rack_wiring.py` (7) |
| 4 | 7 motor determinizmi | `GRAVITY.dominant_attractor` aynı veride koşudan koşuya değişiyordu ('uzun' / 'düşündüm' / 'hakkında'); `SEISMOS.event_id` rastgeleydi | Hash-tohumundan bağımsız bayt-bayt aynı çıktı; deterministik `event_id` | `test_engine_determinism.py` (12) |
| 5 | Telemetri gerçekliği | `simulate_processing()` demo koşusu; açılışta 12/12 READY; UI `READY = gerçek \|\| 12`; sabit "REDIS PUB/SUB"; bayat telemetri; kurgu operatör profili | Simülasyon silindi; açılış WAIT; sayaçlar render edilen slotlardan; kaynak satırı backend beyanından (`redis_bus\|in_memory\|fallback\|error\|unreachable\|none`) | `test_status_source_honesty.py` (31) + `svelte-check` 0 hata |
| 6 | Rust | `set_all_ready()` (Python'daki kusurun ikizi); doğrulayıcı skoru = `çekilen sonuç / 3` → 3 arama sonucu = **%100 otantiklik** | Toplu READY silindi; skor = doğrulanmış iddia oranı, teminat ayrı alan, `NO_VERIFIED_CLAIM` → fail-closed halt | `rust_core` 2 unit test (**DERLENMEDİ**, bkz. §6.4) |
| 7 | Android | Hayalet ajan durumları (`mirror_truth`/`autonomous_verifier`/`human_behavior` RUNNING); "KASA • AKTİF (MÜHÜRLENDİ)"; "şifreli keystore" etiketi; sistem güveni = modelin kendi rezonans skoru | Durum kimliği gerçek hatta çekildi; kasa/güven etiketleri dürüst; kanıt modeli **YOK** (remediation planı §7.3) | Kotlin **DERLENMEDİ** (§7.4) |

**Test durumu (2. tur — CI ağacında ölçüldü):** denetim öncesi `33 failed / 1225 passed`
→ 1. tur `24 failed / 1305 passed / 4 skipped` → **2. tur: `1342 passed / 2 skipped /
0 failed`**, kapsam **%83.36** (CI eşiği %80). 1. turdaki 24 kırmızının tamamı eksik
bağımlılıktı (`holehe, maigret, playwright_stealth, invisible_playwright`); ortam CI'ın
kurduğu `requirements.lock` ağacıyla yeniden kurulunca hepsi YEŞİL oldu — yani "kod
kusuru değil" tespiti doğrulandı. Kalan 2 skip meşru: `crawl4ai` (2. adım dosyası) ve
`open-interpreter` (opsiyonel katman) + PIL kurulu olduğu için koşamayan None-dalı.

**Sıralama dayanıklılığı:** suite üç farklı `pytest-randomly` tohumuyla da
(12345, 777, 20260923) `0 failed` — çünkü bu turda iki **test sızıntısı** kapatıldı (§12).

**CI kapıları (yerel, CI komutlarıyla):** `ruff check .` → All checks passed;
`pytest --cov=agent_core --cov=backend --cov-fail-under=80` → %83.37 ile geçti;
`scripts/generate_routing_shadows.py` sonrası `git diff` → rota gölgesi farkı YOK;
`svelte-check` → 0 hata / 0 uyarı; `vite build` + `grep PINEAL-HERETIC dist/assets/*.js` → var.
**DERLENMEYEN katmanlar:** Rust (`cargo`) ve Android (`gradle`) bu sandbox'ta
toolchain/SDK olmadığı için derlenemedi (§6.4, §7.4). CI'da `rust-core` ve `android`
job'ları var; bu commit'in yeşil kanıtı o job'lardan alınacak — **burada "yeşil" denmiyor.**

**Yeni kilit test sayısı: 81** (15 + 10 güncellenen jüri fake'i hariç + 31 + 12 + 7 + 5 + 10
`no_decision` + 1 sızıntı kilidi).

---

## 1. ADIM 1 — LLM → İDDİA → KANIT → JÜRİ → NİHAİ RAPOR

### 1.1 Ölçülen eski durum (prob kanıtı)

`/home/user/probe/probe_verifier.py` + `probe_gate.py` ile **gerçek kod yolu** koşturuldu:

| Senaryo | Eski hüküm | Yeni hüküm |
|---|---|---|
| 10 iddiadan 1'i kesin, 9'u belirsiz | `VERIFIED`-a yaklaşan skor | `UNVERIFIED confidence=0.0 score=0.0` |
| Hepsi BİLİNMİYOR | "Güvenli", 0.70 (taban) | `UNVERIFIED 0.0`, `data_confidence=False`, `fallback_reason=no_conclusive_evidence` |
| Jüri `evidence_url="https://UYDURMA.test"` (kaynak kümesinde yok) | oy SAYILIYORDU → "Güvenli 0.833" | oy kapıda İPTAL (`kanit_url_kaynaksiz`), kesin oy 0 → `UNVERIFIED 0.0` |
| Geçersiz oy metinleri ("kesinlikle doğru", "Evet") | onay gibi işlenebiliyordu | `BİLİNMİYOR`'a kanonikleşir, `vote_accounting.invalid` içinde sayılır |

### 1.2 Bulunan kusurlar ve düzeltmeleri

1. **Kanıt kapısı yoktu (entailment).** Jürinin bildirdiği `evidence_url` ve alıntı,
   arama motorunun GERÇEKTEN döndürdüğü kaynak kümesiyle karşılaştırılmıyordu:
   model URL uydurabiliyor, "kanıt" diye kendi hayalini gösterebiliyordu.
   → `_audit_vote`: URL kaynak kümesinde değilse `kanit_url_kaynaksiz`, alıntı kaynak
   metninde geçmiyorsa `kanit_alinti_kaynaksiz` (karşılaştırma
   `agent_core/services/quote_guard.quote_matches` ile: Türkçe/ASCII katlama, ≥8 karakter).
2. **Destek oranı ölçülmüyordu.** Bir iddianın kaynak metnindeki destek oranı
   `MIN_CLAIM_SUPPORT_RATIO = 0.5` altındaysa oy iptal: `kanit_destek_orani_dusuk:X`.
3. **Oy sözlüğü açıktı.** Kapalı küme: `{DOĞRULANDI, ÇELİŞKİLİ, YALAN, BİLİNMİYOR}`.
   Büyük/küçük harf, noktalama ve aksan farkları GEÇERSİZ sayılmaz
   (`canonical_vote("Doğrulandı!") → DOĞRULANDI`); sözlük dışı her şey geçersizdir ve
   `BİLİNMİYOR`'a düşer.
4. **Türkçe küçük harf tuzağı (kapının kendi hatası).** `str.lower()` 'İ' harfini
   `i` + U+0307 (birleşik nokta) yapıyordu; bu yüzden geçerli `"BİLİNMİYOR"` oyları
   sözlükte bulunamayıp **iptal ediliyordu**. Çözüm: NFKD ayrıştırma + birleşik
   işaretleri silme, sonra çeviri. (Docstring'e işlendi.)
5. **Negatif oy gerekçesiz sayılıyordu.** `ÇELİŞKİLİ`/`YALAN` oyu boş
   `contradiction_detail` ile gelirse iptal: `celiski_gerekcesi_yok`. Çürütme iddiası
   gerekçesiz olamaz.
6. **0.70 güven tabanı fail-closed'u bypass ediyordu.** Taban kaldırıldı:
   `confidence = (kesin oy / toplam) × anlaşma oranı`. Kanıt yoksa 0.0.
7. **Hüküm sözleşmesi:** `VERIFIED` ⟺ TÜM iddialar doğrulandı; bazıları doğrulanmış,
   hiçbiri çürütülmemiş, bazıları belirsizse `PARTIALLY_VERIFIED`; aksi hâlde
   `UNVERIFIED` + `data_confidence=False`. Oy muhasebesi raporda taşınır:
   `vote_accounting = {cast, counted, voided_by_gate, invalid, seat_errors}`.
8. **Test fikstürü de aynı kusuru taşıyordu:** `tests/integration/test_p2_release_gate.py`
   jürisi `evidence_url="http"` (uydurma) ile geliyordu; yeni kapı bunu doğru şekilde
   iptal edince test kırıldı. Fikstür gerçek mock kaynağı (`http://mock.com`) ve
   birebir alıntıyı kullanacak şekilde düzeltildi — yani **kapı doğru, fixture sahteydi**.

### 1.3 Downstream bacağı (nihai rapor)

`UncertaintyEngine.evaluate` `data_confidence=False` gördüğünde fail-closed:
`is_suspicious=True, confidence=0.0, "Kaynak verisi kullanılamıyor; fallback sonuç
kabul edilmedi."` → `test_uncertainty_data_confidence_gate.py` ile kilitlendi.
Verifier artık böyle bir rapor üretemediği için "uydurma URL + Güvenli" yolu kapandı.

### 1.4 Bağımsız doğrulama var mı?

Var ve korundu: üç jüri koltuğu (`pineal_juror_google/claude/open`) TEK rotaya bağlı
(deterministik), **üreten modelin ailesiyle çakışan koltuk karar anında düşürülüyor**
(`dropped_juror`). Yeni eklenen: koltuk beyanı tek başına onay DEĞİL — her kesin oy
deterministik kanıt kapısından geçiyor. Koltuk düştüğünde panel 2 üyeyle karar verir;
UI artık sabit "3 jürili" yazmıyor, gerçek `jurors` dizisini basıyor (§5).

### 1.5 Kilitler

* `tests/unit/test_verifier_entailment_gate.py` — 15 test (uydurma URL, kaynak dışı
  alıntı, düşük destek oranı, gerekçesiz negatif oy, kapalı sözlük, Unicode,
  taban yokluğu, muhasebe alanları).
* `tests/unit/test_verifier_jury_panel.py` — 10 test (fake'ler gerçek kaynak kümesi +
  birebir alıntı kullanacak şekilde güncellendi).
* `tests/unit/test_uncertainty_data_confidence_gate.py` — 5 test.

### 1.6 KAPANDI (2. tur): `resonance_calc` güven tabanı kaldırıldı → `completed_no_decision`

**Ölçülen eski durum:** `agent_core/services/uncertainty_engine.py`'de `data_confidence=False`
olduğunda `resonance_calc` için `confidence = max(0.75, compatibility_score)` dönüyordu.
Ajanın KENDİ sözleşmesi (`resonance_calculator.py:111`) "False ⇒ çıktı karar değildir
(fail-closed)" diyor; yani **0.75 ölçülmeyen, uydurma bir güven**di ve executor'ın
`LOW_CONFIDENCE` kapısını atlatıyordu. 1. turda yalnız gerekçe metni dürüstleştirilmiş,
sayısal davranış sahip kararına bırakılmıştı (§8.4).

**Uygulanan çözüm — GÖREV TAMAMLANDI ≠ KARAR ÜRETİLDİ:**

1. `UncertaintyReport.no_decision: bool = False` (opt-in; diğer tüm ajanlarda `False`,
   yani genel fail-closed yol **gevşemedi** — kilit:
   `test_llm_agent_with_data_confidence_false_still_fails_closed`).
2. `resonance_calc` + `data_confidence=False` → `confidence = ölçülen benzerlik`
   (**taban yok**) ve `no_decision=True`.
3. `task_executor.py` (hem ana döngü hem gecikmiş ajan yolu): `no_decision` ise koşu
   `LOW_CONFIDENCE` ile `halted` YAZILMAZ; `run.status = "completed_no_decision"`,
   `run.decision_grade = False`, **çıktı ve `state=inference_gap` raporda KALIR**.
   Naif çözümün (güven 0.0 → `halted`) bedeli buydu: kanıt yokluğu bilgisi kayboluyordu.
   Ayrıca `no_decision = getattr(check, "no_decision", False) is True` — `bool(...)`
   DEĞİL: MagicMock tabanlı testlerde `getattr` truthy mock döndürüyor ve kapıyı
   yanlışlıkla açıyordu (ölçüldü: `test_deferred_agent_evidence_gate` kırıldı, düzeltildi).
4. `DecisionEngine` zaten `data_confidence=False` taşıyan koşuyu kanıt saymıyordu
   (`_run_bears_evidence`); bu turda sözleşme **koşu durumuna da** bağlandı:
   `AgentRun.decision_grade: bool` alanı eklendi ve `_unavailable_reasons`
   `status == "completed_no_decision"` veya `decision_grade is False` ise
   `"completed_no_decision"` gerekçesi üretiyor — yani hüküm yalnız özet
   payload'una bakmıyor. Sonuç: yalnız karar-olmayan koşu varsa
   `HALTED_INSUFFICIENT_EVIDENCE`, yanında gerçek kanıt taşıyan bir ajan varsa
   `PARTIALLY_COMPLETED` (karar-Grade DEĞİL). Üçü de kilitlendi
   (`test_no_decision_status_alone_degrades_even_without_summary_flag`).
5. UI: `completed_no_decision` artık `DONE` gibi yeşil boyanmıyor —
   `NO-DECISION` rozeti (amber), özet satırı `KARAR DEĞİL: inference_gap · ölçülen
   benzerlik %0 (güven uydurulmadı)`, inceleme çekmecesinde `TAMAM · KARAR YOK`.

**Kilit:** `tests/unit/test_no_decision_run_status.py` (9) — uncertainty raporu,
executor koşu kaydı (çıktı korunuyor, `confidence=0.0`, `halted` değil),
ölçülmüş rezonansın hâlâ `completed` kaldığı (kaçış kapağı değil), DecisionEngine
hükümleri ve genel fail-closed yolun gevşemediği.

---

## 2. ADIM 2 — KASA & AĞ SINIRLARI

### 2.1 Sağlam bulunanlar (ölçüldü, dokunulmadı)

* `agent_core/services/security.py`: SSRF/private-IP/link-local engelleri, DNS çözümleme
  sonrası kontrol, redirect takibi, gövde boyutu sınırları — `tests/unit/test_security_hardening.py`,
  `tests/integration/test_badhost_auth_bypass.py`, `test_faz3_security.py` yeşil.
* Görüntü indirme hattı (`human_behavior.py`) localhost/private IP'leri reddediyor
  (2026-08-28 düzeltmesi yerinde).
* Açılış bağımlılık kapısı **fail-closed**: sandbox'ta `holehe` kurulu değilken
  `StartupDependencyError: REQUIRED_DEPENDENCY_MISSING: holehe` ile açılış duruyor
  (ölçüldü) — sahte "hazır" durumu üretilmiyor.

### 2.2 Bulgu: kasa mandalı dosya varlığıyla açılıyordu

`backend/api.py::_check_vault_interlock` son koşulu `_load_vault()` idi: diskte
`.pineal_vault.json` **varsa** (ör. `{"providers": {}}`) dış-dünya mandalı açılıyordu.
Dosya varlığı yetki değildir.

**Düzeltme:** `_vault_bears_key_material(vault)` eklendi — kasa ancak gerçek anahtar
malzemesi taşıyorsa açıktır:
`providers.*.api_key` / `provider_keys.*` (uygulanabilir anahtar), veya
`api_key|or_key|ig_sessionid|x_cookie|tavily_key|serpapi_key|exa_key` alanlarında
placeholder olmayan değer. Yer tutucu işaretleri (`your, changeme, placeholder, xxx, <,
ornek`) reddedilir; boş/whitespace reddedilir; her exception **kilitli** döner.

### 2.3 Bulgu: `@handle` kısayolu P1-6 regresyonuydu

`platform_registry.extract_username("@ornek")` → `"ornek"` dönüyordu. Oysa çıplak bir
`@handle` hangi platforma ait olduğunu söylemez ve `[023]/P1-6` denetim kararı
"tanınmayan hedef tahminle kazınmaz" der. Üç denetim kilidi de
(`test_auditor_round2_findings.py:262`, `test_production_audit_findings.py` P1-6,
`test_round3_residue_findings.py` N4) host'suz girdide `""` ister.
**Düzeltme:** `@` dalı kaldırıldı (fail-closed); operatör tam profil URL'si verir.
Not: `effective_scraper_type("@x", "instagram")` açık Instagram seçimiyle hâlâ
`instagram` döner, ama `scrape_instagram` artık host'suz girdide
`InsufficientEvidenceError` ile durur. X/OSINT tarafındaki `extract_x_username`
yalnız **arama sorgusu** kurmak için kullanıldığından (profil kazımıyor) dokunulmadı;
sahip isterse aynı sıkılaştırma oraya da uygulanabilir.

### 2.4 Bulgu: Android'de kasa "mühürlendi" iddiası sahteydi

`PinealViewModel.sealVault()` yalnız bir boolean çeviriyor ve
"Kasa mühürlendi · Kimlik ve anahtarlar bellekte güvenceye alındı" logluyordu; UI yeşil
asma kilit + "KASA • AKTİF (MÜHÜRLENDİ)" + "Cihaz üzerinde yerel ve şifreli saklama"
basıyordu. Gerçekte: **hiçbir şifreleme/Keystore/EncryptedSharedPreferences yok**;
anahtarlar düz `String` olarak `StateFlow` içinde yaşıyor (diske yazılmıyor).

**Düzeltme (etiket + log düzeyinde, derlenemedi):**
`vaultActive = "KASA • İŞARETLİ (ŞİFRELİ SAKLAMA YOK)"`,
`vaultDesc = "Anahtarlar yalnız bellekte (düz metin); kalıcı veya şifreli saklama YOK"`
(EN karşılıkları da), log `SUCCESS → WARNING` ve metin gerçeği söylüyor.
API anahtarı giriş alanı zaten `PasswordVisualTransformation` ile maskeli ✓ (doğrulandı).
Gerçek mühür için gereken: Keystore-backed şifreli saklama + Python tarafındaki
`_vault_bears_key_material` eşdeğeri anahtar-malzemesi doğrulaması (§7.3).

### 2.5 Kilitler

`tests/unit/test_status_source_honesty.py` — 12 parametreli kasa-malzemesi testi +
3 interlock testi (boş dosya → kilitli, placeholder → kilitli, gerçek anahtar → açık,
exception → kilitli) ve `tests/audit/*` (114 test yeşil).

---

## 3. ADIM 3 — 12 AJAN GERÇEKTEN KOŞUYOR MU?

### 3.1 Bulgu: ödünç rack slotları (durum izlenemiyordu)

`PinealExecutor._AGENT_RACK_MAP` içinde:

```python
"shadow_executor": "depth_analyst",      # shadow -> DEPTH ANALYST slotu
"pineal_7pillar":  "pattern_interrupt",  # deterministik motor -> PATTERN INTERRUPT slotu
"vision_analyzer": "pattern_interrupt",  # görsel analizi -> AYNI slot
```

Sonuç: 7-sütun motoru koştuğunda ekranda **PATTERN INTERRUPT** READY yanıyor, görsel
analizi aynı slotu boyuyor, shadow_executor **DEPTH ANALYST** slotunu kendi durumuyla
değiştiriyordu. Rack'te görünen durum, adını taşıdığı ajana izlenemiyordu —
kullanıcının "her UI durumunu backend kaynağına kadar izle" talebinin ihlali.

**Düzeltme:** bu üç adım `None`'a eşlendi (slotsuz). `_rack_update` artık:
eşlemede `None` → hiçbir şey yayınlamaz; eşlemede yok → kendi kimliğiyle yayınlar
(ör. `interpreter`); 12 slot ↔ görev ajanı **bire-bir**.

### 3.2 Bulgu: ölü senkron yazım yedeği

`_rack_update`'in `RuntimeError` dalı `self._agent_tracker.statuses[...]` alanına
yazmayı deniyordu — tracker'da böyle bir alan **yok** (`_statuses`). Yani yedek dal hiç
çalışmadı ve hata sessizce yutuldu. **Düzeltme:** ölü dal kaldırıldı; event loop yoksa
durum yayınlanamaz ve bu dürüstçe loglanır ("durumu yayınlanamadı (çalışan event loop yok)").

### 3.3 Çağrı zinciri bağlı mı? (ölçüldü)

`tests/integration/test_agent_rack_wiring.py::test_full_mission_runs_every_routed_agent`
gerçek `PinealExecutor.execute_task` koşusuyla doğrular: router'ın planladığı her ajan
`await` edilir, rack'e yazılan her durum **slotun adını taşıyan ajandan** gelir,
slotsuz adımlar (`pineal_7pillar`, `vision_analyzer`, `shadow_executor`) rack'e hiç yazmaz.

Kablolama gerçekleri (dürüst notlar):
* 12 rack slotunun hepsi executor kaydında mevcut (`resonance_calc` → `resonance_calculator`
  bire-bir eşleme ile) — `test_every_slotted_task_agent_is_a_real_executor_agent`.
* `interpreter` yalnız `ENABLE_INTERPRETER=true` ile kaydedilir.
* `config/agent_tiers.json` `review_flags` beyanına göre `dialogue_manager`,
  `shadow_executor`, `interpreter` **dormant** (gateway çağıranı yok) — yani zincirde
  dosya olarak varlar, görev akışında koşmuyorlar. Bu bir kusur değil, kayıtlı durum;
  UI'da slotları WAIT kalır (artık uydurma READY yok).

---

## 4. ADIM 4 — YEDİ MOTOR DETERMİNİSTİK Mİ? GİZLİ LLM VAR MI?

### 4.1 Ölçülen eski durum

Aynı girdi, farklı `PYTHONHASHSEED` (0 / 1 / 42), ayrı süreçler:

| Motor | Ölçülen fark |
|---|---|
| GRAVITY | `dominant_attractor`: **'uzun' → 'düşündüm' → 'hakkında'** (21 alan farklı); `wells[0].anchor` ve `machine_note` da değişiyor. KEY matrisi `wells[0]`'ı kullandığı için kusur senteze taşıyordu. |
| SEISMOS | `event_id`'ler her koşuda farklı (`sez_148173…`, `sez_2ea1e7…`) — hash tohumundan bağımsız, çünkü `uuid.uuid4()` |
| VOID | `hits` listesi küme yinelemesinden geliyordu (bugün çıktıya yansımıyor, `hits[:8]` kırpması sıraya bağımlıydı) |

Kök neden: Python'da **küme yineleme sırası** hash rastgelelemesine bağlıdır; eşit
`pull/mass` değerli kuyularda `sort` girdi sırasını koruduğu için nihai sıralama
tohumla değişiyordu.

### 4.2 Düzeltmeler

* `gravity_engine.py`: `sorted(set(...) - STOPS)` ile sözcük yinelemesi,
  `sorted(bucket.items())`, sıralama anahtarına alfabetik kırıcı: `(-pull, -mass, anchor)`.
* `seismos_engine.py`: `event_id(kind, index, window_start, window_end)` =
  `sha256(...)[:12]` — deterministik; olay sıralaması `(-intensity, event_id)`.
* `void_engine.py`: `hits = sorted(...)` (kırpmaya dayanıklı).

### 4.3 Ölçülen yeni durum

Aynı prob yeniden koşuldu: üç tohumda da **yalnız `computed_at` farklı** (duvar saati,
tanımı gereği koşuya özgü); `gravity_map`, `seismos_events`, `void_map` bayt-bayt aynı;
`event_id`'ler tohumlar arasında aynı.

### 4.4 Gizli LLM çağrısı var mı? — YOK (kilitlendi)

`test_engines_do_not_call_llm_gateway` yedi motorun kaynağında `llm_gateway` /
`generate_text` araması yapar; `test_engines_import_no_randomness_sources` ise
`uuid`, `random`, `np.random`, `time.time()`, `datetime.now(` kullanımını yasaklar.
Motorlar `numpy` + regex + sözlük ile çalışıyor; determinizm beyanı artık testle değil
**süreçler-arası çıktı karşılaştırmasıyla** kilitli
(`test_bundle_identical_across_python_hash_seeds`).

**Sahip notu (kusur değil, tasarım sonucu):** `computed_at` kanıt hash'ine
(SHA-256 mühür) girdiği için mühür koşudan koşuya **tekrar-üretilemez**. Yeniden-üretim
karşılaştırması isteniyorsa hash girdisinden duvar saati alanlarının çıkarılması gerekir
(bugünkü mühür "bu koşunun mührü" anlamında doğrudur).

---

## 5. ADIM 5 — TELEMETRİ GERÇEKLİĞİ (sahte durum kaldı mı?)

Kullanıcının üç talebi: (a) telemetri yokken simülasyon kaldırılmalı veya OFFLINE
denmeli, (b) üretim UI'sında gerçek backend telemetrisi gösterilmeli,
(c) her UI durumu backend kaynağına izlenebilmeli.

### 5.1 Backend'de silinen sahtecilikler

| Konum | Eski | Yeni |
|---|---|---|
| `agent_status_tracker.simulate_processing()` | hiçbir ajan koşmadan `Ready→Active→Done` zamanlayıcılı **demo** koşusu | **SİLİNDİ** (ölü kod değildi: rack ile aynı veri sözleşmesini üretiyordu) |
| `AgentStatusTracker.set_all_ready()` | 12 slotu birden READY ilan eden toplu API | **SİLİNDİ**; tekil `set_ready(agent_id)` kaldı (yalnız gerçek geçişte çağrılır) |
| `init_tracker()` | açılışta `set_all_ready()` | açılışta `set_all_wait()` — hiçbir kanıt üretilmeden READY yok |
| `backend/api.py /api/initiate` | "tahmini plan" bahanesiyle `set_all_ready()` | yalnız `set_all_wait()` |
| `/api/agents/status` | tracker varsa koşulsuz `source: "redis_bus"` | `RedisBus.connection_state()` → **gerçek taşıyıcı**: `redis_bus` (PING'lenmiş) / `in_memory`; rack yoksa `fallback`, okuma patlarsa `error` |

Ölçülen kanıt: sandbox'ta Redis kapalı → `Redis baglanamadi … in-memory fallback` logu ve
API artık `source: "in_memory"` döner (eski hâlde `redis_bus` derdi).

### 5.2 Frontend'de silinen sahtecilikler

| Konum | Eski | Yeni |
|---|---|---|
| `AgentRack.svelte` sayaçlar | `READY = gerçek_ready \|\| AGENT_DEFINITIONS.length` → backend susunca **"READY 12"** | sayaçlar render edilen slot etiketlerinden türetilir; **ERROR sayacı** eklendi; yedeğe düşme yok |
| `AgentRack.svelte` taşıyıcı | sabit "REDIS PUB/SUB" metni | `KAYNAK: <busLabel>` satırı; kaynak yoksa `KAYNAK YOK — HİÇBİR AJAN DURUMU OKUNMADI` |
| `AgentRack.svelte` `idle` | `case 'idle': return 'READY'` (boşta = hazır) | `case 'idle': return 'WAIT'` |
| `App.svelte` telemetri | çekim başarısızsa **eski veri ekranda kalıyordu** | `telemetryData = null` (bayat veri canlı veri gibi gösterilemez) |
| `App.svelte` durum kaynağı | backend `source` alanı okunmuyordu; ölü `val.status \|\| val.status` | `agentStatusSource` store'una yazılır; tanımsız kaynak adı `unreachable`'a düşer |
| `store.ts` | kaynak kavramı yoktu | `agentStatusSource: 'redis_bus'\|'in_memory'\|'fallback'\|'error'\|'unreachable'\|'none'` |
| `TacticalWarRoom.svelte` operatör verisi | **sabit İngilizce kurgu** gönderiliyordu: `rituals: 'Morning cold exposure, strategic deep work, journaling'`, `playlist: 'Max Richter, Nils Frahm, Olafur Arnalds'`, `envies: 'Enduring intellectual architects…'` | katlanabilir **OPERATÖR VERİSİ** giriş satırı; operatör yazmadıysa boş gider → backend `[009]` sözleşmesi gereği `user_data_missing` ile dürüst çalışır |
| `TacticalWarRoom.svelte` özetler | uydurma varsayılanlar: `Kullanıcı Frekansı: 'Analitik'`, `Aşil Skoru ?? 15`, `plan \|\| 12`, sabit `'3 jürili'` | `veri yok` / `ölçülmedi` / `kanıt yok (alan boş döndü)`; plan yoksa `—`; **gerçek** jüri sayısı (`output_summary.jurors`) ve **gerçek** hüküm (`status`) |
| `NeuralTelemetryBoard.svelte` | — | main dalında zaten dürüst (OFFLINE overlay, `Math.random` yok) — doğrulandı, dokunulmadı |

`backend/api.py [009]` sözleşmesi ("Kullanıcı göndermediyse ASLA örnek/placeholder
ritüel ÜRETME") UI tarafında ihlal ediliyordu: mirror_truth'un "kullanıcı frekansı"
hükmü uydurma veriye bağlanıyordu. Bu, adım 1'in kanıt zincirini de kirletiyordu.

### 5.3 Doğrulama

* `frontend`: `npm ci && npm run check` → **svelte-check 0 hata, 0 uyarı** (koşuldu).
* `tests/unit/test_status_source_honesty.py` — **31 test**: tracker açılış durumu,
  toplu READY/simülasyon API'sinin yokluğu, `init_tracker` mührü, endpoint kaynak
  beyanı (redis_bus/in_memory/fallback), `/api/initiate` bloğunun yalnız WAIT yazması,
  kasa mandalı, frontend kaynak-kilidi taramaları.

---

## 6. ADIM 6 — RUST KATMANI PYTHON KURALLARINI BYPASS EDEBİLİR Mİ?

### 6.1 Kazıma/hedef kuralları: bypass YOK (ölçüldü)

Rust/Tauri yolu (`scripts/run_task.py`) kazımayı **Python tek sahipliğine** bırakıyor:
`from agent_core.services.platform_registry import … scrape_instagram` (satır 62-93).
Yani `extract_username` fail-closed kuralı, SSRF sınırları ve hedef doğrulaması Rust
tarafından atlanamıyor.

### 6.2 Bulgu: `redis_bridge::set_all_ready` (Python'daki kusurun ikizi)

`rust_core/src/redis_bridge.rs` hem `redis` feature'lı hem stub sürümde
`set_all_ready()` taşıyordu (çağıranı yok). Python'da silinen toplu-READY
sahteciliğinin ikizi olduğu için **iki sürüm de kaldırıldı**; `set_all_wait` ve
`all_agent_ids()` (12 slot, Python `AGENT_DEFINITIONS` ile senkron) korundu.

### 6.3 Bulgu: Rust doğrulayıcısı kanıtsız %100 otantiklik üretiyordu

Eski kod:

```rust
let overall_score = (verifications.len() as f32 / 3.0).min(1.0);
```

Tavily'dan **3 arama sonucu** döndüğünde skor 1.0 oluyordu — tek bir iddia bile
eşleştirilmemişken, tüm kayıtlar `truth_status = "UNVERIFIED"` iken. Yani
"otantiklik" alanı aslında **teminat** (kaç kaynak çekildi) ölçüyordu.

**Düzeltme (Python parity):**
* `authenticity_score(confirmed, total)` = doğrulanmış iddia oranı (`total == 0 → 0.0`).
* `VerifierReport` alanları ayrıştırıldı: `overall_authenticity_score` (doğrulama),
  **yeni** `evidence_coverage` (teminat), **yeni** `status` (`VERIFIED` ancak tüm
  kayıtlar `DOĞRULANDI` ise; bugün Rust hattı iddia eşleştirmesi yapmadığı için daima
  `UNVERIFIED`).
* **Kanıt kapısı:** `confirmed == 0` → `AgentEvent::ErrorHalt { error_code:
  "NO_VERIFIED_CLAIM", severity: Critical }` + `Err(HaltReason::InsufficientEvidence)`.
  Python'daki fail-closed sözleşmenin Rust karşılığı.
* `AnalysisResult.confidence = overall_score` (teminat değil).
* 2 unit test: `authenticity_score_is_confirmed_ratio_not_fetch_coverage`,
  `report_never_claims_verified_without_confirmed_claims`.

### 6.4 DÜRÜSTLÜK NOTU — Rust değişiklikleri DERLENMEDİ

Bu sandbox'ta `cargo`/`rustc`/`rustfmt` **yok** ve crates.io'ya ağ erişimi yok
(ölçüldü). Rust düzenlemeleri elle gözden geçirildi (ownership/`format!` sözdizimi,
feature-gate simetrisi, yeni alanların başka yerde inşa edilmediği doğrulandı) ama
**derleyici kanıtı üretilmedi**. CI'ın `rust` job'ı bu iki dosyayı doğrulamalı:
`rust_core/src/redis_bridge.rs`, `rust_core/src/agents/autonomous_verifier.rs`.
"Derlendi/yeşil" iddiası bu raporda YOKTUR.

### 6.5 AÇIK bulgu: `UncertaintyEngine::evaluate` → `Evidence.score = 100`

`rust_core/src/uncertainty.rs`: `[006]` düzeltmesi alan-varlığı denetimini
gerçekten sıkılaştırmış (boş obje/dizi, placeholder metin, NaN → HALT ✓), ancak PASS
durumunda `score: 100` **salt alan varlığından** üretiliyor — kalite ölçüsü yok.
Python tarafındaki `data_score` (alan ağırlıkları + boş-liste cezası) ile aynı şey değil.
Paylaşılan semantik olduğu ve Rust hattı bugün ürün yolunda olmadığı için bu turda
değiştirilmedi; sahip kararı bekliyor.

---

## 7. ADIM 7 — ANDROID AYNI GÜVENLİK/KANIT MODELİNİ UYGULUYOR MU?

### 7.1 Ölçülen gerçek: uygulamıyor

`android/.../engine/PinealAnalyzerEngine.kt` — **tek bir Gemini çağrısı** tüm profili
üretiyor: passions, frictions, cognitive, bridge, depthReport, shadowProfile.
Python tarafındaki kanıt modelinin hiçbir parçası yok:

| Python sözleşmesi | Android |
|---|---|
| Arama motoruyla gerçek kaynak kümesi (Tavily/SerpAPI) | **yok** — kaynak çekilmiyor |
| Kanıt kapısı: URL kaynak kümesinde mi, alıntı kaynakta geçiyor mu | **yok** |
| 3 koltuklu çapraz jüri + üreten ailenin koltuğunun düşürülmesi | **yok** |
| `confidence = (kesin oy / toplam) × anlaşma` (tabansız) | `overallConfidence = bridge.resonanceScore` — **modelin kendi beyanı** |
| `quote_guard` (alıntı bekçisi, deterministik) | modelin JSON'da **kendi bildirdiği** `kept/droppedFakeQuote` sayıları |
| Fail-closed `data_confidence=False` | yok |

### 7.2 Bu turda yapılan dürüstlük düzeltmeleri (etiket/durum düzeyinde)

1. **Hayalet ajan durumları silindi:** `AgentUpdate("mirror_truth"|"autonomous_verifier"|
   "human_behavior", "RUNNING")` yayınlanıyordu — Android'de bu ajanlar YOK. ViewModel
   isimleri ajan listesinde eşleştiremese de `currentAgentId`'ye yazıyordu, yani ekran
   "şu an koşan: MIRROR TRUTH" diyordu. Artık gerçek hattın kimliği: `deep_inference`
   (`defaultAgents()` zaten tek satır: "DERİN ÇIKARIM AĞI (LLM)" — o kısım dürüsttü).
2. **Eski güven yeni koşuya taşınmıyordu:** `evolveProfile` başlangıcında
   `AgentUpdate("mirror_truth", "RUNNING", currentProfile.overallConfidence)` — ölçülmeyen
   değer yeni koşunun skoru gibi yayınlanıyordu → `0.0` ile başlar.
3. **"MÜHÜRLENDİ" iddiaları:** `"360° BÜTÜNCÜL İNSAN HARİTASI BAŞARIYLA MÜHÜRLENDİ."` →
   `"360° İNSAN HARİTASI OLUŞTURULDU — TEK LLM ÇIKARIMI: bağımsız doğrulama, kanıt URL
   denetimi ve mühür (SHA-256) YOK."`
4. **Kasa etiketleri** (§2.4) ve **güven etiketi**:
   `"TOPLAM SİSTEM GÜVENİ"` → `"MODEL BEYANI GÜVEN (DOĞRULANMADI)"` /
   `"OVERALL SYSTEM CONFIDENCE"` → `"MODEL-CLAIMED CONFIDENCE (UNVERIFIED)"`.

### 7.3 Remediation planı (Android'in kanıt modeline kavuşması)

Sahip onayıyla sırayla:
1. **Kaynak çekme katmanı:** Tavily/SerpAPI istemcisi (Python `SearchEngine` eşdeğeri) +
   kaynak kümesinin ham olarak saklanması (`evidence_url`, `source_text`).
2. **Kanıt kapısı (deterministik, Kotlin'e taşınabilir):** `quote_matches` eşdeğeri
   normalizasyon (Türkçe/ASCII katlama, ≥8 karakter) + `MIN_CLAIM_SUPPORT_RATIO = 0.5`;
   kapıdan geçemeyen oy iptal.
3. **Kapalı oy sözlüğü** `{DOĞRULANDI, ÇELİŞKİLİ, YALAN, BİLİNMİYOR}` + negatif oy için
   zorunlu `contradiction_detail`.
4. **Jüri:** en az iki farklı model ailesi + üreten ailenin koltuğunun düşürülmesi;
   `vote_accounting` raporda.
5. **Güven formülü:** `(kesin / toplam) × anlaşma`, taban YOK; `data_confidence=False`
   → UI "KARAR DEĞİL" rozeti.
6. **Kasa:** Android Keystore + EncryptedSharedPreferences; `_vault_bears_key_material`
   eşdeğeri doğrulama; "mühürlendi" ancak gerçek mühür (hash + saklama) varsa.

### 7.4 DÜRÜSTLÜK NOTU — Kotlin değişiklikleri DERLENMEDİ

Sandbox'ta Android SDK/Gradle yok; üç dosyada yalnız **string literal, log metni ve
yorum** düzeyinde değişiklik yapıldı (tip/imza değişikliği YOK), süslü parantez ve
literal dengesi mekanik olarak doğrulandı. CI'ın `android` job'ı derleme kanıtını
üretmelidir. Dosyalar: `engine/PinealAnalyzerEngine.kt`, `i18n/I18n.kt`,
`ui/PinealViewModel.kt`.

---

## 8. SAHİP KARARI BEKLEYEN MADDELER

| # | Madde | Bugünkü koşan gerçek | Alternatif | Neden dokunulmadı |
|---|---|---|---|---|
| 8.1 | `pipeline.critical_agents` | `["mirror_truth"]`; `passion_mapper` yalnız `graceful_degradation: true` ile düşürülebilir | Test eskiden `passion_mapper`'ı da kritik istiyordu | Executor hükmü `kritik OR NOT graceful` olduğu için iki beyan çelişiyordu; liste kazanır ve passion_mapper tüm görevi kendi başarısızlığına bağlardı. Kilit koşan gerçeğe eşitlendi + **çelişki yasağı** testi eklendi (`test_no_critical_agent_contradicts_itself_with_graceful_degradation`). Passion gerçekten kritikse config'e eklenmeli, bayrak kapatılmalı. |
| 8.2 | `osint_investigator` birincil modeli | `gemini-3.7-flash → grok-4.6 → deepseek-v4-pro` (heavy, üçü de ÇALIŞIR) | Test `grok-4.6` birincil istiyordu | Üretim rota seçimini sessizce değiştirmemek için snapshot koşan gerçeğe eşitlendi ve gerekçe teste yazıldı. Grok birincillik isteniyorsa `AGENT_CHAINS` + kilit birlikte güncellenmeli. |
| 8.3 | `friction_detector` zinciri | `claude-sonnet-5 → gemini-3.7-flash → deepseek-v4-pro` | Test 2 basamaklı snapshot taşıyordu | Heavy tier'da paid basamak meşru; RUNBOOK tablosu (üretilmiş) ile kod uyumlu. Snapshot eşitlendi. |
| 8.4 | ~~`resonance_calc` 0.75 güven tabanı~~ **KAPANDI (2. tur)** | ~~uydurma taban~~ → taban kaldırıldı; koşu `completed_no_decision`, `decision_grade=False`, çıktı + `state=inference_gap` korunuyor; DecisionEngine bunu kanıt saymıyor; UI `NO-DECISION` (amber) | — | Sahip "görev tamamlandı ≠ karar üretildi" ayrımını onayladı; §1.6'da uygulandı ve `test_no_decision_run_status.py` (10) ile kilitlendi. |
| 8.5 | Rust `Evidence.score = 100` | alan varlığı = 100 | Python `data_score` benzeri kalite ölçüsü | Paylaşılan semantik; Rust hattı ürün yolunda değil (§6.5). |
| 8.6 | Android kanıt modeli | tek LLM çağrısı | §7.3 planı | Yeni katman (ağ istemcisi + kapı + jüri) gerektiriyor. |
| 8.7 | Kanıt mühüründe `computed_at` | mühür koşuya özgü, tekrar-üretilemez | hash girdisinden duvar saati alanlarını çıkar | Yeniden-üretim karşılaştırması isteniyorsa gerekir (§4.4). |

---

## 9. BİLİNÇLİ OLARAK YAPILMAYANLAR (dürüstlük kaydı)

* **Rust ve Kotlin derlenmedi** — sandbox'ta `cargo`/`rustc` ve `gradle`/Android SDK yok.
  "Derlendi", "CI yeşil" gibi iddialar üretilmedi; ilgili bölümler (§6.4, §7.4) işaretli.
  CI'da `rust-core` (`cargo check --all-targets`, `cargo test --locked`) ve `android`
  (`gradle lintDebug`, `testDebugUnitTest`, `assembleDebug`) job'ları TANIMLI; bu
  commit'in o iki katman için tek gerçek kanıtı bu job'ların sonucu olacak.
* ~~**`holehe`, `maigret`, `playwright_stealth`, `invisible_playwright` kurulmadı.**~~
  **2. turda KAPANDI:** sandbox sıfırlanınca venv baştan kuruldu ve bu turda CI'ın
  kullandığı `requirements.lock` ağacı birebir kuruldu. 24 kırmızının tamamı yeşile
  döndü → "eksik bağımlılık, kod kusuru değil" tespiti ölçülmüş oldu.
  (`opencv-python-headless` da pin'e uygun 4.x'te.)
* ~~**Executor cerrahisi yapılmadı** (§1.6/§8.4)~~ **2. turda YAPILDI:** sahip onayıyla
  `completed_no_decision` yolu eklendi (§1.6). Görev akışının geri kalanı değişmedi:
  `no_decision` opt-in, yalnız `resonance_calc` + `data_confidence=False` durumunda
  üretiliyor; genel `LOW_CONFIDENCE`/`SUSPICIOUS_EVIDENCE` kapıları aynen duruyor.
* **Rust ve Kotlin hâlâ derlenmedi** (aşağıda, değişmedi).
* Hiçbir yerde **örnek/placeholder veriyle üretilmiş "başarılı" kanıt** bu rapora
  yazılmadı; tüm sayılar bu sandbox'ta koşulan komutların çıktısıdır.

---

## 10. YENİDEN ÜRETME KOMUTLARI

```bash
# Ortam: CI'ın kurduğu ağacın kendisi (starlette==1.6.0 BadHost mührü dahil)
python3.11 -m venv .venv && .venv/bin/pip install -r requirements.lock \
  && .venv/bin/pip install ruff pytest pytest-asyncio pytest-cov

# Tam suite (2. tur, CI komutu): 1342 passed / 2 skipped / 0 failed, kapsam %83.36
PYTHONPATH=$PWD .venv/bin/python -m pytest -q -p no:cacheprovider \
  --cov=agent_core --cov=backend --cov-report=term-missing:skip-covered --cov-fail-under=80

# Sıralama dayanıklılığı (üç tohum da 0 failed — §12 sızıntı düzeltmelerinin kilidi)
for seed in 12345 777 20260923; do .venv/bin/python -m pytest -q --randomly-seed=$seed; done

# Lint
.venv/bin/ruff check .

# Adım 1 — kanıt kapısı, jüri ve "karar değil" ayrımı
.venv/bin/python -m pytest tests/unit/test_verifier_entailment_gate.py \
  tests/unit/test_verifier_jury_panel.py tests/unit/test_uncertainty_data_confidence_gate.py \
  tests/unit/test_no_decision_run_status.py -q

# §12 — test sızıntısı kilitleri
.venv/bin/python -m pytest tests/unit/test_routing_hardening.py \
  tests/unit/test_multi_provider_routing.py tests/unit/test_consolidation_faz1_5.py -q

# Adım 2/3/5 — kasa, rack kablolaması, telemetri dürüstlüğü
.venv/bin/python -m pytest tests/unit/test_status_source_honesty.py \
  tests/integration/test_agent_rack_wiring.py -q

# Adım 4 — motor determinizmi (süreçler-arası hash-seed karşılaştırması dahil)
.venv/bin/python -m pytest tests/unit/test_engine_determinism.py -q

# Adım 4/5 probları (ham ölçüm) — YENİDEN ÜRETİLEMEZ: sandbox sıfırlamasında
# /home/user/probe/ silindi. Aynı ölçümler kalıcı kilit testlere taşındı:
#   probe_engines*.py  -> tests/unit/test_engine_determinism.py (12)
#   probe_verifier.py  -> tests/unit/test_verifier_entailment_gate.py (15)
#   probe_gate.py      -> tests/unit/test_uncertainty_data_confidence_gate.py (5)
#                        + tests/unit/test_no_decision_run_status.py (9)

# Frontend doğrulaması (CI frontend job'ının adımları)
cd frontend && npm ci && npm run check   # svelte-check: 0 hata, 0 uyarı
npm run build && grep -q "PINEAL-HERETIC" dist/assets/*.js && echo BUILD_MARK_OK

# Rota gölgeleri (RUNBOOK + UnifiedCompactPanel) — üretildi ve --check yeşil
.venv/bin/python scripts/generate_routing_shadows.py
.venv/bin/python -m pytest tests/unit/test_routing_shadows.py -q
```

---

## 11. DEĞİŞEN DOSYALAR

**Python (üretim):** `agent_core/agents/autonomous_verifier.py` (kanıt kapısı, kapalı oy
sözlüğü, tabansız güven, NFKD kanonikleştirme), `agent_core/services/agent_status_tracker.py`
(simülasyon + toplu READY silindi, açılış WAIT), `agent_core/services/redis_bus.py`
(`connection_state()`), `agent_core/services/llm_gateway.py` (simple zincirlerdeki ölü paid
basamak silindi, AUTH fail-fast rota-kapsamlı), `agent_core/services/final_routing_policy.py`
(ikame toleransı sıkılaştırıldı), `agent_core/services/platform_registry.py` (`@handle`
fail-closed), `agent_core/services/uncertainty_engine.py` (dürüst gerekçe; **2. tur:** 0.75 tabanı
kaldırıldı, `UncertaintyReport.no_decision`),
`agent_core/task_executor.py` (ödünç slot yasağı, ölü senkron yedek kaldırıldı;
**2. tur:** `completed_no_decision` yolu — ana döngü + gecikmiş ajan yolu,
`decision_grade` bayrağı),
`agent_core/domain/memory_models.py` (**2. tur:** `AgentRun.status` sözlüğü belgelendi,
`decision_grade` alanı),
`agent_core/engines/{gravity,seismos,void}_engine.py` (determinizm),
`backend/api.py` (kasa mandalı, rack kaynağı, initiate WAIT).

**Frontend:** `src/store.ts`, `src/App.svelte`, `src/components/AgentRack.svelte`,
`src/components/TacticalWarRoom.svelte` (**2. tur:** `NO-DECISION` rozeti + amber CSS +
`KARAR DEĞİL:` özet satırı + inceleme çekmecesi `TAMAM · KARAR YOK`),
`src/components/UnifiedCompactPanel.svelte` (**2. tur:** `completed_no_decision`
tamamlanmış koşul sayılıyor ama karar değil),
`src/components/visualizers/{AgentOrchestrator,WaterHoseVisualizer}.svelte` **SİLİNDİ**
(simülasyon görselleştirmeleri; 5. adım).

**Rust:** `rust_core/src/redis_bridge.rs`, `rust_core/src/agents/autonomous_verifier.rs`.

**Android:** `engine/PinealAnalyzerEngine.kt`, `i18n/I18n.kt`, `ui/PinealViewModel.kt`.

**Doküman:** `RUNBOOK.md` (rota gölgeleri yeniden üretildi — simple zincirler artık
2 basamak, ölü gemini basamağı belgelenmiyor).

**Yeni testler:** `tests/unit/test_verifier_entailment_gate.py` (15),
`tests/unit/test_status_source_honesty.py` (31), `tests/unit/test_engine_determinism.py` (12),
`tests/integration/test_agent_rack_wiring.py` (7),
`tests/unit/test_uncertainty_data_confidence_gate.py` (5),
**2. tur:** `tests/unit/test_no_decision_run_status.py` (9).

**Güncellenen testler:** `tests/unit/test_verifier_jury_panel.py` (gerçek kaynak kümesi +
gerekçeli negatif oylar), `tests/integration/test_p2_release_gate.py` (uydurma `evidence_url`
düzeltildi), `tests/unit/test_config_contract.py` (§8.1 + çelişki kilidi),
`tests/unit/test_agent_model_policy.py` (§8.2), `tests/unit/test_task_routing_step1.py` (§8.3),
**2. tur:** `tests/unit/test_uncertainty_data_confidence_gate.py` (taban kaldırıldı →
`no_decision` beklentisi), `tests/unit/test_routing_hardening.py` (§12.1 sızıntı
düzeltmesi + yeni kilit), `tests/unit/test_consolidation_faz1_5.py` (§12.2 singleton
sıfırlaması).

---

## 12. EK BULGU (2. tur) — TEST SIZINTILARI: sıralamaya bağlı sahte yeşil/kırmızı

Denetimin 5. adımı ("sahte durum kaldı mı?") üretim kodunda sahtecilik arıyordu. 2. turda
aynı soru **testlerin kendisine** soruldu ve iki sızıntı ölçüldü. İkisi de CI'ı bugün
kırmıyordu (CI `pytest-randomly` kurmuyor, sıra deterministik) ama suite'in herhangi bir
yeniden sıralanmasında — ya da gelecekte rastgele tohum eklenirse — **başka dosyaların
dürüst testlerini kıracak** cinstendi. Yani yeşil, kısmen şansa bağlıydı.

### 12.1 `tests/unit/test_routing_hardening.py` sahte istemciyi modüle KALICI yazıyordu

`_gw(fake)` ve bir 401 testi `agent_core.services.llm_gateway.AsyncOpenAI` modül
niteliğini doğrudan eziyor, **hiç geri almıyordu**. Sahte sınıf süreç boyunca kalıyordu.

Ölçülen etki (rastgele tohum 12345):

```text
tests/unit/test_multi_provider_routing.py::test_gemini_client_uses_openai_compat_transport
E   AssertionError: assert False
E    +  where False = isinstance(<test_routing_hardening.FakeHttp.factory.<locals>._C object>,
E                                <class 'openai.AsyncOpenAI'>)
```

Aynı tohumda `tests/e2e/test_cross_stack_runtime.py::
test_critical_cross_stack_happy_path_without_method_mocks` de kırmızıydı (gerçek transport
kurucusunu bekliyor, sahteyi buluyordu). Bu iki test **yalnız koştuğunda yeşildi** —
klasik sıralama bağımlılığı.

**Düzeltme:** `monkeypatch.setattr(gwl, "AsyncOpenAI", ...)` (fixture testi bitirince
geri alır) + `_gw(fake, monkeypatch)` imzası; 5 çağrı yeri güncellendi.
**Kilit:** `test_fake_client_stitch_does_not_leak_into_module_state` — dikişin
kurulduğunu, `monkeypatch.undo()` sonrası modülün GERÇEK `AsyncOpenAI`'ye döndüğünü doğrular.

### 12.2 `test_site_dict_loaded_exactly_once_concurrent` maigret singleton'una bağımlıydı

`agent_core/services/maigret_scanner.py`'deki `_db_singleton` modül globali. Maigret
**kurulu olmadığı** eski ortamda bu test hep izoleydi; bağımlılıklar kurulunca başka bir
test (`test_maigret_scanner`) gerçek 3302 sitelik DB'yi yükleyip singleton'u dolduruyor ve
kilit testi "tek yükleme" yerine **sıfır yükleme** ölçüyordu:

```text
E   assert 0 == 1   # tek yükleme
```

Yani test artık KİLİDİ değil, TEST SIRASINI ölçüyordu.

**Düzeltme:** `monkeypatch.setattr(maigret_scanner, "_db_singleton", None)` — kilit
gerçekten ölçülür ve global test sonunda eski değerine döner (yeni sızıntı üretmez).

### 12.3 Ölçülen sonuç

| Koşu | Sonuç |
|---|---|
| CI komutu (deterministik sıra, `requirements.lock` ağacı, kapsam eşiği %80) | **1342 passed / 2 skipped / 0 failed**, kapsam %83.36 |
| `--randomly-seed=12345` | **0 failed** (düzeltme öncesi: 2 failed) |
| `--randomly-seed=777` | **0 failed** |
| `--randomly-seed=20260923` | **0 failed** |
| `ruff check .` | All checks passed |
| `generate_routing_shadows.py` + `git diff --exit-code` | fark yok |
| `svelte-check` / `vite build` / `PINEAL-HERETIC` | 0 hata / derlendi / var |
| `cargo check` / `cargo test` | **KOŞULAMADI** — toolchain yok (§6.4) |
| `gradle lintDebug` / `testDebugUnitTest` / `assembleDebug` | **KOŞULAMADI** — SDK yok (§7.4) |
