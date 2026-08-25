from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_core.domain.memory_models import AuthenticBridge
from agent_core.domain.pipeline_status import PipelineStatus
from agent_core.task_executor import PinealExecutor


class DeferredOnlyRoute:
    agents = ["resonance_synthesizer"]


@pytest.fixture
def executor():
    instance = PinealExecutor()
    instance.router.analyze = AsyncMock(return_value=DeferredOnlyRoute())
    instance.memory = MagicMock()
    instance.memory.merge_evidence = AsyncMock()
    instance.injector.fetch_active_rules = MagicMock(return_value={})
    return instance


@pytest.mark.asyncio
async def test_deferred_agent_low_confidence_is_not_written_as_evidence(executor):
    executor.agents["resonance_synthesizer"].execute = AsyncMock(
        return_value=AuthenticBridge(
            shared_passions=["music"],
            confidence=0.9,
        )
    )
    executor.uncertainty.evaluate = MagicMock(
        return_value=MagicMock(confidence=0.1, is_suspicious=True, reason="insufficient evidence")
    )

    status = await executor.execute_task({"target_profile": {}}, "deferred_low_confidence")

    run = status.agent_runs["resonance_synthesizer"]
    assert run.status == "halted"
    assert run.error_code == "LOW_CONFIDENCE"
    assert "resonance_synthesizer" not in [item["agent"] for item in status.evidence_chain]
    assert status.status == PipelineStatus.PARTIALLY_COMPLETED


@pytest.mark.asyncio
async def test_deferred_agent_invalid_output_is_not_written_as_evidence(executor):
    executor.agents["resonance_synthesizer"].execute = AsyncMock(return_value={"not": "a BaseModel"})

    status = await executor.execute_task({"target_profile": {}}, "deferred_invalid_output")

    run = status.agent_runs["resonance_synthesizer"]
    assert run.status == "failed"
    assert run.error_code == "TypeError"
    assert "resonance_synthesizer" not in [item["agent"] for item in status.evidence_chain]
    assert status.status == PipelineStatus.PARTIALLY_COMPLETED
