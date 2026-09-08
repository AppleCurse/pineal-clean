# PINEAL — stepB_port.patch ENTEGRASYON RAPORU (2026-09-08)

## Commit

- **SHA:** `456849826d81e948e3fca5fafb6de785057cd12a` (`45684982`)
- **Branch:** `arena/01a07f2a-pineal-clean` (HEAD; parent `61830c99`)
- **Mesaj:** `feat(routing): single-source routing snapshot + generated UI/RUNBOOK shadows`
- **Kapsam:** 7 dosya (+494/−18). Merge kararı / `decision_config.yaml` / `interpreter_agent.py:37` sabit modeline **dokunulmadı**.

## Patch uygulaması — çakışma var mıydı?

`stepB_port.patch` dosyası bu sandbox'ta fiziksel olarak yoktu (yalnız içerik mesajda verildi), bu yüzden `git apply --check` yerine içerik **birebir** elle uygulandı: `llm_gateway.py`'ye `effective_routing_snapshot()` + 2 yardımcı (ekleme noktası `capable_chain` sonu / `__init__` öncesi — patch bağlamıyla **birebir aynıydı, çakışma yok**), `config/agent_tiers.json`, `scripts/generate_routing_shadows.py`, `tests/unit/test_routing_shadows.py` yeni dosya olarak. Söz dizimi/ruff doğrulandı; davranış farkı yok.

## Manuel 3 adım sonucu

1. **Svelte marker + üretici:** `// <ROUTING-GENERATED-START/END>` marker'ları eklendi, script çalıştırıldı. **Karşılaştırma (üretici ↔ benim `61830c99` elle fix'im):** 13 ajandan **12'sinde birebir aynı** (primary/backup/via). **Tek fark: `osint_investigator` `via` alanı** — benim fix'imde `xai/tools` idi, üretici `openrouter` yazdı (snapshot baz-fallback kuralı; canlı `run.via` UI'da öncelikli). Bu, task'ta söylenen "üreticinin yakaladığı 1 ek hata" — benim kontrat testim `via`'yı kapsamıyordu, o yüzden bende kaçmıştı. Kod-gerçeği kazanır; fark işaretlendi. (Kozmetik: sütun hizalaması `85839da` kaynak satırından geldiği için birkaç satırda benim elle hizalamamdan farklı — değerler aynı, `svelte-check` temiz.)
2. **RUNBOOK marker + üretici:** `<!-- ROUTING-GENERATED-START/END -->` "Routing zinciri" bölümünün precedence kısmını sardı; üretici precedence + 18 ajan tablosu + tier ihlallerini yazdı. Elle doküman (sağlayıcı merdiveni / fiyat muhasebesi / bilinçli redler) marker dışında **korundu** (üretici onları üretmiyor — içeri alınsaydı silinirdi).
3. **CI kapısı:** `ci.yml` backend job'una "Verify routing shadows committed fresh" adımı (`python scripts/generate_routing_shadows.py` + `git diff --exit-code`), coverage adımından sonra.

## Senin kontrat testin (test_frontend_agent_model_contract.py)

**Değişikliksiz kaldı** ve üretilen yeni gölgelerle **geçiyor** (test SoT'yi canlı okuyor; üretici de aynı SoT'den ürettiği için uyum kanıtlandı). İki kapı tamamlayıcı: üretici "tutarlılık" (üretici doğru çalışıyor), benim test "doğruluk" (üretilen değer SoT ile eşleşiyor).

## Mutasyon (kendi ağacında tekrar — kopyala-yapıştır değil)

| Mutasyon | Kapı | Sonuç |
|---|---|---|
| M-B1: `agent_tiers.json`'dan `passion_mapper` tier'i silindi | `test_every_routed_agent_has_tier` | **KIRMIZI** (`untiered: passion_mapper`) |
| M-B2: svelte `passion_mapper` primary'si `claude-sonnet-5`'e bozuldu | `test_committed_shadows_match_fresh_generator_output` (--check exit 3 "BAYAT") **ve** kontrat testi | **KIRMIZI** (ikisi de) |
| Geri al (temiz) | 10/10 | **YEŞİL** |

İlk M-B2 denememde replace deseni boşluk sayısı yüzünden eşleşmedi (sahte yeşil) — desen sağlamlaştırılıp gerçek mutasyonla tekrarlandı.

## CI sonucu — 5/5 YEŞİL

Run: https://github.com/AppleCurse/pineal-clean/actions/runs/34192066152 → `frontend ✓ · backend ✓ · rust-core ✓ · android ✓ · smoke ✓`. Backend job'ında yeni "routing shadows fresh" kapısı da geçti (commit'li gölgeler taze).

## Tam suite

Yerel (CI'ın birebir komutu): **1099 passed, 3 skipped, %85.68** — önceki referans 1091/3/%85.68 → **+8** (yalnız yeni `test_routing_shadows`), skipped değişmedi, coverage sapmasız (+51 satır/+8 missed = aynı oran). `ruff check .` temiz, `npm run check` 0 hata, `npm run build` temiz.

İdempotence: üretici iki kez çalıştırıldı → ikincisi "taze ✅", `--check` exit 0 (bayt-kararlı).
