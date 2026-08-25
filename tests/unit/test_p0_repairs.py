import pytest

from agent_core.agents.autonomous_verifier import AutonomousVerifier
from agent_core.agents.resonance_calculator import ResonanceCalculator
from agent_core.services.canonical_memory import CanonicalMemory
from agent_core.services.uncertainty_engine import UncertaintyEngine, UncertaintyReport
from agent_core.task_executor import PinealExecutor
from agent_core.domain.pipeline_status import PipelineStatus


class ResonanceOnlyRoute:
    agents = ["resonance_calc"]


class PassThroughUncertainty(UncertaintyEngine):
    def evaluate(self, result, agent_name):
        return UncertaintyReport(confidence=0.9, is_suspicious=False, reason="test")


class RouteProvider:
    async def analyze(self, _):
        return ResonanceOnlyRoute()


@pytest.mark.asyncio
async def test_real_executor_uses_real_resonance_calculator(tmp_path):
    executor = PinealExecutor()
    executor.router = RouteProvider()
    executor.uncertainty = PassThroughUncertainty()
    executor.memory = CanonicalMemory(str(tmp_path))

    input_data = {
        "user_authentic_vector": {"depth": 0.9, "energy": 0.3},
        "target_authentic_vector": {"depth": 0.1, "energy": 0.9},
        "target_profile": {},
    }

    status = await executor.execute_task(input_data, "red_resonance")

    assert status.status == "halted_frequency"
    assert any(e["agent"] == "resonance_calc" for e in status.evidence_chain)
    assert isinstance(executor.agents["resonance_calc"], ResonanceCalculator)


@pytest.mark.asyncio
async def test_resonance_failure_marks_task_failed(tmp_path):
    class FailingResonance(ResonanceCalculator):
        async def execute(self, input_data, memory, llm_gateway):
            raise RuntimeError("synthetic resonance failure")

    executor = PinealExecutor()
    executor.router = RouteProvider()
    executor.memory = CanonicalMemory(str(tmp_path))
    executor.agents["resonance_calc"] = FailingResonance()

    status = await executor.execute_task({"target_profile": {}}, "red_failure")

    assert status.status in ("failed", "partially_completed", PipelineStatus.PARTIALLY_COMPLETED)


@pytest.mark.asyncio
async def test_verifier_without_bio_or_key_is_unverified():
    class NoKeySearch:
        tavily_key = None

    verifier = AutonomousVerifier(NoKeySearch())
    report = await verifier.execute({"target_profile": {}}, None, None)

    assert report.status == "UNVERIFIED"
    assert report.overall_authenticity_score == 0.0
    assert report.verifications == []
