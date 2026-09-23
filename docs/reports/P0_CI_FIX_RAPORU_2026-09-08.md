# P0 — CI REGRESYON FİX RAPORU (2026-09-08)

## Commit

- **SHA:** `1ce27343724d70f8815c7fd2a5f74fd56c56c3c7` (`1ce27343`)
- **Branch:** `arena/01a07f2a-pineal-clean` (HEAD; parent `85839da`)
- **Mesaj:** `fix(ci): repair ruff lint and rust purity_scan gates broken since 024c82b0`
- **Kapsam:** 2 dosya, +37/−4. Mimari/merge, UI etiket senkronu, config kalıntılarına **dokunulmadı**.

## Ne değişti

### 1) Backend lint — `tests/unit/test_llm_gateway_rtk_integration.py`
Dosyanın tamamı okunarak teyit edildi (kör silme değil):
- `_RTK_POLICY_PATH` importu kaldırıldı — dosyada yalnız **string** olarak `monkeypatch.setattr("agent_core.services.llm_gateway._RTK_POLICY_PATH", ...)` (satır 23/37/122) geçiyor; import nesnesi hiç kullanılmıyor.
- `from pathlib import Path` kaldırıldı — dosyada hiç kullanılmıyor.
- 10/10 test hâlâ PASS (`pytest tests/unit/test_llm_gateway_rtk_integration.py`).

### 2) Rust purity kapağı — `rust_core/tests/purity_scan.rs`
- **Seçenek (b)** uygulandı (gerekçe: Python'daki simetrik test `test_token_compressor_purity.py` AST tabanlıdır — yorumları ve test bölgesini asla saymaz; (c) `syn` sandbox'ında crates.io erişimi olmadığı için kullanılamazdı ve bu dosya için ağırlıktı; (a)'nın kaba kesmesi tek başına satır 39'daki doküman yorumunu hâlâ yakalardı, o yüzden (b): `//` yorum temizliği + `#[cfg(test)]` bölgesi hariç tutma).
- Yeni sözleşme, Python mirror'u ile birebir hizalı:
  1. `#[cfg(test)]` başlangıcından itibaren her şey tarama **DIŞI** (test-only `use std::fs;` artık meşru — testler ayrı dosya/durumdur).
  2. `//` satır yorumları (//! doküman yorumları dahil) tarama **DIŞI**.
  3. Bu ikisinin dışında kalan **üretim bölgesinde** yasak belirteç → test KIRMIZI. Yasak listesi aynen korundu.

## Mutasyon kayıtları (canlı, sonra geri alındı)

### Backend (ruff):
| Mutasyon | Sonuç |
|---|---|
| `_RTK_POLICY_PATH` importu geri ekle | `ruff` exit 1, `F401` yakalandı → **KIRMIZI** ✓ |
| Geri al (temiz) | `ruff check .` exit 0, "All checks passed!" → **YEŞİL** ✓ |

### Rust purity (Python replica — birebir aynı tarama algoritması; sandbox'ta rustc yok, doğrulama CI'da `cargo test --locked` ile):
| Mutasyon | Sonuç |
|---|---|
| Temiz kaynak (mevcut `#[cfg(test)] use std::fs` + doküman yorumu) | hit yok → **YEŞİL** ✓ |
| Üretim bölgesine gerçek `let _ = std::fs::read_to_string("/tmp/x");` ekle | `std::fs` yakalandı → **KIRMIZI** ✓ |
| Üretim bölgesine `use std::fs;` ekle | `std::fs` yakalandı → **KIRMIZI** ✓ |

Yani test hem "gerçek üretim `std::fs` kullanımı KIRMIZI" hem de "test-only kullanım + yorumlar YEŞİL" koşulunu kanıtlıyor.

## CI sonucu

- **Run:** https://github.com/AppleCurse/pineal-clean/actions/runs/34186848237 (id `34186848237`, başlık = fix commit)
- **Sonuç: 5/5 YEŞİL** — `frontend: success`, `backend: success`, `rust-core: success`, `android: success`, `smoke: success` (run conclusion `success`).
  - `rust-core` job'ındaki **"Cargo test"** adımı CI'da geçti (yerelde toolchain indirilemediği için `cargo test --locked` yalnız CI'da koştu — aynı komut).
  - `backend` job'ı başarılı = `ruff check .` **ve** `pytest --cov-fail-under=80` CI'da geçti. (Job log-blob'u bu sandbox'tan erişilemediği için CI içi satır sayısı çekilemedi; job-level conclusion yetkili.)
  - `smoke` artık çalıştı (önceki kırmızı run'larda `needs: [backend]` yüzünden skip ediliyordu).

## Tam test paketi sayıları

Yerel (CI backend job'ının birebir komutu: `pytest -q -p no:cacheprovider --cov=agent_core --cov=backend --cov-report=term-missing:skip-covered --cov-fail-under=80`):

| Ölçüm | Önce (85839da, bu fix'ten önceki denetim) | Sonra (1ce27343) | Sapma |
|---|---|---|---|
| passed | 1089 | **1089** | 0 |
| skipped | 3 | **3** | 0 (crawl4ai ×2 + PIL None-dalı — env koşullu, CI ile tutarlı) |
| coverage | 85.68% | **85.68%** | 0 |
| ruff | exit 1 (2 F401) | **exit 0** | düzeldi |
| tests/audit | 84/84 | 84/84 | 0 |
| frontend check/build | PASS | değişmedi (dokunulmadı) | — |

Sapma yok: fix yalnız iki test/kapı dosyasındaki kullanılmayan import ve tarama sözleşmesini düzeltti; üretim kodu ve test davranışı değişmedi (1089 sayısının birebir korunması bunun kanıtıdır).
