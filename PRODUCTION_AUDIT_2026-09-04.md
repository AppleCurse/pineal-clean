# PINEAL-HERETIC v3.0.0-rc.1 — Üretim Öncesi Kod Denetimi (Forensic QA)

**Denetçi rolü:** Kıdemli Yazılım Mimarı / QA
**Tarih:** 2026-09-04
**Kapsam:** `main` @ `c75a126` — `backend/`, `agent_core/` (≈35.000 satır Python), `tests/` (123 dosya)
**Yöntem:** Statik okuma + **gerçek çalışma zamanı ölçümü**. Her bulgu ya kod satırı ya da
komut çıktısıyla kanıtlanmıştır. Kanıtlanamayan iddia bu raporda yoktur.

---

# ⚑ ONARIM TURU — 2026-09-04 (bu rapor yazıldıktan sonra uygulandı)

İlk 6 öncelik + çapraz denetimde çıkan bir ek boşluk kapatıldı. Aşağıdaki
rakamların tamamı bu turda **yeniden ölçüldü**; raporun geri kalanı bulguların
ilk hâlini belgelemeye devam ediyor.

## Durum tablosu

| # | Bulgu | Durum | Kapanış ölçümü |
|---|---|---|---|
| P0-1 | redact O(N×M) | ✅ KAPATILDI | 67.8 ms → **2.20 ms** / 900 string; 200 mesaj 13.60 s → **0.43 s**; **11/11 çıktı birebir aynı** |
| P0-2 | cache prune yok | ✅ KAPATILDI (v2) | düşük trafikte 10 satır → **1 satır**, `pruned=10` |
| P0-3 | dict olmayan vault 500 | ✅ KAPATILDI | 4 varyant (list/null/str/int) → dict |
| P0-4 | rooms eviction yok | ✅ KAPATILDI | tavan 8 iken 12 istek → `[200×8, 503×4]`, oda sayısı **8** |
| P0-5 | `_rate_buckets` sızıntısı | ✅ KAPATILDI | 2000 kimlik, tavan 50 → **≤50 kova** |
| P0-6 | senkron SQLite | ✅ KAPATILDI | loop blokesi **28.59 ms → 2.08 ms**; `to_thread` ile medyan **0.59 ms** |
| P1-8 | `time.sleep` loop'u donduruyor | ✅ KAPATILDI | `iscoroutinefunction` + `await` çağrı noktası |
| P2-10 | auth fail-open | ✅ KAPATILDI | `PINEAL_ENV` yok + token yok → startup **reddedildi** (`PRODUCTION_AUTH_REQUIRED`) |
| P1-6 | `extract_username` | ⛔ AÇIK | — |
| P1-7 | `evaluate_confidence` ölü kod | ⛔ AÇIK | — |
| P2-9 | bozuk `learnings.json` 500 | ⛔ AÇIK | — |

## Çapraz denetimde yakalanan ek boşluk (P0-2 v2)

İlk onarım budamayı **yalnızca yazım sayısına** bağlamıştı (her 256 yazım).
Ölçülen boşluk:

```
10 yazım + TTL doldu + hiç okuma/yazma yok
  diskte kalan süresi dolmuş satır : 10
  cache.pruned                     : 0
  _writes_since_prune              : 10  (eşik 256)
SONUÇ: SIZINTI VAR — satırlar sonsuza kadar kalıyor
```

Yani düşük trafikli ama benzersiz anahtar üreten bir sistemde eşik hiç
aşılmıyordu. Tetikleyici **zaman temelli** yapıldı (`PINEAL_CACHE_PRUNE_INTERVAL_SECONDS`,
varsayılan 900 s); her `get`/`put` tek float karşılaştırması yapıyor, açılışta
da bir kez buda çalışıyor. Onarım sonrası aynı senaryo: `rows=1, pruned=10`.

## Dağıtım yapılandırmaları (fail-closed etkisi)

| Yapılandırma | `PINEAL_ENV` | Etki |
|---|---|---|
| `Dockerfile:23` | `production` (ENV ile mühürlü) | ✅ Token zorunlu — hedeflenen davranış |
| `railway.toml:3` / `railway.json:4` | `builder = docker` → **imajdan devralır** | ✅ Doğrudan yazmıyor ama kapsanmış |
| `vercel.json` | — | ✅ Yalnızca frontend (statik Vite, Python yok) |
| `baslat.bat` | `if not defined PINEAL_ENV set PINEAL_ENV=development` (eklendi) | ✅ Yerel akış kırılmadı |
| `.env.example:75` | `development` + fail-closed açıklaması (eklendi) | ✅ |

Sözleşme koruması: `tests/unit/test_dockerfile_contract.py` → `assert "PINEAL_ENV=production" in content` (**3 passed**).
**Kalan kırılganlık:** Railway builder'ı Docker'dan çıkarılırsa `PINEAL_ENV`
kaybolur — ama bu artık *sessizce açılmak* yerine *başlamayı reddetmek* demek
(fail-closed), ve `/health` 503 → `restartPolicyType = on_failure` döngüsüyle
operatöre yüksek sesle görünür.

## Onarım doğrulaması: mutasyon testi

Bir testin gerçek bir kusuru mu yoksa kendi kendini mi kandırdığını ayırmanın
tek yolu, onarımı geçici olarak geri alıp testin **kızardığını** göstermektir.
14 mutasyon uygulandı, her biri geri alındı:

```
BULGU                      SONUÇ                     ÖZET
P0-1 redact hoist          KIZARDI (test gerçek)     1 failed
P0-2 get() budama          KIZARDI (test gerçek)     1 failed
P0-2 acilista buda         KIZARDI (test gerçek)     1 failed
P0-2 son tarih yenileme    KIZARDI (test gerçek)     1 failed
P0-2 PRAGMA sirasi         KIZARDI (test gerçek)     1 failed
P0-3 vault dict            KIZARDI (test gerçek)     4 failed
P0-4 TTL karsilastirma     KIZARDI (test gerçek)     1 failed
P0-4 aktif oda korumasi    KIZARDI (test gerçek)     1 failed
P0-4 oda tavani            KIZARDI (test gerçek)     1 failed
P0-4 client_id dogrulama   KIZARDI (test gerçek)     1 failed
P0-5 LRU kirpma            KIZARDI (test gerçek)     1 failed
P0-5 suresi dolmus silme   KIZARDI (test gerçek)     1 failed
P1-8 async delay           KIZARDI (test gerçek)     2 failed
P2-10 fail-closed          KIZARDI (test gerçek)     2 failed, 4 passed
SAHTE/UYGULANAMAYAN: 0 / 14
```

**Bu tur üç sahte testi ortaya çıkardı ve düzeltti:**

1. **`P0-5/bos-kova`** — `rate_limit` içindeki "boşalan kovayı sil" satırını
   test ediyordu ama satırı kaldırmak testi **yeşil bıraktı**. Sebep: satır ölü
   koddu — `q` boşaldığında `0 >= limit` (min limit 5) daima False, yani her
   izin verilen çağrı `setdefault(...).append(now)` ile anahtarı anında geri
   koyuyordu. Test uydurmak yerine **ölü kod silindi** ve gerçek geri kazanım
   yolu (`_sweep_rate_buckets`) ayrı bir mutasyonla doğrulandı.
2. **`P0-2/acilista-buda`** — açılış budaması hiç test edilmiyordu.
   `test_startup_prune_clears_rows_left_by_previous_process` eklendi
   (önceki süreç 25 satır bırakır → yeni örnek hiçbir `get`/`put` olmadan
   temizlemeli).
3. **`P1-8`** — ilk hâli kaynak metninde `"time.sleep"` arıyordu; düzeltme
   docstring'inde bu ifade geçtiği için test kendi kendini kandırıyordu.
   `inspect.iscoroutinefunction` + çağrı noktasında `await` kontrolüne ve
   davranışsal bir event-loop testine çevrildi.

## Onarım sonrası doğrulama

| Komut | Sonuç |
|---|---|
| `ruff check .` | `All checks passed!` |
| `pytest -q` (tam set) | **832 passed, 2 skipped, 9 xfailed** (öncesi: 806 passed, 19 xfailed) |
| CI kapsam kapısı `--cov-fail-under=80` | **%84.66 — geçti** |
| Mutasyon testi | **0 / 14 sahte** |
| Canlı süreç: `PINEAL_ENV` yok | startup `PRODUCTION_AUTH_REQUIRED` ile reddedildi |
| Canlı süreç: `PINEAL_ENV=development` | `/health` 200, geçersiz `client_id` → 400, 5 KB `client_id` → 400 |
| Canlı süreç: `PINEAL_MAX_ROOMS=8` | 12 istek → 8×200 + 4×503, `ROOM_CAPACITY_EXCEEDED` |

Tek başarısız test `test_open_interpreter_imports_with_installed_psutil`
(`ModuleNotFoundError: No module named 'interpreter'`) — denetim sandbox'ında
`open-interpreter` kurulu değil; kod kusuru değil.

---

## 0. Çalıştırılan Doğrulamalar (ham çıktı)

| Komut | Sonuç |
|---|---|
| `ruff check .` (projenin kendi linter'ı) | `All checks passed!` |
| `python -m compileall agent_core backend scripts` | `compile OK` |
| `pytest -q` (tam set) | **1 failed, 806 passed, 2 skipped, 19 xfailed** |
| Tek başarısız test | `test_no_mock_in_production.py::...::test_open_interpreter_imports_with_installed_psutil` → `ModuleNotFoundError: No module named 'interpreter'` — **sandbox'ımda `open-interpreter` kurulu değil**, kod hatası değil |
| `pytest tests/audit/test_production_audit_findings.py -v` | **19 xfailed / 0 failed** — aşağıdaki 10 bulgunun tamamı yürütülebilir olarak yeniden üretildi |

> Bu raporda **P0 = canlıya çıkmayı engellemeli**, **P1 = çıkmadan hemen önce**,
> **P2 = ilk sprint içinde** olarak sınıflandırılmıştır.

**Genel değerlendirme:** Bu depo ortalama bir projeden belirgin şekilde daha disiplinli.
`CanonicalMemory` (fsync'li atomik yazma, fail-closed bozulma semantiği), `security.py`
(DNS-pinning'li SSRF koruması, `secrets.compare_digest`, path-traversal guard) ve
LLM bütçe rezervasyon/uzlaşma (reserve → settle) katmanları **gerçekten iyi tasarlanmış**.
Aşağıdaki bulgular bu genel kalitenin *dışında kalan* boşluklardır.

---

## 1. İş Mantığı ve Edge Case'ler

### 🔴 P0-3 — `.pineal_vault.json` dict değilse tüm API 500 verir

**Sorun** — `backend/api.py:378-386`

```python
vault = {}
vault_file = ".pineal_vault.json"
if os.path.exists(vault_file):
    try:
        with open(vault_file, "r", encoding="utf-8") as f:
            vault = json.load(f)          # <-- try/except YALNIZCA burayı sarıyor
    except Exception:
        pass                              # <-- sessiz yutma, log yok

api_key = vault.pop("api_key", None) or ...   # <-- korumasız
```

`json.load` bir `list`/`None`/`str`/`int` döndürürse hata **try bloğunun dışında** patlar.

**Kanıt (gerçek çalıştırma):**

```
=== 4) .pineal_vault.json dict değilse ===
sonuç: TypeError: pop expected at most 1 argument, got 2
null vault sonucu: AttributeError: 'NoneType' object has no attribute 'pop'
```

**Neden Kritik?** `get_room()` **her** endpoint'in giriş kapısı (`/api/telemetry`, `/api/initiate`,
`/api/vault`, `/ws/{client_id}`, `/api/tasks`...). Bu dosya bir kez bozulduğunda veya elle
düzenlenirken yanlışlıkla JSON dizisi kaydedildiğinde **uygulamanın tamamı ölüyor** ve
kullanıcıya dönen mesaj `INTERNAL / TypeError` — teşhis edilemez. Ayrıca `except Exception: pass`
hiçbir şey loglamadığı için operatör sebebin vault dosyası olduğunu asla göremez.

**Çözüm Önerisi**

```python
def _load_vault(path: str = ".pineal_vault.json") -> dict:
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        logger.warning("VAULT_CORRUPT: %s okunamadı (%s), boş kasa ile devam", path, exc)
        return {}
    if not isinstance(data, dict):
        logger.error("VAULT_SCHEMA_INVALID: %s bir JSON nesnesi değil (%s); yok sayıldı",
                     path, type(data).__name__)
        return {}
    return data
```

---

### 🔴 P1-6 — `extract_username` profil olmayan URL'yi hedef kullanıcı adı sanıyor

**Sorun** — `agent_core/services/platform_registry.py:42-44`

```python
def extract_username(url: str) -> str:
    return (url or "").split("?")[0].rstrip("/").split("/")[-1].replace("@", "")
```

**Kanıt (gerçek çalıştırma):**

```
https://www.instagram.com/p/CxYz123Ab/          -> username='CxYz123Ab'
https://www.instagram.com/reel/DaBc9/           -> username='DaBc9'
https://www.instagram.com/explore/tags/kedi/    -> username='kedi'
https://www.instagram.com/stories/username/123/ -> username='123'
https://www.instagram.com/accounts/login/       -> username='login'
https://www.instagram.com/                      -> username='www.instagram.com'
```

**Neden Kritik?** Modülün kendi dokümanı tam olarak bunu yasaklıyor:
> *"URL'nin son path segmentini Instagram adı gibi kullanıp yanlış hedefi kazımak misattribution'dır."*

Kod bu kuralı yalnızca **tanınmayan platformlar** için uyguluyor, Instagram içi path'ler için
uygulamıyor. Sonuç: kullanıcı bir *gönderi* linki yapıştırdığında sistem `CxYz123Ab` adında bir
profili kazımaya çalışıyor; Instagram 404/boş sayfa dönünce `InsufficientEvidenceError` ile halt
ediyor (en iyi durum) ya da **`/explore/tags/kedi/` gibi bir sayfadan "kedi" adlı bir kişinin
psikolojik profilini** üretmeye çalışıyor. Kişisel-veri hedefli bir sistemde yanlış kişiye atfedilmiş
çıktı, teknik hatadan çok daha ciddi bir risktir.

**Çözüm Önerisi**

```python
_IG_RESERVED = frozenset({
    "p", "reel", "reels", "tv", "stories", "explore", "accounts", "about",
    "legal", "privacy", "terms", "developer", "direct", "web", "challenge",
})

def extract_username(url: str) -> str:
    """Yalnızca tek segmentli gerçek profil path'ini kabul eder; aksi halde boş."""
    parsed = urllib.parse.urlsplit(url or "")
    if "instagram.com" not in (parsed.netloc or "").lower():
        return ""
    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) != 1:                       # /p/XXX, /stories/a/1, / -> reddet
        return ""
    name = parts[0].lstrip("@")
    if name.lower() in _IG_RESERVED:
        return ""
    return name
```

Ve çağıran tarafta (`scrape_instagram`) boş kullanıcı adında **kazıma yapmadan dur**:

```python
username = extract_username(url)
if not username:
    raise ValueError(f"TARGET_NOT_A_PROFILE: {url!r} bir Instagram profil adresi değil")
```

---

### 🟠 P1-7 — Scraper'ın anti-halüsinasyon güven kapısı üretimde **hiç çağrılmıyor**

**Sorun** — `agent_core/scraper/instagram_ghost.py:404-423`

```python
def evaluate_confidence(self, profile: InstagramProfile) -> float:
    ...
    # Eğer skor < 0.6 ise, task_executor bunu halt etmeli
    return round(score, 0.2)
```

**Kanıt (gerçek çalıştırma):**

```
$ grep -rn "evaluate_confidence" --include=*.py .
./agent_core/scraper/instagram_ghost.py:404:    def evaluate_confidence(...)   # TANIM
./tests/test_instagram_ghost.py:44: ...                                        # TEST
./tests/test_instagram_ghost.py:58: ...                                        # TEST
./tests/unit/test_p1_5_scraper_errors.py:187: ...                              # TEST
```

**Üretim kodundan tek bir çağrı yok.**

**Neden Kritik?** Bu, denetimde en tehlikeli bulgu türü: **testler geçiyor ama test ettikleri yol
canlıda hiç çalışmıyor.** Ekip "scraper güven kapısı test edildi, yeşil" diye düşünecek; oysa
kapı devrede değil. Düşük kaliteli/zayıf kanıtlı bir profil kazındığında pipeline durmuyor,
zayıf veriyle tam analiz üretiyor. Projenin birincil tasarım ilkesi ("Halüsinasyon = 0")
kodda uygulanmıyor.

**Çözüm Önerisi** — `platform_registry.scrape_instagram` içinde, `return`'den önce:

```python
ig_data = await ig_scraper.scrape_async(username, playwright_page=page)

confidence = ig_scraper.evaluate_confidence(ig_data)
if confidence < float(os.getenv("PINEAL_MIN_SCRAPER_CONFIDENCE", "0.6")):
    emit("ERROR", f"SCRAPER_CONFIDENCE_LOW: {confidence} < eşik; analiz başlatılmadı")
    raise InsufficientEvidenceError(
        f"Instagram kanıtı yetersiz (confidence={confidence}); profil uydurulmaz"
    )
return ig_target_profile_update(ig_data)
```

---

### 🟠 P1-11 — Log "N fotoğraf inceleniyor" diyor, kod yalnızca 2 tanesini indiriyor

**Sorun** — `agent_core/task_executor.py:409` ve `:258`

```python
self._log("INFO", f"[{task_id}] MULTIMODAL VISION: {len(raw_imgs)} fotoğraf görsel zeka ile inceleniyor...")
...
results = await asyncio.gather(*(fetch_image(client, u) for u in urls[:2]))   # <-- [:2]
```

`ig_target_profile_update` 12 posta kadar `images` üretiyor (`InstagramProfile.posts_must_be_real`
`v[:12]` diyor), ama `_download_images` sessizce ilk 2'sini alıyor.

**Neden Kritik?** İki ayrı sorun: (a) operatör log'a bakıp 12 görselin analiz edildiğini sanıyor —
telemetri yalan söylüyor; (b) 10 görselin kanıtı sessizce düşüyor, `visual_evidence` çıktısı
"kısmi" olduğu halde "tam" gibi sunuluyor. Kanıt-zinciri iddiası olan bir sistemde bu, kanıt
bütünlüğü ihlalidir.

**Çözüm Önerisi**

```python
MAX_VISION_IMAGES = 4  # modül sabiti, config'e taşınabilir

self._log("INFO", f"[{task_id}] MULTIMODAL VISION: {len(raw_imgs)} görselden "
                  f"{min(len(raw_imgs), MAX_VISION_IMAGES)} tanesi incelenecek (tavan).")
results = await asyncio.gather(*(fetch_image(client, u) for u in urls[:MAX_VISION_IMAGES]))
# ...
status.visual_evidence["images_seen"] = len(paths)
status.visual_evidence["images_available"] = len(raw_imgs)   # UI kısmi analizi göstersin
```

---

### 🟡 P2-12 — `except TypeError` ile ajan imzası "tahmin ediliyor"

**Sorun** — `agent_core/task_executor.py:552-555` (aynı desen 717-720'de tekrar)

```python
try:
    result = await agent.execute(input_data, self.memory, self.llm_gateway)
except TypeError:
    result = await agent.execute(input_data)
```

**Neden Kritik?** `TypeError` yalnızca "yanlış sayıda argüman" demek değildir. Ajanın **içinde**
gerçek bir bug varsa (`None >= 0`, `str + int`, hatalı `dict.get` zinciri) da `TypeError` fırlar.
Bu durumda kod, gerçek hatayı imza uyumsuzluğu sanıp **aynı ajanı bir kez daha çalıştırıyor**:

1. Gerçek hata maskeleniyor, teşhis imkânsızlaşıyor.
2. İlk çağrı LLM'e ulaşmışsa **aynı ajan için iki kat ödeme** yapılıyor (gateway retry'ı değil,
   pipeline seviyesinde tam tekrar).

**Çözüm Önerisi** — imzayı bir kez, belirleyici olarak tespit et:

```python
import inspect
from functools import lru_cache

@lru_cache(maxsize=None)
def _agent_arity(agent_cls: type) -> int:
    params = inspect.signature(agent_cls.execute).parameters
    return len(params) - 1          # 'self' hariç

# çağrı noktası
if _agent_arity(type(agent)) >= 3:
    result = await agent.execute(input_data, self.memory, self.llm_gateway)
else:
    result = await agent.execute(input_data)
```

Daha da iyisi: tüm ajanları `async def execute(self, ctx: AgentContext)` tek sözleşmesine çekmek
(Strategy + ortak arayüz). Şu an 13 ajan, 2 farklı imza ve çalışma-zamanı deneme-yanılma var.

---

## 2. Performans ve Ölçeklenebilirlik

### 🔴 P0-1 — `redact_text` her metin alanı için tüm `os.environ`'ı yeniden tarıyor

**Sorun** — `agent_core/utils/security.py:236-245`

```python
def redact_text(value: object, *, extra_secrets: Iterable[str] = ()) -> str:
    text = str(value)
    for secret in (*_environment_secret_values(), *tuple(extra_secrets)):  # <-- HER ÇAĞRIDA
        if secret:
            text = text.replace(secret, "[REDACTED]")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text
```

`redact_structure` bunu özyinelemeli olarak **her string yaprağı** için çağırıyor.

**Kanıt (gerçek ölçüm, 40 sırlı env değişkeni + 900 string'lik telemetri gövdesi):**

```
env'den toplanan sır sayısı: 42
redact_structure(900 string) tek çağrı: 67.8 ms
_environment_secret_values çağrı sayısı (tek redact_structure): 900
toplam str.replace operasyonu ~= 900 x 42 = 37800
200 telemetri mesajı için toplam CPU: 13.60 s
```

**Neden Kritik?** `redact_text` / `redact_structure` telemetri **sıcak yolunda ve event loop
üzerinde senkron** çağrılıyor:

- `backend/api.py:917` — `broadcast_log` → `redact_text(msg)`
- `backend/api.py:939` — `broadcast_event` → `redact_structure(event.model_dump(...))`
- `backend/api.py:985/988` — snapshot gövdesi; `:1233/1248/1251` — result gövdesi

Yani tek bir görev boyunca yüzlerce telemetri mesajı × onlarca milisaniye = **event loop'un
saniyelerce saf CPU ile meşgul olması**. Bu sürede `/health` yanıt vermez, WebSocket
gönderici kuyruğu şişer, `asyncio.Queue(maxsize=2000)` dolup mesaj düşmeye başlar
(`DEGRADED_QUEUE_OVERFLOW`). Maliyet ayrıca env değişkeni sayısıyla **doğrusal** büyüyor —
gerçek bir dağıtımda (DB URL'leri, provider anahtarları, CI secret'ları) 100+ değişkenle
durum 2-3 kat kötüleşir.

**Çözüm Önerisi**

```python
import functools, threading

_secret_cache: tuple[str, ...] = ()
_secret_lock = threading.Lock()
_secret_env_fingerprint: tuple[int, ...] | None = None

@functools.lru_cache(maxsize=4096)          # metin başına yeniden tarama yok
def _redact_one(text: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        if secret:
            text = text.replace(secret, "[REDACTED]")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text

def _current_secrets() -> tuple[str, ...]:
    """Env'i yalnızca içerik parmak izi değiştiğinde yeniden topla."""
    global _secret_cache, _secret_env_fingerprint
    fingerprint = tuple(hash((k, v)) for k, v in os.environ.items())
    if fingerprint != _secret_env_fingerprint:
        with _secret_lock:
            _secret_cache = _environment_secret_values()
            _secret_env_fingerprint = fingerprint
    return _secret_cache

def redact_text(value: object, *, extra_secrets: Iterable[str] = ()) -> str:
    extra = tuple(extra_secrets)
    return _redact_one(str(value), _current_secrets() + extra)
```

Ek olarak: `broadcast_*` fonksiyonlarındaki redaksiyonu `asyncio.to_thread`'e almak ya da
**yalnızca dışa çıkan payload'da** (WS'ye yazarken) redakte etmek, ara katmanlarda tekrar
tekrar redakte etmemek.

---

### 🔴 P0-2 — `ResponseCache` süresi dolan satırları asla silmiyor (disk sızıntısı)

**Sorun** — `agent_core/services/response_cache.py:116-140`

```python
value, created_at = row
if self.ttl_seconds and (time.time() - float(created_at)) > self.ttl_seconds:
    # Süresi dolmuş — yoksay (yeni değerin üzerine yazılacak)
    self.misses += 1
    return None
```

TTL **yalnızca okuma anında** kontrol ediliyor ve süresi dolmuş satır **silinmiyor**.
Yorum "yeni değerin üzerine yazılacak" diyor ama bu yalnızca **birebir aynı anahtar** tekrar
üretildiğinde olur — ki cache'in tüm amacı farklı prompt'lar için farklı anahtar üretmek.
`prune`, `DELETE`, `VACUUM`, satır sayısı tavanı: **hiçbiri yok.**

**Kanıt (gerçek çalıştırma, TTL=1sn, 500 kayıt):**

```
DB boyutu (yazım sonrası)               : 2084 KB
DB boyutu (TTL dolup okunduktan sonra)  : 2084 KB
expired ama diskte duran satır var mı   : True
isabet sayısı (0 olmalı)                : 0
```

**Neden Kritik?** `MAX_CACHABLE_PROMPT_CHARS = 32_000` → kayıt başına onlarca KB.
7 günlük varsayılan TTL ile sürekli çalışan bir sistemde `./cache/responses.db` **sınırsız**
büyür. Railway/Vercel/Docker ephemeral disk'lerde bu **disk dolu → sqlite `disk I/O error` →
`self.errors += 1` ve cache sessizce ölür**; daha kötüsü `CanonicalMemory` de aynı diske
yazdığı için **kanıt yazımı da başarısız olur**. Yani bir cache sızıntısı tüm sistemin veri
katmanını indirebilir.

**Çözüm Önerisi**

```python
MAX_ROWS = 50_000

def prune(self) -> int:
    cutoff = time.time() - (self.ttl_seconds or 0)
    try:
        conn = self._connect()
        try:
            cur = conn.execute("DELETE FROM response_cache WHERE created_at < ?", (cutoff,))
            conn.execute(
                "DELETE FROM response_cache WHERE key NOT IN "
                "(SELECT key FROM response_cache ORDER BY created_at DESC LIMIT ?)",
                (MAX_ROWS,),
            )
            conn.commit()
            deleted = cur.rowcount
            if deleted > 0:
                conn.execute("PRAGMA incremental_vacuum")
            return deleted
        finally:
            conn.close()
    except Exception as exc:
        logger.warning("Cache budanamadı: %s", exc)
        self.errors += 1
        return 0
```

Zamanlayıcı (asyncio task, 15 dk'da bir) + startup'ta bir kez çağrı.
Ayrıca `_init_db` başarısız olduğunda `stats()["enabled"]` şu an yanlışlıkla `True` dönüyor —
`self.enabled = False` set edilmeli.

---

### 🔴 P0-6 — Senkron SQLite çağrıları event loop'u bloke ediyor

**Sorun** — `agent_core/services/llm_gateway.py:1208` ve `:1299`

```python
cached = self.cache.get(cache_key)      # senkron sqlite3.connect + SELECT
...
self.cache.put(cache_key, content)      # senkron sqlite3.connect + INSERT + commit
```

`ResponseCache._connect()` **her** `get`/`put` için yeni bir bağlantı açıyor
(`sqlite3.connect(self.db_path, timeout=5)`), WAL modu yok.

**Kanıt (gerçek ölçüm):**

```
300 senkron cache.get sırasında en uzun event-loop gecikmesi: 30.7 ms
  (asyncio.sleep(0.001) bekliyordu; 30.7 ms = event loop bloke)
```

**Neden Kritik?** 300 okuma için 30 ms. Ölçek bunu katlayarak büyütür: (a) her çağrı
`connect()`+`close()` maliyeti ödüyor; (b) WAL kapalı olduğu için **yazıcı tüm veritabanını
kilitliyor** — eşzamanlı iki görev `put` yaparken ikincisi `timeout=5` saniye bekleyebiliyor.
Bu 5 saniye **event loop'un içinde** geçiyor: tüm HTTP istekleri, health check'ler ve
WebSocket'ler donuyor. Konteyner orkestratörü health check timeout'unda pod'u öldürebilir.

**Çözüm Önerisi**

```python
# response_cache.py
import threading

class ResponseCache:
    def __init__(self, db_path="./cache/responses.db", ttl_seconds=DEFAULT_TTL_SECONDS):
        ...
        self._local = threading.local()

    def _connect(self) -> sqlite3.Connection:
        conn = getattr(self._local, "conn", None)
        if conn is None:
            os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
            conn = sqlite3.connect(self.db_path, timeout=5, check_same_thread=False)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            self._local.conn = conn
        return conn

# llm_gateway.py — çağrı noktaları
cached = await asyncio.to_thread(self.cache.get, cache_key)
...
await asyncio.to_thread(self.cache.put, cache_key, content)
```

---

### 🔴 P0-4 — `app.state.rooms` için hiçbir eviction yok: kalıcı bellek sızıntısı + maliyet DoS'u

**Sorun** — `backend/api.py:368-449`

Her yeni `client_id` için **tam bir oda** yaratılıyor: `PinealExecutor` (13 ajan + kendi
`LLMGateway`'i + kendi `ResponseCache` SQLite bağlantısı + `CanonicalMemory`), `AspasiaChief`,
`asyncio.Queue(maxsize=2000)`, kalıcı `_room_sender` task'i, `TaskLifecycleRegistry`.
`rooms` sözlüğünden silen tek yer `lifespan` **kapanış** bloğu.

**Kanıt (gerçek çalıştırma):**

```
=== 2) sınırsız room üretimi ===
başlangıç rooms: 0
300 farklı client_id GET /api/telemetry sonrası rooms: 300
eviction/TTL/LRU kodu var mı: hayır
```

**Neden Kritik?** `client_id` **istemcinin kendi seçtiği, doğrulanmayan bir string**.
`GET /api/telemetry?client_id=<rastgele>` tek başına bir oda yaratıyor — yani **kimlik
doğrulamasız, kimlik doğrulama varsa bile tek token'la** sınırsız kaynak üretilebilir:

```bash
for i in $(seq 1 100000); do curl -s "https://host/api/telemetry?client_id=v$i" & done
```

Her oda bir executor + sender task + kuyruk taşıdığı için bu doğrudan **OOM**'dur.
Dahası `POST /api/initiate` da aynı `client_id` ile oda yarattığı için saldırgan
**saniyede N yeni LLM pipeline'ı** başlatabilir — `rate_limit("initiate:...")` `client_id`
üzerinden anahtarlandığı için her yeni `client_id` **sıfırdan 5 istek/60sn hakkı** alıyor.
`OPENROUTER_MAX_SPEND_USD=0` ise (lifespan bunu yalnızca *uyarı* olarak logluyor,
`degraded` işaretliyor, **engellemiyor**) fatura sınırsız.

**Çözüm Önerisi**

```python
MAX_ROOMS = int(os.getenv("PINEAL_MAX_ROOMS", "512"))
ROOM_TTL_SECONDS = float(os.getenv("PINEAL_ROOM_TTL_SECONDS", "1800"))
_rooms_last_seen: dict[str, float] = {}

def _evict_rooms(now: float) -> None:
    stale = [cid for cid, ts in _rooms_last_seen.items()
             if now - ts > ROOM_TTL_SECONDS
             and not app.state.rooms.get(cid, {}).get("mission_tasks")]
    for cid in stale:
        room = app.state.rooms.pop(cid, None)
        _rooms_last_seen.pop(cid, None)
        if room:
            task = room.get("sender_task")
            if task and not task.done():
                task.cancel()

def get_room(client_id: str) -> dict:
    validate_identifier(client_id, field="client_id")   # [A] biçim doğrulaması
    now = time.monotonic()
    _evict_rooms(now)
    if client_id not in app.state.rooms and len(app.state.rooms) >= MAX_ROOMS:
        raise HTTPException(status_code=503, detail="ROOM_CAPACITY_EXCEEDED")
    _rooms_last_seen[client_id] = now
    ...
```

Ve `client_id`'yi **güven sınırı** olarak kullanmayı bırakın — hız sınırlaması kimlik
üzerinden yapılmalı:

```python
# auth_middleware zaten identity_hash hesaplıyor; initiate'i de oraya taşıyın
if request.url.path == "/api/initiate" and not rate_limit(f"initiate:{identity_hash}", "initiate"):
    return JSONResponse({"error": {"code": "RATE_LIMITED", ...}}, status_code=429)
```

---

### 🔴 P0-5 — `_rate_buckets` anahtarları asla silinmiyor

**Sorun** — `backend/api.py:315-338`

```python
_rate_buckets: Dict[str, deque] = defaultdict(deque)

def rate_limit(key: str, bucket: str) -> bool:
    ...
    q = _rate_buckets[key]                 # defaultdict -> anahtar HER erişimde yaratılır
    while q and now - q[0] > window:
        q.popleft()                        # deque boşalır ama ANAHTAR kalır
    ...
```

**Kanıt (gerçek çalıştırma):**

```
başlangıç bucket sayısı: 0
5000 farklı kimlik sonrası bucket sayısı: 5000
hiçbiri siliniyor mu: hayır - _rate_buckets.pop/del yok
```

**Neden Kritik?** `identity` = token ya da **istemci IP'si**
(`identity = presented_token or request.client.host`). Her farklı IP kalıcı bir sözlük girdisi
bırakır. İnternet'e açık bir uç için bu **sınırsız bellek büyümesi**dir — düşük hacimli,
yavaş ama durdurulamaz bir sızıntı; haftalar içinde OOM.

Ek ve daha acil sorun: `request.client.host`, Railway/Vercel/nginx arkasında **proxy'nin IP'si**dir.
Yani **tüm gerçek kullanıcılar tek bir hız-sınırı kovasını paylaşır** ve `/v1` için 60 istek/dk
tavanına hep birlikte takılırlar. `X-Forwarded-For` hiç okunmuyor.

**Çözüm Önerisi**

```python
def rate_limit(key: str, bucket: str) -> bool:
    limit, window = RATE_LIMITS.get(bucket, (999, 1))
    now = time.monotonic()
    q = _rate_buckets.get(key)
    if q is None:
        if len(_rate_buckets) >= 100_000:        # sert tavan + fırsatçı temizlik
            for k in [k for k, v in _rate_buckets.items() if not v or now - v[-1] > window]:
                _rate_buckets.pop(k, None)
        q = _rate_buckets[key] = deque()
    while q and now - q[0] > window:
        q.popleft()
    if not q and key in _rate_buckets:           # boşalan kovayı geri ver
        _rate_buckets.pop(key, None)
    if len(q) >= limit:
        return False
    q.append(now)
    return True

# Kimlik tespiti (proxy arkasında doğru çalışması için)
TRUST_PROXY_HEADERS = os.getenv("PINEAL_TRUST_PROXY_HEADERS", "false").lower() == "true"

def client_identity(request: Request) -> str:
    if TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
```

> Uzun vade: süreç-içi sözlük çok örnekli (multi-replica) dağıtımda zaten yanlış çalışır.
> Redis tabanlı kayan pencere (`INCR` + `EXPIRE`) veya reverse-proxy katmanında limit.

---

### 🟠 P1-8 — Scraper `time.sleep` ile **tüm API'yi 2-5 saniye donduruyor**

**Sorun** — `agent_core/scraper/instagram_ghost.py:84-86`, çağrı noktası `:375`

```python
def _random_delay(self):
    """İnsan gibi bekle, bot gibi değil."""
    time.sleep(random.uniform(2.0, 5.0))     # SENKRON
```

`scrape_async` (async) → `platform_registry.scrape_instagram` (async) → `run_mission` (async,
FastAPI event loop'unda) zincirinin içinde çağrılıyor.

**Neden Kritik?** Tek bir kazıma boyunca **tüm süreç** durur: başka bir kullanıcının
`/v1/chat/completions` isteği, WebSocket telemetrisi, `/health` yoklaması — hepsi. Üç
denemeli retry döngüsünde bu **15 saniyeye** kadar çıkabilir. Konteyner health check'i
timeout'a düşerse orkestratör instance'ı öldürür ve görev yarıda kaybolur. Ayrıca Playwright
tarayıcısı o süre boyunca açık kaldığı için bellek de tutuluyor.

**Çözüm Önerisi**

```python
async def _random_delay(self):
    """İnsan gibi bekle — ama event loop'u kilitlemeden."""
    await asyncio.sleep(random.uniform(2.0, 5.0))

# çağrı noktası
await playwright_page.goto(target_url, wait_until="domcontentloaded", timeout=15000)
await self._random_delay()
```

---

### 🟠 P1-9 — Sıralı `await` döngüsü: public-web araştırmasında N×RTT

**Sorun** — `backend/api.py:1714-1720`

```python
for m in matched[:crawl_enricher.research_limit()]:
    res = await crawl_enricher.fetch_readable(m["source_url"])   # sıralı
    if res.available:
        m["crawl"] = res.model_dump()
        crawled += 1
```

**Neden Kritik?** 8 sonuç × ortalama 2 sn = **16 saniye** tek bir HTTP isteği içinde.
İstemci zaman aşımına düşer, bağlantı kopar, ama sunucu tarafında iş devam eder (boşa harcanan
kaynak). `/api/scraper/authorize-alternative` yanıt veremez hale gelir.

**Çözüm Önerisi**

```python
targets = matched[: crawl_enricher.research_limit()]
results = await asyncio.gather(
    *(crawl_enricher.fetch_readable(m["source_url"]) for m in targets),
    return_exceptions=True,
)
for m, res in zip(targets, results):
    if isinstance(res, BaseException):
        logger.warning("crawl failed for %s: %s", m["source_url"], type(res).__name__)
        continue
    if res.available:
        m["crawl"] = res.model_dump()
        crawled += 1
```

---

### 🟡 P2-13 — Oda başına sınırsız listeler

| Konum | Yapı | Sınır |
|---|---|---|
| `api.py:930` | `room["events"].append(telemetry)` | **yok** (`logs` 50'de kırpılıyor, `events` kırpılmıyor) |
| `api.py:997` | `room["active_tasks"][snapshot.task_id] = snapshot` | **yok** — her snapshot tüm profili (görsel kanıt, OSINT ayak izi) tutar |
| `api.py:1813` | `room.setdefault("interventions", []).append(...)` | **yok** |
| `api.py:1760` | `room["authorized_alternatives"]` | **yok** |
| `canonical_memory.py:47` | `self._locks = defaultdict(asyncio.Lock)` | **yok** — her `task_id` kalıcı bir `Lock` bırakır |
| `dialogue_manager.sessions` | `/api/experimental/chat/respond` | **yok** |

**Çözüm:** hepsini `collections.deque(maxlen=N)` yapın; `_locks` için `WeakValueDictionary` ya da
görev sonunda `self._locks.pop(task_id, None)`.

```python
# canonical_memory.py
async def merge_evidence(self, task_id, evidence_chain):
    lock = self._locks[task_id]
    async with lock:
        try:
            ...
        finally:
            if not lock.locked() and task_id in self._locks:
                self._locks.pop(task_id, None)
```

---

## 3. Hata Yönetimi (Error Handling)

### 🔴 P2-9 — Bozuk `learnings.json` → `/api/override` **kalıcı** 500

**Sorun** — `backend/api.py:1341-1358`

```python
def _read_learnings():
    return json.load(open(lp, encoding="utf-8")) if os.path.exists(lp) else []
def _write_learnings(data):
    with open(lp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

learn = await asyncio.to_thread(_read_learnings)
learn.append({...})                              # dict gelirse AttributeError
await asyncio.to_thread(_write_learnings, learn)
```

**Kanıt (gerçek çalıştırma):**

```
=== 5) /api/override bozuk learnings.json ===
JSONDecodeError: Expecting property name enclosed in double quotes: line 1 column 3 (char 2)
=== 6) learnings.json dict ise (liste bekleniyor) ===
AttributeError: 'dict' object has no attribute 'append'
```

**Neden Kritik?** Dosya bir kez bozulursa endpoint **kendini onaramaz** — kullanıcı her denemede
500 alır, dosya bozuk kaldığı için sonsuza dek. Üstelik `_write_learnings` doğrudan hedef dosyaya
yazıyor: süreç yazma sırasında ölürse (OOM, `SIGKILL`, konteyner yeniden başlatma) dosya **yarım
kalır** ve bir sonraki okuma bozuk olur. Yani sistem kendi kendine bu durumu üretebiliyor.
`CanonicalMemory`'de doğru yapılan iş (fsync'li atomik `os.replace`) burada yapılmamış.

Not: `json.load(open(...))` ayrıca **kapatılmayan dosya tanıtıcısı** bırakır — `-W error::ResourceWarning`
ile doğrulandı: `ResourceWarning: unclosed file <_io.TextIOWrapper ... mode='r'>`. CPython refcount
sayesinde pratikte kapanıyor, ama bu bir dil uygulaması garantisidir, kod garantisi değil.

**Çözüm Önerisi**

```python
def _read_learnings() -> list:
    if not os.path.exists(lp):
        return []
    try:
        with open(lp, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
        logger.error("LEARNINGS_CORRUPT: %s okunamadı (%s); karantinaya alınıyor", lp, exc)
        os.replace(lp, f"{lp}.corrupt.{int(time.time())}")   # kanıtı sakla, akışı kurtar
        return []
    if not isinstance(data, list):
        logger.error("LEARNINGS_SCHEMA_INVALID: liste değil (%s); sıfırlanıyor", type(data).__name__)
        return []
    return data

def _write_learnings(data) -> None:
    tmp = f"{lp}.{os.getpid()}.tmp"                # benzersiz ad -> çok süreçli çakışma yok
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, lp)
```

---

### 🔴 P2-10 — Kimlik doğrulama **fail-open**: `PINEAL_ENV` unutulursa tüm API açık

**Sorun** — `agent_core/utils/security.py:60-80`

```python
def _is_production() -> bool:
    return os.getenv("PINEAL_ENV", "development").strip().lower() in {"production", "prod"}

def security_posture() -> dict:
    environment = "production" if _is_production() else "development"
    ...
    return {"auth_required": required or bool(token), ...}
```

**Kanıt (gerçek çalıştırma, `PINEAL_ENV` ve `PINEAL_TOKEN` set edilmemiş):**

```
{"environment": "development", "auth_required": false,
 "auth_state": "DISABLED_DEVELOPMENT_ONLY", "warning_code": "AUTH_DISABLED_DEVELOPMENT_ONLY"}
```

**Neden Kritik?** Varsayılan **"development"**. Gerçek bir dağıtımda en sık yapılan hata tek bir
env değişkenini unutmaktır. `PINEAL_ENV` unutulduğunda `/api/*`, `/v1/*` ve `/ws/*` **tamamen
kimlik doğrulamasız** açılır. Bu sistem ne yapıyor? Hedef kişilerin OSINT profilini çıkarıyor,
e-posta/kullanıcı adı taraması yapıyor, kişisel veri üretiyor. Kimlik doğrulamasız açık bir
`/api/experimental/maigret/scan` **üçüncü şahıslara ücretsiz bir OSINT aracı** demektir.

Güvenlik varsayılanları her zaman **fail-closed** olmalıdır: ortam belirsizse koruma açık kalır.

**Çözüm Önerisi**

```python
_TRUSTED_DEV_ENVS = {"development", "dev", "test", "ci", "local"}

def _environment_name() -> str:
    return os.getenv("PINEAL_ENV", "").strip().lower()

def security_posture() -> dict:
    env = _environment_name()
    if not env:
        # Belirsiz ortam = üretim kabul et (fail-closed)
        logger.warning("PINEAL_ENV set edilmemiş; ortam ÜRETİM varsayıldı (fail-closed).")
        environment = "production"
    elif env in _TRUSTED_DEV_ENVS:
        environment = "development"
    else:
        environment = "production"
    ...
```

Ek: `lifespan` içinde `auth_state == "DISABLED_DEVELOPMENT_ONLY"` iken **bağlayıcıyı da daraltın**
(`0.0.0.0` yerine `127.0.0.1`) veya startup'ı tamamen reddedin.

---

### 🟠 P1-14 — 14 yerde exception sessizce yutuluyor

**Kanıt (gerçek tarama):**

```
sessizce yutulan exception sayısı: 14
  backend/api.py:383                     except Exception: -> pass      # vault yükleme
  agent_core/aspasia/aspasia_chief.py:76 except Exception: -> pass
  agent_core/scraper/instagram_ghost.py:133  -> pass
  agent_core/scraper/instagram_ghost.py:222  -> return None
  agent_core/scraper/instagram_ghost.py:277  -> continue
  agent_core/scraper/instagram_ghost.py:323  -> continue
  agent_core/services/llm_gateway.py:752/781/866/942/991/1878/1885/1891
```

En kritik olanı `backend/api.py:383` — P0-3'te anlatılan vault yükleme. Kullanıcının API anahtarı
sessizce yüklenmez, kullanıcı "neden LLM çalışmıyor" diye saatlerce arar, loglarda **hiçbir iz yok.**

**Neden Kritik?** "Kod hata aldığında sistem çöküyor mu?" sorusunun cevabı burada tersine dönüyor:
sistem çökmüyor ama **sessizce yanlış davranıyor.** Kişisel veri üreten bir sistemde teşhis
edilemeyen sessiz başarısızlık, gürültülü çökmeden daha pahalıdır.

**Çözüm Önerisi** — proje geneli kural:

```python
# YASAK
except Exception:
    pass

# ZORUNLU: ya daralt, ya logla, ya ikisini de yap
except (json.JSONDecodeError, OSError) as exc:
    logger.warning("VAULT_LOAD_FAILED path=%s err=%s", vault_file, exc)
```

Ve `ruff.toml`'a ekleyin (şu an yalnızca `E9` + `F` seçili — bu sınıfı hiç yakalamıyor):

```toml
[lint]
select = ["E9", "F", "S110", "S112", "BLE", "TRY"]   # try-except-pass, bare-except, blind-except
```

Ayrıca `backend/api.py:1036`'da **çıplak `except:`** var (WebSocket döngüsü) — `KeyboardInterrupt`,
`SystemExit` ve `asyncio.CancelledError`'ı da yutar; `except (WebSocketDisconnect, Exception)` olmalı.

---

### 🟠 P1-15 — Yakalanmayan hata işleyicisi hiçbir şey loglamıyor

**Sorun** — `backend/api.py:299-307`

```python
@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    body = (...)
    return JSONResponse(body, status_code=500)     # <-- logger yok, exc_info yok
```

**Neden Kritik?** Starlette bu işleyiciyi çağırdıktan sonra istisnayı yeniden yükseltir, yani
uvicorn bir traceback basar — ama **yapılandırılmış log yok**: hangi endpoint, hangi `client_id`,
hangi `task_id`, hangi payload? `/api/override` örneğinde olduğu gibi 500'ler gelmeye başladığında
operatörün elinde yalnızca `INTERNAL / TypeError` ve bir yığın izi var; hangi isteğin tetiklediği
belirsiz. 20+ yılın dersi: **500 her zaman korelasyon kimliğiyle loglanmalı.**

**Çözüm Önerisi**

```python
@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request.state.request_id = uuid.uuid4().hex[:12]
    response = await call_next(request)
    response.headers["X-Pineal-Request-ID"] = request.state.request_id
    return response

@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    rid = getattr(request.state, "request_id", "unknown")
    logger.error(
        "UNHANDLED request_id=%s method=%s path=%s client=%s type=%s",
        rid, request.method, request.url.path,
        request.query_params.get("client_id", "-"), type(exc).__name__,
        exc_info=exc,
    )
    body = (
        _openai_error(f"Internal server error (request_id={rid})", "server_error", "internal_error")
        if request.url.path.startswith("/v1/")
        else {"error": {"code": "INTERNAL", "message": type(exc).__name__, "request_id": rid}}
    )
    return JSONResponse(body, status_code=500)
```

---

### 🟡 P2-16 — `run_mission`: geri çekilme (backoff) yok, maliyet 3× katlanıyor

**Sorun** — `backend/api.py:1160-1190`

```python
max_attempts = _bounded_env_int("PINEAL_TASK_MAX_ATTEMPTS", 3, 1, 3)
for attempt in range(1, max_attempts + 1):
    try:
        res = await asyncio.wait_for(executor.execute_task(payload, task_id), timeout=task_timeout)
        ...
    except Exception as e:                       # <-- CancelledError dahil her şey
        if attempt == max_attempts: ...
```

Üç ayrı sorun:

1. **Backoff yok.** Bir provider kesintisinde üç deneme arka arkaya, sıfır beklemeyle yapılır.
   Gateway kendi içinde de 3 deneme yapıyor (`max_retries = 3`, `backoff = 2**attempt_index`) →
   toplam **9 LLM denemesi**, fatura 9×.
2. **`except Exception` `asyncio.CancelledError`'ı yakalar mı?** Python 3.8+'da
   `CancelledError`, `BaseException`'dan türer, yani yakalanmaz — bu doğru. Ama
   `asyncio.wait_for` timeout'unda `TimeoutError` yakalanır ve **görev iptal edilmiş olsa bile
   yeniden başlatılır.** Kullanıcı `/api/tasks/{id}/cancel` çağırdıysa `mission.cancel()`
   `run_mission`'ın kendisini iptal eder (doğru), ancak `wait_for` iç zaman aşımıyla karıştığında
   iptal edilmiş bir görev tekrar denenebilir.
3. **`task_id` `None` kalabilir.** `task_id = task_id or _new_task_id()` satırı **scrape
   adımından sonra**. Scrape `InsufficientEvidenceError` atarsa dış `except` bloğuna
   `task_id=None` ile düşülür → `broadcast_result_error(..., None)` → payload'da `task_id` yok.
   Ama `api_initiate` çoktan `_lifecycle(room).transition(task_id, "processing")` ile bir
   **yaşam döngüsü kaydı açmış** ve o kayıt **asla terminal duruma geçmiyor**.
   `/api/aspasia/state` metrikleri sonsuza dek "processing" hayalet görevler biriktirir.

**Çözüm Önerisi**

```python
async def run_mission(req: InitiatePayload, task_id: Optional[str] = None):
    client_id = req.client_id
    task_id = task_id or _new_task_id()          # [A] EN BAŞTA ata
    executor = get_executor(client_id)
    ...
    for attempt in range(1, max_attempts + 1):
        try:
            res = await asyncio.wait_for(executor.execute_task(payload, task_id),
                                         timeout=task_timeout)
            broadcast_result(client_id, res)
            return
        except asyncio.CancelledError:
            _lifecycle(get_room(client_id)).transition(task_id, "cancelled")
            raise                                 # iptal asla yeniden denenmez
        except InsufficientEvidenceError:
            raise
        except asyncio.TimeoutError as e:
            broadcast_log(client_id, "ERROR", f"ZAMAN AŞIMI (deneme {attempt}/{max_attempts})")
            if attempt == max_attempts:
                broadcast_result_error(client_id, "timeout", "Görev zaman aşımına uğradı", task_id)
                return
        except Exception as e:
            logger.exception("MISSION_FAILED task_id=%s attempt=%s", task_id, attempt)
            if attempt == max_attempts:
                broadcast_result_error(client_id, "failed",
                                       f"MAKSİMUM DENEME AŞILDI ({max_attempts})", task_id)
                return
        await asyncio.sleep(min(2 ** attempt, 30) + random.uniform(0, 1))   # [B] backoff + jitter
```

Ayrıca: deneme sayısı, **yalnızca geçici (transient) hatalarda** artırılmalı. Kalıcı hatalarda
(auth, bilinmeyen model, yetersiz kanıt) tekrar denemek sadece para yakar:

```python
_PERMANENT = (InsufficientEvidenceError, SpendCapExceeded, ModelSubstitutionDeniedError)
if isinstance(e, _PERMANENT):
    broadcast_result_error(client_id, "failed", str(e)[:200], task_id)
    return
```

---

### 🟡 P2-17 — HTTP 200 içinde hata gövdesi

`backend/api.py:1503-1516` (`/api/experimental/chat/respond`):

```python
except Exception as e:
    logger.error("Dialogue generation failed: %s", type(e).__name__)
    return {"error": {"code": "DIALOGUE_FAILED", "message": type(e).__name__}}   # 200 OK
```

Aynı desen `/api/experimental/shadow/analyze`, `/shadow/generate`, `/api/aspasia/chat`
(`ASPASIA_UNAVAILABLE`) için de geçerli. İzleme araçları ve yük dengeleyiciler **200 görür**,
alarm üretmez; hata oranı metriklerde görünmez. `logger.error` da `exc_info` taşımıyor —
stack trace kayboluyor.

**Çözüm:** başarısızlıkta doğru durum kodu dönün (`502`/`503`) ve `logger.error(..., exc_info=exc)`.

---

## 4. Kod Kalitesi ve Standartlar

### 🟠 P1-18 — `backend/api.py` = 2014 satır, 30+ endpoint, 6 farklı sorumluluk

Dosya şunların **hepsini** içeriyor: FastAPI uygulaması, CORS/auth/rate-limit middleware,
telemetri FIFO veriyolu, oda (room) yaşam döngüsü, vault yönetimi, OSINT uçları, Aspasia
komut dispatch'i, public-web araştırma motoru, görev retention/silme API'si, statik dosya mount'u.

**Neden Kritik?** Bu bir **God Object**. Somut sonuçları raporda zaten görünüyor:
`rate_limit` hem middleware'de hem route'ta hem de farklı anahtarlama stratejileriyle kullanılıyor;
`_run_public_web_research` (bir *domain servisi*) HTTP katmanında yaşıyor; room şeması
sözlük anahtarlarıyla (`room["telemetry_delivery"]`, `room.setdefault("interventions", ...)`)
tanımlı olduğu için derleyici/tip denetleyicisi hiçbir tutarsızlığı yakalayamıyor. Yeni bir
endpoint eklemek için 2000 satırlık bir dosyada gezinmek gerekiyor — **SRP ve OCP ihlali.**

**Çözüm Önerisi** — `APIRouter` ile bölün:

```
backend/
  api.py                    # uygulama fabrikası + middleware + mount (<200 satır)
  routers/
    telemetry.py            # /api/telemetry, /ws/{client_id}
    tasks.py                # /api/initiate, /api/tasks/*
    vault.py                # /api/vault, /api/override
    aspasia.py              # /api/aspasia/*
    openai_compat.py        # /v1/*
    experimental.py         # /api/experimental/*
  core/
    rooms.py                # RoomStore (TypedDict/dataclass + eviction)
    telemetry_bus.py        # _room_sender / _enqueue / delivery durumu
    rate_limit.py           # RateLimiter sınıfı (Redis arayüzü arkasında)
  services/
    public_web_research.py  # _run_public_web_research buraya
```

Ve oda şemasını sözlükten tip'e taşıyın:

```python
@dataclass
class Room:
    executor: PinealExecutor
    vault: dict[str, Any]
    websockets: set[WebSocket] = field(default_factory=set)
    logs: deque[str] = field(default_factory=lambda: deque(maxlen=50))
    events: deque[Any] = field(default_factory=lambda: deque(maxlen=200))
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=2000))
    lifecycle: TaskLifecycleRegistry = field(default_factory=TaskLifecycleRegistry)
    interventions: deque[dict] = field(default_factory=lambda: deque(maxlen=100))
    last_seen: float = field(default_factory=time.monotonic)
```

Böylece `room["telemtry_delivery"]` gibi bir yazım hatası **test zamanında değil, import
zamanında** yakalanır.

---

### 🟡 P2-19 — DRY ihlalleri

| Tekrar | Konum |
|---|---|
| `_dump_field` iki kez **birebir aynı** tanımlı | `api.py:949-953` ve `api.py:1222-1226` |
| Görev başlatma bloğu (`_new_task_id` → `transition` → `create_task` → `mission_tasks` → `add_done_callback`) | `api.py:1280-1286` (`api_initiate`) ve `api.py:1547-1552` (`_aspasia_command_dispatch`) |
| `except TypeError: agent.execute(input_data)` imza tahmini | `task_executor.py:552` ve `:717` |
| Bütçe release kalıbı (`if budget_reserved: self._release_budget(...); budget_reserved = False`) | `llm_gateway.py` içinde **14 kez** |

**Çözüm Önerisi**

```python
# api.py — görev başlatmanın TEK yolu
def start_mission(client_id: str, req: InitiatePayload) -> str:
    room = get_room(client_id)
    task_id = _new_task_id()
    _lifecycle(room).transition(task_id, "processing")
    mission = asyncio.create_task(run_mission(req, task_id))
    room["mission_tasks"][task_id] = mission
    mission.add_done_callback(lambda _t: room["mission_tasks"].pop(task_id, None))
    return task_id

# llm_gateway.py — bütçe için context manager
@contextmanager
def _budget(self, call_id: str, amount: float):
    self._reserve_budget(call_id, amount)
    try:
        yield
    except BaseException:
        self._release_budget(call_id)
        raise
```

---

### 🟡 P2-20 — Küçük ama gerçek kod kokuları

| Konum | Sorun |
|---|---|
| `instagram_ghost.py:390` | `if "Login • Instagram" in html or 'name="username"' in html and 'name="password"' in html:` — `and`/`or` önceliği parantezsiz. Şu anki değerlendirme `A or (B and C)`; niyet `(A or B) and C` idiyse kod yanlış. En azından belirsiz. |
| `api.py:1036` | Çıplak `except:` — `KeyboardInterrupt`/`SystemExit`'i de yutar. |
| `api.py:857` | `print(f"[room_sender] hata: ...")` — `logger` yerine `print`; yapılandırılmış log altyapısını atlar. |
| `api.py:1839` | `import os` fonksiyon içinde (modül zaten import etmiş). |
| `api.py:1074` | `import uuid` fonksiyon içinde. |
| `task_executor.py:404` | `f"... {e}"` — exception mesajı doğrudan kullanıcı log'una (`redact_text`'ten geçiyor, ama yine de iç detay sızdırıyor). |
| `ruff.toml` | Yalnızca `E9` + `F` seçili. `S` (bandit), `B` (bugbear), `BLE`, `TRY`, `ASYNC` kuralları kapalı — bu raporun yarısı o kurallarla otomatik yakalanırdı. |
| `api.py:1115` | Cookie havuzundan seçim `random.choice` — "rotasyon" değil, **rastgele**. Aynı cookie arka arkaya seçilebilir; asıl amaç (Instagram rate-limit'ten kaçınmak) karşılanmıyor. Sıra tabanlı (`itertools.cycle`) ya da son-kullanım-zamanı tabanlı olmalı. |

---

## 5. Test Kapsamı

**Mevcut durum:** 806 geçen test, 2 atlama. Kapsam kapısı `--cov-fail-under=80`.
Bu, **nicelik olarak etkileyici** — ama denetimde bulunan 10 bulgunun **hiçbiri** mevcut
testlerce yakalanmıyor. Sorun kapsam yüzdesi değil, **kapsamın yanlış yerlere bakması.**

### 5.1 En tehlikeli desen: test edilen kod üretimde çalışmıyor

`evaluate_confidence` için 4 ayrı test var ve hepsi yeşil. Üretimde tek bir çağrı yok (P1-7).
`--cov-fail-under=80` bunu yakalamaz çünkü **fonksiyon test tarafından çağrıldığı için
kapsanmış sayılıyor.**

**Öneri:** kapsam kapısına **branch coverage** ekleyin ve kritik sözleşmeler için
"üretimden çağrılıyor mu" testleri yazın:

```ini
# ci.yml
pytest -q --cov=agent_core --cov=backend --cov-branch --cov-fail-under=80
```

```python
def test_anti_hallucination_gate_is_wired():
    src = (ROOT / "agent_core/services/platform_registry.py").read_text()
    assert "evaluate_confidence" in src, "güven kapısı üretim yoluna bağlanmamış"
```

### 5.2 Yazılması kritik, eksik test senaryoları

Aşağıdakilerin tamamı `tests/audit/test_production_audit_findings.py` içinde **çalışır durumda**
teslim edildi (19 test, hepsi `xfail` işaretli — bulgu kapatıldığında `XPASS`'e döner ve
işaretin kaldırılması gerektiğini söyler):

| # | Eksik senaryo | Neden kritik |
|---|---|---|
| 1 | `redact_structure` maliyeti: N string × M env değişkeni için çağrı sayısının **1** olması | Performans regresyonunun tek erken uyarısı |
| 2 | `ResponseCache`: TTL dolunca satırların **silinmesi** ve DB boyutunun küçülmesi | Disk sızıntısı |
| 3 | `get_room` ile dict olmayan `.pineal_vault.json` (4 varyant: list/null/str/int) | Tüm API'yi öldüren yol |
| 4 | `app.state.rooms` için eviction: N farklı `client_id` sonrası oda sayısının **sınırlı** kalması | OOM + maliyet DoS'u |
| 5 | `_rate_buckets` anahtar sayısının **sabit** kalması | Yavaş bellek sızıntısı |
| 6 | `extract_username` ile 6 profil-dışı URL (`/p/`, `/reel/`, `/explore/`, `/stories/`, `/accounts/`, kök) | Yanlış kişiye atıf |
| 7 | `evaluate_confidence`'ın üretim yolundan çağrılması | Ölü güvenlik kapısı |
| 8 | `_random_delay`'in senkron `time.sleep` **kullanmaması** | Event loop donması |
| 9 | `/api/override` bozuk/dict `learnings.json` ile 500 **döndürmemesi** | Kalıcı bozulma |
| 10 | `security_posture()` `PINEAL_ENV` yokken `auth_required=True` | Fail-open |

### 5.3 Bunlara ek olarak yazılması gerekenler

**Entegrasyon / eşzamanlılık**
- **Eşzamanlı 50 görev**: `asyncio.gather` ile 50 `execute_task` → `call_log` 500 sınırının
  doğru kırpıldığı, `_reserved_spend_usd`'nin **sıfıra döndüğü** (rezervasyon sızıntısı yok),
  oda kuyruğunun taşmadığı.
- **Event loop gecikme bütçesi testi**: bir heartbeat coroutine ile "herhangi bir 100 ms'lik
  pencerede loop bloke olmadı" iddiası. `redact_structure`, `cache.get` ve `_random_delay`
  bulgularının üçünü de otomatik yakalar.
- **`CanonicalMemory` çok süreçli yazma**: iki süreç aynı `task_id`'ye eşzamanlı yazdığında
  dosyanın bozulmadığı (şu an sabit `.tmp` adı bunu garanti etmiyor — bkz. 5.5).
- **WebSocket reconnect fırtınası**: aynı `client_id` ile 100 bağlantı → `room["websockets"]`
  kümesinin kapalı soketlerden temizlendiği.

**Hata enjeksiyonu**
- LLM provider 429/500/timeout döndürürken `run_mission`'ın **kaç deneme** yaptığı ve
  **toplam maliyetin** tavanı aşmadığı (şu an 3 pipeline × 3 gateway denemesi = 9).
- `asyncio.wait_for` timeout'unda iç görevin gerçekten iptal edildiği ve rezervasyonun iade edildiği.
- `broadcast_result_error`'ın `task_id=None` ile çağrıldığında yaşam döngüsünün hayalet
  "processing" kaydı bırakmadığı.
- Playwright `goto` timeout'unda tarayıcı/bağlam/sayfanın **kesinlikle** kapandığı
  (`finally` bloğu var ama test edilmiyor → sızıntı riski).

**Güvenlik**
- `PINEAL_ENV` matrisi: `{unset, development, staging, production, PROD, " production "}` ×
  `PINEAL_TOKEN {set, unset}` → beklenen `auth_required`. Şu an yalnızca birkaç kombinasyon testli.
- Proxy arkasında hız sınırı: `X-Forwarded-For` ile iki farklı gerçek istemcinin ayrı kovalarda
  olduğu; tek proxy IP'sinin tüm kullanıcıları kilitlemediği.
- `/ws/{client_id}` için **oda yaratma** hız sınırı (şu an `/ws/` auth middleware'deki hız
  sınırlamasının **kapsamı dışında** — yalnızca `/api/` ve `/v1/` kontrol ediliyor).

**Sözleşme / regresyon**
- `InitiatePayload` alanlarının gerçekten davranışa bağlı olduğu (repo'da `[037]` notu bu sınıf
  bir hatayı belgeliyor — aynı sınıfın tekrar oluşmasını engelleyen bir test yok).
- Telemetri şeması: `delivery_state` / `dropped_event_count` alanlarının her event'te bulunduğu.

### 5.4 CI iyileştirmeleri

```yaml
# ci.yml — mevcut adıma ek
- name: Lint (genişletilmiş kural seti)
  run: ruff check . --select E9,F,B,S,BLE,TRY,ASYNC,C4,PERF
- name: Branch coverage
  run: pytest -q --cov=agent_core --cov=backend --cov-branch --cov-fail-under=80
- name: Bellek sızıntısı kapısı
  run: pytest tests/audit -q --runxfail   # xfail'ler FAIL'e dönerse bilerek
```

`--runxfail` adımı, denetim bulguları kapatıldıkça **kırmızıya döner** — yani "bu bulguyu
kapattım" iddiası otomatik doğrulanır.

### 5.5 Denetim sırasında bulunan, test yazılamayan tek gerçek kusur

`CanonicalMemory._atomic_write` sabit geçici dosya adı kullanıyor:

```python
temp_file = f"{profile_file}.tmp"     # canonical_memory.py:106
```

Tek uvicorn worker'ında `asyncio.Lock` bunu koruyor. **Birden fazla replikada** (Railway/Vercel
yatay ölçekleme, ya da API + `scripts/run_task.py` eşzamanlı) iki süreç aynı `.tmp` dosyasına
yazar → **yırtık yazma / kanıt kaybı.** Çözüm:

```python
import tempfile
fd, temp_file = tempfile.mkstemp(dir=os.path.dirname(profile_file), prefix=".mem-", suffix=".tmp")
with os.fdopen(fd, "w", encoding="utf-8") as handle:
    handle.write(payload)
    handle.flush()
    os.fsync(handle.fileno())
os.replace(temp_file, profile_file)
```

---

## 6. Önceliklendirilmiş Kapanış Planı

| Sıra | Bulgu | Etki | Efor | Kanıt |
|---|---|---|---|---|
| 1 | **P2-10** fail-open auth | Açık OSINT API'si | ~15 dk | `security_posture()` çıktısı |
| 2 | **P0-1** redact O(N×M) | Event loop donması | ~45 dk | 13.60 s / 200 mesaj |
| 3 | **P0-4 + P0-5** rooms + rate buckets | OOM, maliyet DoS'u | ~2 sa | 300 room / 5000 bucket |
| 4 | **P0-3** dict olmayan vault | Tüm API 500 | ~15 dk | TypeError / AttributeError |
| 5 | **P0-2 + P0-6** cache prune + to_thread | Disk dolu, loop bloke | ~1.5 sa | 2084 KB sabit / 30.7 ms |
| 6 | **P1-8** `time.sleep` → `asyncio.sleep` | 2-5 sn tam donma | ~5 dk | kaynak okuması |
| 7 | **P1-6** `extract_username` doğrulama | Yanlış kişiye atıf | ~45 dk | 6 URL çıktısı |
| 8 | **P1-7** güven kapısını bağla | Halüsinasyon koruması yok | ~30 dk | grep çıktısı |
| 9 | **P2-9** learnings.json kurtarma | Kalıcı 500 | ~30 dk | JSONDecodeError |
| 10 | **P2-16** backoff + `task_id` sırası | 9× maliyet, hayalet görevler | ~1 sa | kod okuması |
| 11 | **P1-18** `api.py` bölme | Büyütülebilirlik | ~1 gün | 2014 satır |
| 12 | **P2-14** 14 sessiz `except` | Teşhis edilemezlik | ~2 sa | tarama çıktısı |

**Tavsiye:** 1-6 canlıya çıkmadan **mutlaka** kapanmalı (toplam ≈ yarım gün). 7-10 ilk sürüm
yamada. 11-12 teknik borç sprintinde.

---

## 7. Teslim Edilen Artefaktlar

| Dosya | İçerik |
|---|---|
| `PRODUCTION_AUDIT_2026-09-04.md` | Bu rapor |
| `tests/audit/test_production_audit_findings.py` | 10 bulgu için **19 yürütülebilir regresyon testi**, `xfail(strict=False)` işaretli — CI'ı kırmaz, bulgu kapatıldığında `XPASS` ile uyarır |

**Doğrulama:** `pytest -q` → `1 failed, 806 passed, 2 skipped, 19 xfailed`.
Tek başarısız test sandbox'ta `open-interpreter` kurulu olmadığı için; kod kusuru değil.
