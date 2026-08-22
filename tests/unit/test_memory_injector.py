import pytest
import os
import tempfile
import json
from agent_core.services.memory_injector import MemoryInjector

def test_fetch_active_rules_no_file():
    injector = MemoryInjector(memory_path="/tmp/does_not_exist_xyz123.json")
    result = injector.fetch_active_rules()
    assert result == ""

def test_fetch_active_rules_empty_file():
    with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
        json.dump([], f)
        temp_name = f.name
    
    try:
        injector = MemoryInjector(memory_path=temp_name)
        result = injector.fetch_active_rules()
        assert result == ""
    finally:
        os.remove(temp_name)

def test_fetch_active_rules_with_rules():
    rules = [
        {"hash": "123", "tag": "KURAL1", "fact": "Rule 1 content"},
        {"hash": "123", "tag": "KURAL1", "fact": "Rule 1 duplicate"}, # Should deduplicate
        {"tag": "KURAL2", "fact": "Rule 2 content"}, # No hash
    ]
    with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as f:
        json.dump(rules, f)
        temp_name = f.name
        
    try:
        injector = MemoryInjector(memory_path=temp_name)
        result = injector.fetch_active_rules()
        
        assert "=== KUTSAL KURALLAR (OVERRIDE) ===" in result
        assert "- [KURAL1] Rule 1 content" in result
        assert "- [KURAL1] Rule 1 duplicate" not in result # Deduplicated out
        assert "- [KURAL2] Rule 2 content" in result
    finally:
        os.remove(temp_name)
