"""
P1.7 — Pydantic V2 Migration
Kullanımdan kalkan (deprecated) .dict() ve .json() metodlarının
üretim kodunda kullanılmadığını kanıtlayan test.
"""
import ast
import inspect
import pytest
from pathlib import Path

from agent_core.agents import resonance_calculator
from agent_core.shadow import shadow_executor

def test_no_pydantic_deprecated_dict_or_json():
    """
    Pydantic V2'de .dict() ve .json() deprecated'dir (kullanımdan kalkmıştır).
    Yerine .model_dump() ve .model_dump_json() kullanılmalıdır.
    """
    modules_to_check = [resonance_calculator, shadow_executor]
    
    for module in modules_to_check:
        src = inspect.getsource(module)
        # Sadece yorum olmayan ve doğrudan çağrılan .dict() / .json() ları yakalamak için AST de kullanabiliriz,
        # ama basit bir string araması da (eğer doğru formatlanmışsa) iş görür.
        # Daha güvenli olması için kod satırlarını tarayalım:
        for i, line in enumerate(src.splitlines()):
            # Yorumları ve string'leri göz ardı etmek için basit kontrol:
            clean_line = line.split('#')[0].strip()
            if '.dict(' in clean_line:
                pytest.fail(f"GÜVENLİK/V2 İHLALİ: {module.__name__} satır {i+1} içinde deprecated '.dict()' bulundu: {clean_line}")
            if '.json(' in clean_line and 'model_dump_json' not in clean_line:
                # requests response'larında .json() olabilir. 
                # Ama bizim modüllerde (resonance ve shadow) sadece Pydantic nesneleri dönüyor.
                pytest.fail(f"GÜVENLİK/V2 İHLALİ: {module.__name__} satır {i+1} içinde deprecated '.json()' bulundu: {clean_line}")
