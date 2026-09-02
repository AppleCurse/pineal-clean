# "Tam Forensic AI Engine" tanımını dürüstçe taşımak için yol haritası (2026-09-02)

**Mevcut hüküm:** Pineal gerçek, denetimden geçmiş kritik açıkları testle mühürlenmiş bir
evidence-gated hybrid orchestration sistemidir — ama epistemik sözleşme uçtan uca zorunlu
olmadıkça "forensic AI engine" sayılmaz.

**Çevirme sınavı (tüm maddelerin ortak DoD'si):**
> *Bir LLM yorumu, pipeline'ın hiçbir noktasında etiketsiz olarak kanıta dönüşemiyor mu?*
> Bu soruya CI'da kırmızıya düşen bir testle "evet" dendiği gün tanım "DİR"e döner.

Satır referansları `70c3831` checkout'unun doğrulanmış hâlindendir.

---

## A. Temel katman — epistemik sözleşme (önce bu, hepsi buna dayanır)

### A-1. Typed epistemic contract'ı schema seviyesine indir
- **Ne:** `EpistemicStatus` enum (`OBSERVED | INTERPRETED | HYPOTHESIS | VERIFIED | UNAVAILABLE`)
  + her agent çıktı modelinin miras alacağı `EpistemicResult` Pydantic mixin'i
  (`epistemic: EpistemicStatus`, `evidence_refs: list[str]`, `source_provenance: str`).
- **Nerede:** `agent_core/schemas/` yeni modül; mevcut modeller (DepthReport, VerifierReport,
  AuthenticBridge, OsintProfile…) mixini miras alır.
- **DoD:** Statü alanı olmayan veya default `'OBSERVED'` bırakılan agent çıktısı schema
  validasyonundan geçemez. Yanlış statü = test kırılır.
- **Risk/kapsam:** Orta-büyük. Tek schema katmanına tecrit edilebilir; agent prompt'larına
  statü talimatı eklenir ama **statüyü kod yazar, model öneremez** (kural).

### A-2. Downstream tüketiciler statüyü zorunlu okusun
- **Nerede:** `resonance_calculator.py:_has_required_dimensions` ve
  `canonical_memory.py:_calculate_overall_confidence` (239-255), `_resolve_conflicts`.
- **Ne:** Rezonans, `model_estimate` vektörü ancak `allow_estimates=True` açıkça verildiyse
  kabul eder; çıktı `ResonanceProfile.epistemic` alanı taşır (UI "uyumluluk = model tahmini"
  diye damgalar). Bellek ortalaması statü-ağırlıklı olur (VERIFIED > INTERPRETED > HYPOTHESIS);
  confidence'lar düz ortalamayla karışmaz.
- **DoD:** `_epistemic=model_estimate` damgalı girdi ile hesaplanan rezonans skoru
  pytest'te reddedilir/etiketlenir (bugün: damga yazılıyor ama okunmuyor).

---

## B. Bilinen sıcak noktalar (A'ya bağımlı küçük düzeltmeler)

### B-1. AuthenticVector zinciri (en yüksek epistemik risk)
- **Nerede:** `task_executor.py:_calculate_authentic_vector` (~1043+), `_store_authentic_vector`.
- **Ne:** LLM psikolojik çıkarımı (depth/energy/achilles_heel/core_wound/dark_detail)
  çıktısı `HYPOTHESIS` statüsünde doğar; numeric depth/energy yalnız deterministik
  7-pillar sinyallerinden **hesaplanabilirse** OBSERVED olur — aksi halde rezonansa giremez.
- **DoD:** LLM-üretimi vektörle `ResonanceCalculator.execute` çağrısı `ResonanceCalculationError`
  fırlatır; UI "tahmini vektör" gösterimi kalır, skor üretilmez.

### B-2. PatternInterrupt data_confidence
- **Nerede:** `pattern_interrupt.py:83-90` — bugün LLM parse başarısı `data_confidence=True`'ya
  çevriliyor.
- **Ne:** `data_confidence` yalnız `_grounded_evidence` filtresinden geçen kanıt varsa True;
  yoksa `data_confidence=False` + `fallback_reason` (mevcut sözleşme).
- **DoD:** Boş kanıt input'uyla birim testte `data_confidence=False` döner.

### B-3. Verifier kaynak kapıları (deterministic)
- **Nerede:** `autonomous_verifier.py` (çağrılar 83 ve 145; çitler mevcut).
- **Ne:** Hüküm öncesi **kod** hesaplar: kaynak domain kimliği, yayın tarihi,
  bağımsızlık sınıfı (aynı domain/sindikasyon = bağımsız sayılmaz). LLM yalnız bu
  yapılandırılmış kanıtın üstüne hüküm verir; `DOĞRULANDI` statüsü en az N bağımsız,
  kimliği-doğrulanmış kaynak gerektirir (N policy).
- **DoD:** Tek domain'li iki sonuç "bağımsız kanıt" sayılamaz — testle mühürlenir.

---

## C. Routing fabric v2'yi üretime bağla (mimari katman)

### C-1. Shadow mode geçişi
- **Nerede:** `llm_gateway.py` (v1) + `llm_gateway_v2.py` (bu oturumda eklendi, 21 testli,
  hiçbir production call-site import etmiyor).
- **Ne:** `PINEAL_ROUTER_FABRIC=shadow` env'iyle v1 çağrı yaparken v2 rota kararını
  hesaplayıp loglar (diff'i kanıtlar); sorunsuzsa `=enforce`.
- **DoD:** Shadow loglarında v1/v2 karar farkı raporlanır; enforce modunda 6 kilit
  (PAID_ESCALATION vb.) mevcut `SpendCapExceeded` ile aynı muhasebeye bağlanır.

### C-2. Tek routing authority kararı
- Bugün 5 katman var (CognitiveRouter, UnifiedRouter, RoutedChatExecutor, ProviderManager,
  LLMGateway). Fabric gelirken bir tanesi tek otorite ilan edilmeli; aksi halde "çoklu
  otorite" teknik borcu büyür. (Karar dokümante edilmeli — `CAPABILITY_ROUTING_DECISION`'a ek.)

### C-3. Canlı katalog kanıtı (kullanıcı tarafında, 5 dk)
- `NOUS_API_KEY` ile `scripts/verify_nous_catalog.py` koşulur; çıktı buraya yapıştırılır.
- Damgalanan rotalar `MODEL_REGISTRY` + `MODEL_PRICING`'e **kaynak etiketiyle** mühürlenir
  (hesap-kanıtlı fiyatlar dahil). Bu olmadan "canlı provider doğrulandı" cümlesi kurulmaz.

---

## D. Güven ve operasyon sertleştirme (tanımın "forensic" ayağı)

| # | Madde | Nerede | Boyut |
|---|---|---|---|
| D-1 | Vault şifreleme / OS keystore — `.pineal_vault.json` plaintext kalmasın | `backend/api.py:377-381` | Orta |
| D-2 | Confidence aggregation: statü + ajan ağırlıklı (düz ortalama biter) | `canonical_memory.py`, `task_executor._holistic_confidence` | Küçük |
| D-3 | Fiyat tablosu tek kaynak: `MODEL_PRICING` ↔ `provider_catalog.json` ↔ docs drift bekçisi (catalog script'inden üretilen dosya) | `llm_gateway.py:136+`, `config/` | Küçük |
| D-4 | `quality_scores` için mini bench harness: konserve görevler → aday modeller → gerçek kalite sinyali (v2 skorlayıcısının boş kalan girdisi) | yeni `scripts/bench_routing_quality.py` | Orta |
| D-5 | QuotaState kalıcılığı (şu an bellek-içi; restart'ta sıfırlanır — REST sonrası kota aşım riski) | v2 modülü | Küçük-orta |

---

## Önerilen sıra ve dürüst efor tahmini

| Faz | İçerik | Tahmin | Tanıma etkisi |
|---|---|---|---|
| 1 | A-1 + A-2 (contract + tüketici zorlaması) | 2-4 gün | **Kapının kilidi** — bu olmadan gerisi tanımı değiştirmez |
| 2 | B-1, B-2, B-3 (sıcak noktalar) | 1-2 gün | Epistemik sızdıran bilinen tüm yollar kapanır |
| 3 | C-3 (katalog kanıtı) + D-3 (fiyat tek-kaynak) | yarım gün (+sizdeki komut) | Canlı-idam cümlesi kurulabilir |
| 4 | C-1 + C-2 (fabric üretime) | 2-3 gün | Maliyet-güvenlik mimarisi fiilen devrede |
| 5 | D-1, D-2, D-4, D-5 | 2-3 gün | Sertleştirme |
| 6 | CI'a "epistemik sınav" testi + nihai denetim turu | yarım gün | **Tanım "DİR"e döner** |

Tahminler bu kod tabanı içindir (sürekli yeşil suite + mevcut test altyapısı sayesinde);
canlı sağlayıcı sürprizleri dahil değildir.

## Ne değişmeyecek

- "Kanıt yoksa dur" ilkesi, halted_evidence davranışı, fail-closed kapılar: bunlar zaten
  doğru; yol haritası onları bozmaz, üstüne epistemik tip zorunluluğu ekler.
- Kullanıcı Nous kanalı hesap-kanıtlı kalır; statik slug yazımı yok (discovery kuralı korunur).

---

## Faz günlüğü

### 2026-09-02 — Faz 1 başladı (bu commit)

**Yapıldı:**
- ✔ `agent_core/schemas/epistemic.py`: `EpistemicStatus` (OBSERVED/INTERPRETED/HYPOTHESIS/
  VERIFIED/UNAVAILABLE), `EpistemicResult` mixin'i (varsayılan INTERPRETED — model kendini
  ölçülmüş ilan edemez), ağırlık tablosu, damga okuyucular (`read_marker`, `is_estimate`,
  `status_weight`).
- ✔ A-2/B-1 (rezonans kapısı): `ResonanceCalculator` artık `model_estimate` damgalı vektörü
  varsayılan olarak skora SOKMUYOR (`PINEAL_ALLOW_ESTIMATED_RESONANCE=true` ile açık taviz
  mümkün; çıktı o zaman da `epistemic="model_estimate"` damgalı). `measured`/`unstamped`
  damgaları ayrıştırılıyor.
- ✔ A-2 (bellek): `CanonicalMemory._calculate_overall_confidence` statü-ağırlıklı;
  UNAVAILABLE güvene hiç giremiyor; damgasız legacy satırlar eski düz-ortalama davranışını korur.
- ✔ Sınav testleri: `tests/unit/test_epistemic_contract.py` (9 test) +
  `test_resonance_executor_signature.py`'ye production-gerçekçi "LLM damgalı vektör →
  rezonans dürüstçe FAILED, skor üretilmez, pipeline devam eder" senaryosu.
  E2E (`test_p2_release_gate`) taviz yolunu AÇIKÇA set ediyor ve etiketin zincire taşıdığını
  doğruluyor. Tam suite: **676 passed, 2 skipped.**

**Bilerek sınırlandırılan kapsam (dürüstlük notu):**
- A-1'in schema-sweep'i (mixin'in TÜM ajan çıktı modellerine uygulanması) henüz yok — sözleşme
  çekirdeği + iki tüketici kapısı mühürlü; geriye kalan modeller Faz 1'in devam PR'ı.
- B-2 (PatternInterrupt data_confidence) ve B-3 (Verifier deterministic kaynak kapıları) sırada.
- `_DETERMINISTIC_AGENTS` içindeki `resonance_calc` sınıflandırması, vektörleri LLM'den geldiği
  sürece epistemik olarak yanıltıcıdır — Faz 2'de bu sınıf "hesaplama deterministik, girdi
  değil" diye ikiye ayrılmalı.

### 2026-09-02 (devam) — B-2 + B-3 kapandı

**B-2 (PatternInterrupt `data_confidence`):** Eski kod ayrıştırma başarılı olur olmaz
`data_confidence=True` basıyordu — prompt'ta "kanıt yetersizse false döndür" yazmasına
rağmen modelin kendi vetosu EZİLİYORDU. Yeni kural: bayrağı KOD türetir (boş mesaj veya
model vetosu → False; "true" beyanı tek başına açamaz). Veto/boş-mesaj durumunda içerik
`""`'a kırpılır (kanıtsız mesaj sızması), `epistemic=UNAVAILABLE`; aksi halde
`epistemic=INTERPRETED` + `evidence_refs` = yalnızca gerçek grounded kanıt kümesi.
`GeneratedMessage` artık `EpistemicResult` miraslı; LLM'in JSON'da `epistemic="verified"`
göndermesi parse sonrası kod tarafından ezilir (test mühürlü).

**B-3 (Verifier deterministik kaynak kapısı):** LLM'in claim sınıflandırması
(DOĞRULANDI/YALAN/ÇELİŞKİLİ) artık ancak döndürdüğü `evidence_url` o istemde GERÇEKTEN
getirilmiş arama sonuçlarından biriyse korunur; hallusine/eksik URL → BİLİNMİYOR'a demote
(simetrik: yalanlama yönünde de kanıt uydurulamaz). İzinli dört statü dışındaki model
çıktısı güvenli tarafa düşer. `VerifierReport` `EpistemicResult` miraslı: raporun damgası
hiçbir yolda VERIFIED'a çıkmaz (en yüksek INTERPRETED); `status="VERIFIED"` artık açıkça
"süreç kararı" olarak damgalı `epistemic=INTERPRETED` ile birlikte taşınır. Tüm fail-closed
erken çıkışlar (no_bio / no_search_provider / no_claims / search_unavailable /
no_verifications) `epistemic=UNAVAILABLE` damgalı.

**Testler:** +4 PatternInterrupt (kod-damgası, boş-mesaj klempi, model vetosu, self-stamp
reddi), +5 Verifier (gerçek URL korunur, hallusine URL reddedilir, simetrik kapı, bilinmeyen
statü demote, fail-closed damgalar). E2E mock'unun `evidence_url="http"` değeri kapıya
takıldı (tasarlandığı gibi) — gerçek URL ile düzeltildi. Tam suite: **685 passed, 2 skipped.**
