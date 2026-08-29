"""
P1.6 — Interpreter Registry ve Agent KeyError testi.

PinealExecutor'ın agent registry'sini test eder:
1. InterpreterAgent VARSAYILAN olarak registry'de YOK (SEC FIX: kod-icra
   yüzeyi ana pipeline'dan izole edildi; ENABLE_INTERPRETER=true ile yüklenir).
2. ENABLE_INTERPRETER=true iken 'interpreter' adıyla kaydedilir.
3. Bilinmeyen bir agent çağrıldığında KeyError fırlatılıyor mu?
"""
import pytest
from unittest.mock import patch

from agent_core.task_executor import PinealExecutor
from agent_core.agents.interpreter_agent import InterpreterAgent
from agent_core.services.cognitive_router import RoutePlan

def test_executor_does_not_register_interpreter_by_default(monkeypatch):
    """Varsayılan (ENABLE_INTERPRETER tanımsız/false): interpreter registry'de olmamalı."""
    monkeypatch.delenv("ENABLE_INTERPRETER", raising=False)
    executor = PinealExecutor()
    assert "interpreter" not in executor.agents, (
        "interpreter varsayılan registry'de olmamalı (ENABLE_INTERPRETER kapısı)"
    )

def test_executor_registers_interpreter_agent_when_enabled(monkeypatch):
    """ENABLE_INTERPRETER=true iken InterpreterAgent 'interpreter' anahtarıyla kaydedilmeli."""
    monkeypatch.setenv("ENABLE_INTERPRETER", "true")
    executor = PinealExecutor()
    assert "interpreter" in executor.agents, "'interpreter' registry'de bulunamadı"
    assert isinstance(executor.agents["interpreter"], InterpreterAgent), "'interpreter' bir InterpreterAgent değil"

@pytest.mark.asyncio
async def test_router_never_schedules_interpreter_in_main_route():
    """[SEC FIX] Ana rota, kullanıcı verisi olsa bile interpreter'ı planlamamalı."""
    from agent_core.services.cognitive_router import CognitiveRouter
    route = await CognitiveRouter().analyze({
        "user_profile": {"private_rituals": ["çay"]},
        "target_profile": {"bio": "hedef"},
    })
    assert "interpreter" not in route.agents

@pytest.mark.asyncio
async def test_executor_raises_keyerror_for_unknown_agent():
    """Kayıt dışı agent için execute_task KeyError ('Bilinmeyen yetenek') fırlatmalı."""
    executor = PinealExecutor()
    
    # CognitiveRouter.analyze mock'lanarak bilinmeyen bir agent ('unknown_agent') döndürsün
    mock_route = RoutePlan(agents=["unknown_agent"], reasoning="Test", priority=1)
    
    with patch.object(executor.router, "analyze", return_value=mock_route):
        with pytest.raises(KeyError) as exc_info:
            await executor.execute_task({"task": "test"}, "task_id_123")
            
        assert "Bilinmeyen yetenek: unknown_agent" in str(exc_info.value)
