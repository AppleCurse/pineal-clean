import pytest
from unittest.mock import AsyncMock, MagicMock
from agent_core.agents.friction_detector import FrictionDetectorAgent
from agent_core.domain.memory_models import FrictionProfile
from agent_core.services.llm_gateway import LLMGateway

@pytest.mark.asyncio
async def test_friction_detector_empty_data():
    agent = FrictionDetectorAgent()
    res = await agent.execute({})
    assert isinstance(res, FrictionProfile)
    assert res.sensitivities == []
    assert res.confidence == 0.2

@pytest.mark.asyncio
async def test_friction_detector_with_data():
    mock_gateway = MagicMock(spec=LLMGateway)
    mock_gateway.query_json = AsyncMock(return_value=FrictionProfile(
        sensitivities=["Yüzeysel İletişim", "Zaman İsrafı"],
        stress_triggers=["Gereksiz Toplantılar"],
        boundary_signals=["Özel Hayat Saygısı"],
        evidence_quotes=["Boş muhabbet enerjimi tüketiyor."],
        confidence=0.85
    ))
    
    agent = FrictionDetectorAgent(llm_gateway=mock_gateway)
    payload = {
        "target_profile": {
            "bio": "Derinlik arayan bir araştırmacı.",
            "posts": ["Boş muhabbet enerjimi tüketiyor.", "Sessizlik bazen en iyi cevaptır."]
        }
    }
    res = await agent.execute(payload)
    assert isinstance(res, FrictionProfile)
    assert "Yüzeysel İletişim" in res.sensitivities
    assert "Özel Hayat Saygısı" in res.boundary_signals
    assert res.confidence == 0.85
