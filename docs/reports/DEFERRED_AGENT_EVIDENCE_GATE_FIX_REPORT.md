# Düzeltme Raporu — Deferred Agent Evidence Gate

**Durum:** Uygulandı ve test edildi  
**Kapsam:** Büyük sorun 2/5 — Deferred ajanların evidence/uncertainty bypass etmesi

## Sorun

`pattern_interrupt` ve `resonance_synthesizer`, bağımlılıkları tamamlandıktan sonra çalıştırılmak üzere deferred kuyruğa alınıyordu. Ancak eski deferred döngü:

- `BaseModel` çıktı sözleşmesini doğrulamıyordu;
- `UncertaintyEngine.evaluate()` çağırmıyordu;
- minimum confidence eşiğini uygulamıyordu;
- graceful-degradation / critical-agent politikasını ana döngüden farklı uyguluyordu;
- tamamlanan adım eventini yayımlamıyordu.

Bu nedenle sıralama amaçlı bir kuyruk, kanıt güvenliği bypass’ına dönüşüyordu.

## Uygulanan değişiklik

Dosya: `agent_core/task_executor.py`

Deferred döngü artık ana ajan döngüsü ile aynı evidence sözleşmesini uygular:

```python
if not isinstance(result, BaseModel):
    raise TypeError(agent_name + " gecersiz cikti: " + str(type(result)))

check = self.uncertainty.evaluate(result, agent_name)
if check.confidence < agent_cfg.min_llm_confidence:
    run.status = "halted"
    run.error_code = "LOW_CONFIDENCE"
    continue
```

Ayrıca:

- tanınmayan agent adı açık hata verir;
- non-critical hata/low-confidence durumunda `failed` veya `halted` agent run kaydı tutulur ve pipeline policy’ye göre devam eder;
- critical veya graceful-degradation kapalıysa pipeline `halted_critical` olur;
- yalnızca doğrulanmış, confidence eşiğini geçen sonuç evidence chain’e yazılır;
- başlangıç (`TaskStartedEvent`) ve tamamlanma (`StepCompletedEvent`) eventleri yayımlanır;
- run confidence, çıktıdaki self-reported sayı yerine `UncertaintyEngine` tarafından hesaplanan değerden gelir.

## Eklenen regresyon testleri

Dosya: `tests/unit/test_deferred_agent_evidence_gate.py`

1. Low-confidence deferred sonuç `halted` olur ve evidence chain’e girmez.
2. `BaseModel` olmayan deferred çıktı `failed` olur ve evidence chain’e girmez.
3. Her iki durumda da non-critical agent için final durum `PARTIALLY_COMPLETED` olur; sahte başarı üretilmez.

## Doğrulama

```text
8 passed: hedefli deferred/executor integration testleri
234 passed: tam test paketi
```

## Sonraki çalışma

Büyük sorun 3/5: Deep research akışının asıl agent output’unu `VerifiedNote` ile ezmesini önlemek; ilk bulgu, şüphe gerekçesi ve doğrulama çıktısını ayrı, provenance’lı evidence kayıtları olarak saklamak.
