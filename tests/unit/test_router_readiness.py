import pytest

from agent_core.services.cognitive_router import CognitiveRouter


@pytest.mark.asyncio
async def test_empty_profile_objects_do_not_schedule_analysis_agents():
    route = await CognitiveRouter().analyze({"user_profile": {}, "target_profile": {}})
    assert route.agents == []


@pytest.mark.asyncio
async def test_target_text_schedules_target_analysis_but_not_resonance_without_user_evidence():
    route = await CognitiveRouter().analyze({"target_profile": {"bio": "designer"}, "user_profile": {}})
    assert "human_behavior" in route.agents
    assert "resonance_calc" not in route.agents
