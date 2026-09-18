# PINEAL-HERETIC — Sıfır-Güven Doğrulama Turu (2026-09-18)

**Zemin:** `main@75f12c7` (PR #91 merge sonrası HEAD). Önceki raporlar (AUDIT_2026-09.md,
PR #91 gövdesi) kaynak olarak KULLANILMADI; her madde çalışan kod + canlı koşu ile ölçüldü.
Ortam: Python 3.11.2, temiz venv (`pip install -r requirements.txt`), starlette 1.6.0,
fastapi 0.141.1, uvicorn 0.53.0, gerçek uvicorn sunucusu (0.0.0.0:8765), gerçek TCP WS istemcileri.

Etiket sözlüğü: **DOĞRULANDI** = kendi ölçümüm + mutasyon testi kırmızı verdi.
**KISMİ** = ölçüm yapıldı ama bir ön koşul eksik. **BULGU** = raporla çelişen gerçek.

---

## A — P0 WS-izolasyon (öncelik 1)

### A1. `leak_probe.py` — BULGU: dosya hiç var olmamış
`git log --all -- '**/leak_probe*'` → boş. `docs/AUDIT_2026-09.md:24` "leak_probe.py ile sızıntı 0'a
indirildi" diyor; repoda böyle bir dosya **hiç commit edilmemiş**. Mevcut kanıt yalnız
`tests/integration/test_live_fixes_2026_09.py::test_send_ws_room_scoped_no_cross_room_leak`
— bu test FakeWS ile `_send_ws` fonksiyonunu izole çağırıyor; gerçek sunucu/WS yok.

Testin mantığı tautoloji mi? **Hayır**: `app.state.rooms`'a iki oda kaydedip yalnız A'ya
gönderiyor ve B'nin `sent == []` olmasını istiyor. Mutant-1 (eski `all_ws.update(...)` döngüsü
geri konuldu) → **2 failed**. Test sızıntıyı gerçekten ölçüyor, ama süreç-içi.

Eksik canlı kanıtı ben ürettim: `scripts/ws_leak_probe.py` (yeni, commit c61fe66).
Tautoloji koruması: her istemci **kendi** odasının sırrını görmek zorunda; görmüyorsa
sonuç `VIOLATION_OR_INVALID` (ilk denemede tam da bu oldu — log yayını `fact`'i değil
`tag`'i taşıyordu; sır `tag`'e taşındı, sonra geçerli oldu).

### A2. Canlı ölçüm (gerçek uvicorn, gerçek TCP) — DOĞRULANDI
| Senaryo | Alınan mesaj | Cross-room leak | Kendi sırrını kaçıran |
|---|---|---|---|
| 4 oda × 3 istemci × 3 tur (eşzamanlı POST) | 36 | **0** | 0 |
| 6 oda × 4 istemci × 5 tur | 120 | **0** | 0 |
| **Mutant** (eski tüm-odalar döngüsü, 4×3×2) | 96 | **72** | 0 |

Mutant aynı probe ile 72 sızıntı verdi → ölçüm aleti gerçek sızıntıya duyarlı.

### A3. `_send_ws` timeout/eviction — donmuş soket — DOĞRULANDI (bir nüansla)
Yöntem: aynı odada 1 donmuş istemci (`transport.pause_reading()` + SO_RCVBUF=2048 → TCP zero-window)
+ 1 sağlıklı istemci; `_WS_SEND_TIMEOUT_S=2.0`, `ws_max_queue=1`.
- Sonuç: **2885 mesajdan sonra donmuş soket setten atıldı** (t=40s); sonrasında sağlıklı
  istemciye sentinel **0.02 s**'de ulaştı, `queue.qsize()=0`. **Oda kilitlenmedi.**
- Mutant-2 (timeout kaldırıldı) → `test_send_ws_evicts_stuck_socket_on_timeout` **failed**.
- **Nüans (tasarım gerçeği, regresyon değil):** Linux tcp_wmem 4 MB'a kadar büyüdüğü için donmuş
  bir istemci ~MB'larca veri tamponlanana kadar "asılı" görünmez; eviction ancak kernel tamponu
  dolduktan sonra tetiklenir. Bu sırada oda FIFO'su o soketin timeout'u kadar (5 s prod) blokelenir
  ve `queue(maxsize=2000)` drop-oldest devreye girebilir. Kabul edilebilir; not ediyorum.
- İlk deneme bilgisi: varsayılan RATE_LIMITS["api"]=(300,60) canlı doldurmayı engelledi (429),
  bu yüzden PoC süreç-içi uvicorn + kova by-pass ile yapıldı; canlı sunucuda 120 mesajlık
  deneme (tampon dolmadan) 0.008 s gecikme, stall yok.

### A4. Zombi Chromium — KISMİ (Chromium indirilemedi) / zincir DOĞRULANDI
`playwright install chromium` sandbox'ta CDN'e ulaşamadı (Download failure); sistemde chromium yok.
Bu yüzden **gerçek Chromium süreç ağacı** ölçülemedi. Ölçülen: api.py zinciri
(WS kopar → TTL → `_evict_rooms` → `_close_room` → `session.close()`), `BrowserSession` yerine
gerçek bir çocuk süreç (`sleep 600`) başlatan ikame ile, `PINEAL_ROOM_TTL_SECONDS=1`:
- WS koptu, oda evict edildi: `room_removed=true, session_close_called=true, child alive=false` ✔
- Mutant-3 (`room.pop("browser")` + `_detach_browser_close` silindi) → `test_close_room_closes_browser_session` **failed** ✔
- **Bilinçli sınır:** WS **açıkken** oda hiç evict edilmez (`_evict_rooms` websockets olan odayı atlar);
  tarayıcı süreci WS açık kaldığı sürece yaşar (`ws_open_room_evicted=false, browser alive=true`).
  Bu tasarım kararı; ancak "sekmesi açık kullanıcı × açık tarayıcı" = süreç başına ~150-300 MB.
  `BrowserSession._teardown_locked` → `page/ctx/browser.close()` + `pw.stop()`; playwright'ın
  gerçek süreç ağacını öldürmesi ayrıca doğrulanmalı (Chromium olan ortamda `ps -ef | grep chrom`).

---

## B — 11 Eylül düzeltmelerinde regresyon

### B5. Auth path kaynağı — DOĞRULANDI, regresyon yok
- `grep -rn "url.path\|request.url" backend/ agent_core/`: gelen istekte `request.url.path`
  kullanan **sıfır** satır (tek eşleşme docstring; `security.py:259` giden httpx isteğidir).
  `auth_middleware` → `_secure_path()` → `request.scope.get("path","")` (fail-closed).
- Canlı BadHost PoC (starlette 1.6.0, tokensiz, ham `nc`):
  `Host: x/zzz?y=` → **401**, `Host: evil.example#` → **401**, `Host: a/b` → **401**,
  normal Host tokensiz → 401, tokenli → 200.

### B6. `VITE_PINEAL_TOKEN` build-time gömme — DOĞRULANDI kapalı
`VITE_PINEAL_TOKEN=CANARY_TOKEN_9f8e7d6c npm run build` → `grep -r CANARY dist/` = **0 hit**,
`VITE_PINEAL_TOKEN` string'i dist'te 0. `src/store.ts` yalnız `VITE_API_BASE` okuyor.
`grep PINEAL-HERETIC dist/assets/*.js` ✔ (gerçek Svelte build).

### B7. `requirements.lock` — KISMİ: güvenlik pinleri sağlam, lock 7 gün eskimiş
- starlette **1.6.0** (≥1.0.1 BadHost yaması ✔), fastapi 0.141.1, open-interpreter yok ✔.
- Temiz `pip install -r requirements.txt` bugün 20 paketi lock'tan farklı çözüyor
  (uvicorn 0.52.4→0.53.0, playwright 1.62→1.63, openai 3.13→3.16, invisible-playwright
  0.14→0.22, reportlab 4.5→5.0 vb.). Dockerfile lock'u kurar → prod deterministik; ama
  **CI `requirements.txt` kuruyor**, yani CI ile prod imajı farklı ağaçta test ediliyor.
  **Yapıldı (commit sonrası):** `requirements.lock` ile temiz venv → `ruff` temiz,
  **1185 passed / 2 skipped / %85.01** (PR #91'in "2 skipped" rakamı bu ağaçtan geliyormuş;
  crawl4ai lock'ta var). CI backend + smoke job'ları artık `requirements.lock` kuruyor
  (`.github/workflows/ci.yml`) → CI ile prod imajı aynı ağaç. Lock içeriği değiştirilmedi
  (yenileme = bağımlılık yükseltmesi; bu turun kapsamı değil).

---

## C — Ölü config temizliği (commit 47760b9)

Kaldırılan: `require_data_confidence`, `min_final_confidence`, `critical: true`, `fallback_enabled`.
- Ölçüm: `config_loader.py` yalnız `min_data_score/min_llm_confidence/graceful_degradation/
  field_weights/empty_list_penalty` + `pipeline.critical_agents` okuyor; 4 anahtarın kod
  tabanında başka okuyucusu yok (grep).
- `DecisionConfig.load()` önce/sonra JSON diff: tüketilen alanlarda **fark yok**.
- Karar: **kaldır** (bağlama). Gerekçe CHANGELOG'da: data_confidence kapısı koşulsuz olmalı;
  kritik ajan tek kaynak = `critical_agents` listesi; ikinci "final" eşik tasarlanmış katman değil.
- Kilit: `test_decision_config_has_no_dead_keys` — mutasyon (`critical: true` geri) → **1 failed**;
  geri alınca 6/6 yeşil.

---

## D — Zemin gerçeği

### D9. Tam CI komutu HEAD üzerinde — BULGU: rakam PR iddiasıyla tutmuyor (ama yeşil)
- `ruff check .` → All checks passed.
- `pytest --cov-fail-under=80` @75f12c7 → **1181 passed, 4 skipped**, coverage **85.01 %**.
  PR #91 iddiası: "1183 passed / 2 skipped". Fark: 2 test bu ortamda skip (crawl4ai ve
  open-interpreter opsiyonel katman kurulu değil — CI de yalnız `requirements.txt` kurduğundan
  GitHub CI'da da skip olmaları beklenir). PR iddiası muhtemelen osint ekstraları kurulu
  yerel ortamdan; "1183 passed" CI'da **yeniden üretilemedi**.
- Bu turun eklemeleriyle (2 yeni test): requirements.txt ağacı **1183 passed, 4 skipped**;
  requirements.lock ağacı **1185 passed, 2 skipped**, %85.01. Skip farkı = crawl4ai (lock'ta var,
  txt'de yok) + open-interpreter (ikisinde de yok).
- `scripts/generate_routing_shadows.py` + `git diff --exit-code` → temiz.
- GitHub Actions @75f12c7 (run 35344288711): backend/frontend/rust-core/android/smoke **success**
  (job log detayı API'den artık indirilemiyor; yalnız sonuç görüldü).

### D10. Cloudflare Pages — kod tarafı TAM, dashboard tarafı DOĞRULANAMAZ
- Kod: `wrangler.toml` (`pages_build_output_dir = "frontend/dist"`), `functions/api/[[path]].ts`
  (HTTP proxy, hop-by-hop temizliği, BACKEND_ORIGIN yoksa dürüst 502), `functions/ws/[[path]].ts`
  (WebSocketPair, doğru uç accept/return, guard kapatma). `functions/` kökte — doğru.
- Dashboard: **Root directory** (kök olmalı — `frontend/` seçilirse `functions/` görünmez) ve
  **BACKEND_ORIGIN** secret'ı repo dışı; buradan doğrulanamaz. Canlı test:
  `curl https://<pages>/api/health` → `BACKEND_ORIGIN_NOT_CONFIGURED` dönüyorsa secret eksik,
  404 dönüyorsa Root directory yanlış.

---

## Özet — go-live görüşü

| # | Madde | Durum |
|---|---|---|
| 1 | leak_probe.py var mı | **BULGU**: hiç yoktu; yeni `scripts/ws_leak_probe.py` eklendi |
| 2 | Canlı WS izolasyon | **DOĞRULANDI** 0 leak (mutant: 72) |
| 3 | Timeout/eviction | **DOĞRULANDI**, oda kilitlenmiyor (tcp_wmem nüansı) |
| 4 | Zombi Chromium | **KISMİ**: zincir doğrulandı, gerçek Chromium ortamda yoktu |
| 5 | scope["path"] | **DOĞRULANDI**, canlı 401×3 |
| 6 | VITE token | **DOĞRULANDI**, canary 0 hit |
| 7 | requirements.lock | Güvenlik pinleri ✔; CI≠lock ağacı (öneri) |
| 8 | Ölü config | Kaldırıldı, mutasyonla kilitli |
| 9 | CI | Yeşil; "1183 passed" HEAD'de 1181+4 skip olarak üretildi |
| 10 | Cloudflare | Kod tam; dashboard doğrulanamaz |

**Chromium tekrar denemesi:** 4 Playwright CDN host'u da sandbox'tan erişilemez (000/timeout;
npm/pypi 200). Gerçek Chromium ölçümü bu ortamda yapılamaz — CI/staging'de yapılmalı.

**Blocker yok.** Açık kalan tek gerçek boşluk: gerçek Chromium ile süreç-ağacı temizliğinin
Chromium olan bir ortamda tekrar ölçülmesi (madde 4).

Commit'ler: `47760b9` (config C8 + kilit test + CHANGELOG), `c61fe66` (ws_leak_probe.py), `abac3d2` (rapor), + CI lock hizalaması.
