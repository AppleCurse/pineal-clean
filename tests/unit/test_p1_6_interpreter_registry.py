"""
P1.6 — Interpreter Registry ve Agent KeyError testi.

PinealExecutor'ın agent registry'sini test eder:
1. InterpreterAgent 'interpreter' adıyla executor'a kaydedilmiş mi?
2. Bilinmeyen bir agent çağrıldığında KeyError fırlatılıyor mu?
"""
import pytest
from unittest.mock import MagicMock, patch

from agent_core.task_executor import PinealExecutor
from agent_core.agents.interpreter_agent import InterpreterAgent
from agent_core.services.cognitive_router import RoutePlan

def test_executor_registers_interpreter_agent():
    """InterpreterAgent 'interpreter' anahtarıyla registry'de olmalı."""
    executor = PinealExecutor()
    assert "interpreter" in executor.agents, "'interpreter' registry'de bulunamadı"
    assert isinstance(executor.agents["interpreter"], InterpreterAgent), "'interpreter' bir InterpreterAgent değil"

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
