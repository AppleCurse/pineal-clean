# Düzeltme Raporu — Sahte Authentic Vector Engeli

**Durum:** Uygulandı ve test edildi  
**Kapsam:** Büyük sorun 1/5 — LLM başarısızlığında sahte sayısal vektör üretimi

## Sorun

Önceki akış, authentic-vector LLM çağrısı hata verdiğinde aşağıdaki kararı verilebilir sahte veriyi üretiyordu:

```python
{"depth": 0.5, "energy": 0.5, "achilles_heel": "Bilinmiyor", ...}
```

`ResonanceCalculator` da kullanıcı vektörü hiç yoksa ikinci bir default kullanıyordu:

```python
{"depth": 0.9, "energy": 0.3}
```

Bu iki davranış, verinin bulunmadığı bir durumda rezonans/uyum kararı verilmesine neden olabiliyordu.

## Uygulanan değişiklikler

### 1. Hesaplanamayan vector artık `None`

Dosya: `agent_core/task_executor.py`

```python
except Exception as e:
    self._log("WARNING", "Vektör hesaplanamadı; veri kullanılamaz olarak işaretlendi: ...")
    return None
```

Sayısal fallback tamamen kaldırıldı.

### 2. Veri yokluğu explicit olarak kaydediliyor

Dosya: `agent_core/task_executor.py`

```python
input_data["user_authentic_vector_status"] = {
    "available": False,
    "reason": "AUTHENTIC_VECTOR_UNAVAILABLE",
}
```

Eski/sahte `user_authentic_vector` veya `target_authentic_vector` anahtarı siliniyor. Böylece önceki bir çalışmadan kalma vektör de yanlışlıkla kullanılamaz.

### 3. ResonanceCalculator artık kullanıcı default’u kullanmıyor

Dosya: `agent_core/agents/resonance_calculator.py`

```python
user_vector = input_data.get("user_authentic_vector")
if not self._has_required_dimensions(user_vector):
    raise ResonanceCalculationError(
        "Kullanıcı authentic vector'u mevcut değil; rezonans hesaplanamaz."
    )
```

Bu durumda skor, öneri veya frekans kararı üretilmez. Executor bunu gerçek bir ajan hatası olarak kaydeder; mevcut konfigürasyonda `resonance_calc` kritik olmadığı için görev `partially_completed` olur, ancak uydurma rezonans sonucu üretmez.

### 4. Boş hedef analizi üzerinden sentetik hedef vector üretimi engellendi

Önceden `{}` gibi boş bir target analysis metne çevrilip varsayımsal kelime istatistikleri üzerinden sayı üretebiliyordu. Artık:

```python
raise ResonanceCalculationError(
    "Hedef için ölçülebilir vektör veya analiz verisi yok; rezonans hesaplanamaz."
)
```

## Eklenen regresyon testleri

Dosya: `tests/unit/test_authentic_vector_unavailable.py`

1. Provider hatasında `None` dönmesini doğrular.
2. `None` vektörün açık `UNAVAILABLE` metadata’sına dönüşmesini doğrular.
3. Kullanıcı vektörü yokken ResonanceCalculator’ın default kullanmak yerine hata vermesini doğrular.
4. Boş target analysis için sentetik hedef vektör üretilemediğini doğrular.

Var olan executor–resonance integration testi de gerçek hesaplayıcıyı korur; yalnızca bu testin kapsadığı wiring için açık test vektörleri sağlar. Production davranışı için fallback eklenmemiştir.

## Doğrulama

```text
15 passed: hedefli regresyon + resonance + P0 + task-executor flow testleri
232 passed: tam test paketi
```

## Sonraki dört büyük çalışma

1. Deferred ajanları ana uncertainty/evidence gate’inden geçirmek.
2. 7-pillar failure’ını final pipeline statüsünde görünür ve policy-controlled yapmak.
3. Deep-research sonucunu asıl ajan output’unu ezmeden ayrı, provenance’lı evidence olarak kaydetmek.
4. Hard-coded confidence değerlerini (`0.85`, `0.7`, `0.9`, `0.5`) ölçülebilir veya explicit unavailable semantics ile değiştirmek.
