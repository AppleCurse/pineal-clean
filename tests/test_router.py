import pytest
import asyncio
from agent_core.task_executor import PinealExecutor, InsufficientEvidenceError

@pytest.mark.asyncio
async def test_cognitive_router_halt():
    executor = PinealExecutor()
    
    # Mock uncertainty engine to return low confidence
    class MockUncertainty:
        from pydantic import BaseModel
        class UR(BaseModel):
            is_suspicious: bool = False
            confidence: float = 0.5
            reason: str = "Mocked low confidence"
            
        def evaluate(self, result, agent_name):
            return self.UR(confidence=0.5)

    executor.uncertainty = MockUncertainty()
    
    # Mock LLMGateway to avoid requiring real API keys
    class MockLLMGateway:
        async def query(self, *args, **kwargs):
            return "mock"
        async def query_json(self, *args, **kwargs):
            from pydantic import BaseModel
            class DummyResult(BaseModel):
                message: str = "mock"
            return DummyResult()
            
    executor.llm_gateway = MockLLMGateway()

    task_input = {
        'user_profile': {'private_rituals': ['mock']},
        'target_profile': {'posts': ['mock data']}
    }
    
    status = await executor.execute_task(task_input, "test_task")
    assert status.status == "halted_evidence"
