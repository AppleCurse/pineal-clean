import pytest

from agent_core.engines.pillar_orchestrator import PillarComponentError, PillarOrchestrator


class BrokenFrequency:
    async def analyze(self, _data):
        raise RuntimeError("synthetic frequency failure")


@pytest.mark.asyncio
async def test_component_failure_is_not_converted_to_success_like_bundle():
    orchestrator = PillarOrchestrator(frequency=BrokenFrequency())

    with pytest.raises(PillarComponentError, match="FREQUENCY failed"):
        await orchestrator.run({"target_profile": {}})
