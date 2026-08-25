import pytest

from agent_core.services.cognitive_router import CognitiveRouter


@pytest.mark.asyncio
async def test_router_does_not_schedule_osint_forensic_stamp_twice():
    route = await CognitiveRouter().analyze(
        {"user_profile": {"bio": "user"}, "target_profile": {"bio": "target"}}
    )

    assert "osint_investigator" not in route.agents
    assert "autonomous_verifier" in route.agents
