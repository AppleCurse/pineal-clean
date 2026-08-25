from unittest.mock import AsyncMock, MagicMock

import pytest

from agent_core.domain.pipeline_status import PipelineStatus
from agent_core.engines.pillar_orchestrator import PillarOrchestrator
from agent_core.task_executor import PinealExecutor


@pytest.mark.asyncio
async def test_pillar_failure_is_evidence_and_halts_by_explicit_policy(monkeypatch):
    async def fail_run(self, _input):
        raise RuntimeError("synthetic pillar outage")

    monkeypatch.setattr(PillarOrchestrator, "run", fail_run)
    executor = PinealExecutor()
    executor.memory = MagicMock()
    executor.memory.merge_evidence = AsyncMock()

    status = await executor.execute_task({"target_profile": {}}, "pillar_failure_policy")

    assert status.status == PipelineStatus.HALTED_CRITICAL
    assert status.agent_runs["pineal_7pillar"].status == "failed"
    failure = next(item for item in status.evidence_chain if item["agent"] == "pineal_7pillar")
    assert failure["evidence_type"] == "execution_failure"
    assert failure["result"]["error_code"] == "RuntimeError"
    executor.memory.merge_evidence.assert_awaited_once()
