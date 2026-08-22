import pytest
from unittest.mock import AsyncMock, MagicMock
from agent_core.agents.passion_mapper import PassionMapperAgent
from agent_core.domain.memory_models import PassionProfile
from agent_core.services.llm_gateway import LLMGateway

@pytest.mark.asyncio
async def test_passion_mapper_empty_data():
    agent = PassionMapperAgent()
    res = await agent.execute({})
    assert isinstance(res, PassionProfile)
    assert res.core_passions == []
    assert res.confidence == 0.2

@pytest.mark.asyncio
async def test_passion_mapper_with_data():
    mock_gateway = MagicMock(spec=LLMGateway)
    mock_gateway.query_json = AsyncMock(return_value=PassionProfile(
        core_passions=["Mimari", "Fotoğrafçılık"],
        energizing_topics=["Minimalist Tasarım", "Işık Oyunları"],
        flow_triggers=["Sokak Çekimleri"],
        sentiment_polarity=0.7,
        evidence_quotes=["Estetik detaylar hayatın özüdür."],
        confidence=0.9
    ))
    
    agent = PassionMapperAgent(llm_gateway=mock_gateway)
    payload = {
        "target_profile": {
            "bio": "Mimar ve fotoğraf tutkunu.",
            "posts": ["Estetik detaylar hayatın özüdür.", "Yeni bir perspektif yakalamak harika."]
        }
    }
    res = await agent.execute(payload)
    assert isinstance(res, PassionProfile)
    assert "Mimari" in res.core_passions
    assert "Fotoğrafçılık" in res.core_passions
    assert res.sentiment_polarity == 0.7
    assert res.confidence == 0.9
