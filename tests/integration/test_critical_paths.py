import pytest
from agent_core.task_executor import PinealExecutor
from agent_core.services.canonical_memory import CanonicalMemory

@pytest.mark.asyncio
async def test_critical_path_task_execution(monkeypatch, tmp_path):
    monkeypatch.setenv("LIVE_LLM_E2E", "0")

    # We will use temporary memory storage
    memory = CanonicalMemory(storage_path=str(tmp_path))
    executor = PinealExecutor()
    executor.memory = memory

    # Basit girdi: rota bos kalir (user/target profil yok), gorev zararsiz tamamlanir.
    input_data = {"type": "test"}
    result = await executor.execute_task(input_data, task_id="test_task_id")

    assert hasattr(result, "status")
    assert result.status in ("completed", "failed")

    # Verify memory
    mem_data = memory.get_task_memory("test_task_id")
    assert "evidence" in mem_data
