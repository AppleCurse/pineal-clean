# PİNEAL ADLİ DİRİLİŞ VE TEMİZLİK GÜNLÜĞÜ (CANLI TAKİP)

**Tarih:** 2026-08-28 (BÜYÜK OPERASYON)  
**Durum:** 🟢 P0, P1 ve P2 Siber & Mimari Açıklar Kapatıldı! 

---

## 🎯 4 AŞAMALI HAREKÂT PLANI VE GERÇEK İLERLEME

| Aşama | Kapsam | Durum | Tamamlanan Somut Değişiklik |
|---|---|---|---|
| **1. SSRF & OOM Zırhı (P0)** | `human_behavior.py` | ✅ TAMAMLANDI | Görüntü indirme rutinine DNS çözümleme eklendi. Localhost, Private, Link-local IP'ler (`10.x.x.x`, `192.168.x.x`) engellendi. Stream üzerinden max byte limiti (10MB) ve manual redirect takibi ile sızıntılar kapatıldı. |
| **2. Auth & Session Çeliği (P1)** | `api.py` | ✅ TAMAMLANDI | `PINEAL_REQUIRE_AUTH=true` desteği getirildi. Token yoksa API kendini kilitliyor. WebSocket için `Authorization` header eklendi, query string'den sızıntı önlendi. Queue drop telemetry (`dropped_events`) aktif. |
| **3. Bilimsel Kontrat (P1/P2)** | `human_behavior.py`, `shadow_executor.py` | ✅ TAMAMLANDI | `DigitalColdReading` şeması baştan yazıldı. Sistemin "Aşil Tendonu" gibi kaba teşhisler koyması engellenerek `observations`, `possible_interpretations` ve `alternative_interpretations` (Hipotez) yapısına geçirildi. |
| **4. Heuristic Kalibrasyon (P2)** | `human_behavior.py` | ✅ TAMAMLANDI | Fotoğraf gerginliği `visual_edge_density` olarak değiştirildi. "Pasif dil kullanımı = kontrol kaybı" kuralının `0.85` olan ağırlığı `0.30`'a çekildi ve adı `passive_voice_observation` yapıldı. |
| **5. CI/CD Uyumu** | `tests/` dizini | ✅ TAMAMLANDI | Değişen Pydantic şeması nedeniyle kırılacak olan tüm `tests/unit` ve `tests/integration` dosyaları Regex ile onarıldı. |

---

## 🔴 2026-09-03 — KIRMIZI HÜKÜMLERİN YENİDEN ÖLÇÜMÜ + G7 MEKANİZMA ONARIMI

**Kapsam:** `INDEPENDENT_FORENSIC_AUDIT.md` + `REPORT_CROSS_VALIDATION.md` + `SON_HUKUM_DENETIM.md` içindeki kırmızı satırlar `f1e4602` (main, #59) üzerinde **yeniden koşuldu**; yalnız kanonik-ötesi (mekanizma) açık kapatıldı.

| # | Kırmızı madde | Ölçüm / İşlem | Sonuç |
|---|---|---|---|
| 1 | 2 bayat `test_human_behavior` assertion → "CI backend kırmızı" | `pytest -q` | ✅ **723 passed, 2 skipped** — hüküm BAYAT |
| 2 | Kalite kapısı coverage ≥ %80 | `--cov=agent_core --cov=backend` | ✅ **%84.13** |
| 3 | Lint | `ruff check .` | ✅ All checks passed! |
| 4 | CI (backend·frontend·rust·android·smoke) | main run `33694988566` | ✅ success |
| 5 | **G7-A: `Release Gates` workflow'u dispatch listesinde yok** | `.github/workflows/release-gates.yml` işlendi (gövde `release/` ile birebir) + `tests/unit/test_release_gates_workflow.py` (7 test); **PR #60 squash-merge `68fa552`** → `gh workflow list` artık `Release Gates active` (id 349137796) gösteriyor | ✅ **KAPANDI** — kök neden yerleşimdi, dispatch listesi doğrulandı |
| 6 | G7-A: yeşil koşu kaydı | dispatch denendi: `gh workflow run release-gates.yml --ref main` → **403** (agent token'ında Actions-write yok). `gh secret list` → 403 (secret varlığı doğrulanamıyor); sandbox dış ağ kapalı (`openrouter.ai` → `000`) → yeşil koşu **üretilmedi ve uydurulmadı** | 🔴 **AÇIK · NOT_EXECUTED — OPERATÖR** |
| 7 | G7-B: Docker + Chromium smoke | sandbox'ta docker daemon yok; IG initiate ağ/çerez bağımlı; workflow'un kendisi artık koşulabilir durumda | 🔴 **AÇIK · NOT_EXECUTED — OPERATÖR** |
| 5 | **G7-A: `Release Gates` workflow'u dispatch listesinde yok** | `.github/workflows/release-gates.yml` işlendi (gövde `release/` ile birebir) + `tests/unit/test_release_gates_workflow.py` (7 test) | ✅ **mekanizma kapandı** — merge sonrası dispatch edilebilir |
| 6 | G7-A: yeşil koşu kaydı | `gh run list --workflow "Release Gates"` → 0 kayıt; `gh secret list` → 403 (secret varlığı doğrulanamıyor); sandbox dış ağ kapalı (`openrouter.ai` → `000`) | 🔴 **AÇIK — OPERATÖR** |
| 7 | G7-B: Docker + Chromium smoke | sandbox'ta docker daemon yok; IG initiate ağ/çerez bağımlı | 🔴 **AÇIK — OPERATÖR** |

**Bilinçli yapılmayanlar:** `release/release-gates.yml` silinmedi (kanonik kaynak olarak durur; test eşitliği zorunlu kılar). Gate A/B için "koşuldu" iddiası üretilmedi — dispatch yetkisi/secret/docker bu ortamda yok ve raporda sahte yeşil bırakmak, denetimin kendi dürüstlük sözleşmesini ihlal ederdi.

**Operatör tek adım (Gate A/B kapatma):** PR merge → `Actions → Release Gates → Run workflow (main)` → iki job yeşil + run URL'sini `RELEASE_EVIDENCE.md` §12'ye işlemek; Gate B için ayrıca yerelde `docker compose up --build` → `POST /api/initiate` (IG) → WS scrape logu.
