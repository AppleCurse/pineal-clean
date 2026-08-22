import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import BaseModel
from datetime import datetime, timezone
from agent_core.task_executor import PinealExecutor
from agent_core.domain.memory_models import TaskSnapshot
from agent_core.task_executor import InsufficientEvidenceError

class DummyResult(BaseModel):
    compatibility_score: float = 0.9

class DummyCheck(BaseModel):
    confidence: float
    is_suspicious: bool
    reason: str = ""

@pytest.fixture
def mock_router():
    router = MagicMock()
    # RoutePlan expects agents as a list
    class DummyRoute:
        agents = ["human_behavior", "mirror_truth", "resonance_calc"]
    router.analyze = AsyncMock(return_value=DummyRoute())
    return router

@pytest.fixture
def mock_uncertainty():
    uncertainty = MagicMock()
    uncertainty.evaluate.return_value = DummyCheck(confidence=0.9, is_suspicious=False)
    return uncertainty

@pytest.fixture
def mock_memory():
    memory = MagicMock()
    memory.merge_evidence = AsyncMock()
    return memory

@pytest.fixture
def mock_llm_gateway():
    llm = MagicMock()
    llm.query = AsyncMock(return_value="Verified Note")
    return llm

@pytest.fixture
def mock_injector():
    injector = MagicMock()
    injector.fetch_active_rules.return_value = {"rule": "test"}
    return injector

@pytest.fixture
def executor(mock_router, mock_uncertainty, mock_memory, mock_llm_gateway, mock_injector):
    e = PinealExecutor()
    e.router = mock_router
    e.uncertainty = mock_uncertainty
    e.memory = mock_memory
    e.llm_gateway = mock_llm_gateway
    e.injector = mock_injector
    
    # Mock agents
    for name in e.agents:
        e.agents[name] = MagicMock()
        e.agents[name].execute = AsyncMock(return_value=DummyResult())
        
    return e

@pytest.mark.asyncio
async def test_execute_task_full_flow(executor):
    input_data = {"target_profile": {"images": ["http://test.com/1.jpg"]}}
    
    # Mock download to avoid real network
    executor._download_images = AsyncMock(return_value=["/tmp/1.jpg"])
    
    status = await executor.execute_task(input_data, "task_1")
    
    assert isinstance(status, TaskSnapshot)
    assert status.status == "completed"
    assert status.task_id == "task_1"
    assert len(status.evidence_chain) == 3 # 3 agents in route
    
    # Ensure memory was updated
    executor.memory.merge_evidence.assert_called_once()
    
    # Ensure route was analyzed
    executor.router.analyze.assert_called_once()

@pytest.mark.asyncio
async def test_execute_task_halt_low_confidence(executor):
    input_data = {}
    
    # Simulate low confidence on first agent
    executor.uncertainty.evaluate.return_value = DummyCheck(confidence=0.4, is_suspicious=False)
    
    status = await executor.execute_task(input_data, "task_2")
    
    assert status.status == "halted_evidence"
    assert len(status.evidence_chain) == 0 # It fails before appending if router cuts it
    
@pytest.mark.asyncio
async def test_execute_task_suspicious_research(executor):
    input_data = {}
    
    # Override router to only return a simple agent that doesn't expect specific fields on result
    class SimpleRoute:
        agents = ["human_behavior"]
    executor.router.analyze = AsyncMock(return_value=SimpleRoute())
    
    # First agent suspicious, deep research needed
    executor.uncertainty.evaluate.return_value = DummyCheck(confidence=0.8, is_suspicious=True, reason="Inconsistent")
    
    status = await executor.execute_task(input_data, "task_3")
    
    # Still completes if deep research doesn't raise exception
    assert status.status == "completed"
    executor.llm_gateway.query.assert_called() # Deep research called

@pytest.mark.asyncio
async def test_execute_task_frequency_mismatch(executor):
    input_data = {}
    
    # Make resonance calculator return low compatibility
    executor.agents["resonance_calc"].execute = AsyncMock(return_value=DummyResult(compatibility_score=0.5))
    
    status = await executor.execute_task(input_data, "task_4")
    
    assert status.status == "halted_frequency"
    # Should have appended evidence for human_behavior, mirror_truth, and resonance_calc
    assert len(status.evidence_chain) == 3
