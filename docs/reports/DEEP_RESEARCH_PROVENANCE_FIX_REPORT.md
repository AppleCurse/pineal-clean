# Düzeltme Raporu — Deep Research Provenance

**Durum:** Uygulandı ve test edildi  
**Kapsam:** Büyük sorun 3/5 — Deep research sonucunun asıl ajan çıktısını ezmesi

## Sorun

Şüpheli bir ajan sonucu için eski akış şunu yapıyordu:

```python
result = await self._deep_research(input_data, result, agent_name)
```

`_deep_research()` bir `VerifiedNote` döndürdüğü için bu atama, ajan çıktısının tipini ve içeriğini kaybediyordu. Sonraki adımlar `result` değerini normal ajan çıktısı kabul ederek input/evidence zincirine yazıyordu. Böylece:

- orijinal bulgu kaybolabiliyordu;
- şüphe nedeni zincirde yer almıyordu;
- doğrulama notu hangi ajanın sonucuna ait olduğu belirsiz kalıyordu;
- downstream ajanlar typed çıktı yerine `VerifiedNote` tüketebiliyordu.

## Uygulanan değişiklik

Dosya: `agent_core/task_executor.py`

Deep research artık özgün çıktıyı ve uncertainty raporunu girdi olarak alır:

```python
research_note = await self._deep_research(result, check, agent_name)
```

Orijinal `result` asla yeniden atanmaz. Bu nedenle downstream input’lara her zaman kaynak ajanın typed output’u yazılır.

Evidence chain iki ayrı, provenance’lı kayıt alır:

```python
{
    "agent": "human_behavior",
    "evidence_type": "agent_output",
    "result": {"...": "orijinal ajan çıktısı"},
    "uncertainty": {"reason": "...", "confidence": 0.9}
}

{
    "agent": "deep_research",
    "source_agent": "human_behavior",
    "evidence_type": "verification_note",
    "result": {"note": "ayrı doğrulama notu"},
    "uncertainty": {"reason": "...", "confidence": 0.9}
}
```

Bu yapı ana ve deferred ajan akışlarının ikisinde de uygulanır.

## Regresyon doğrulaması

`tests/integration/test_task_executor_flow.py` içindeki şüpheli araştırma testi genişletildi:

- `target_analysis` alanının `VerifiedNote` değil orijinal typed output olduğunu doğrular;
- orijinal evidence’in `agent_output` tipinde olduğunu doğrular;
- uncertainty gerekçesinin kaydedildiğini doğrular;
- deep-research kaydının ayrı `verification_note` olduğunu ve `source_agent` taşıdığını doğrular.

## Sonraki çalışma

Büyük sorun 4/5: 7-pillar failure’ını final pipeline statüsünde görünür ve policy-controlled hale getirmek.
