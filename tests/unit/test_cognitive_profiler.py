import pytest
from unittest.mock import AsyncMock, MagicMock
from agent_core.agents.cognitive_profiler import CognitiveProfilerAgent
from agent_core.domain.memory_models import CognitiveStyle
from agent_core.services.llm_gateway import LLMGateway

@pytest.mark.asyncio
async def test_cognitive_profiler_empty_data():
    agent = CognitiveProfilerAgent()
    res = await agent.execute({})
    assert isinstance(res, CognitiveStyle)
    assert res.communication_tone == "dengeli"
    assert res.confidence == 0.2

@pytest.mark.asyncio
async def test_cognitive_profiler_with_data():
    mock_gateway = MagicMock(spec=LLMGateway)
    mock_gateway.query_json = AsyncMock(return_value=CognitiveStyle(
        communication_tone="analitik",
        complexity_level="kavramsal",
        humor_style="kuru mizah",
        social_orientation="gözlemci",
        confidence=0.9
    ))
    
    agent = CognitiveProfilerAgent(llm_gateway=mock_gateway)
    payload = {
        "target_profile": {
            "bio": "Veri analisti ve felsefe meraklısı.",
            "posts": ["Mantıksal çıkarımlar duyguların filtresidir."]
        }
    }
    res = await agent.execute(payload)
    assert isinstance(res, CognitiveStyle)
    assert res.communication_tone == "analitik"
    assert res.complexity_level == "kavramsal"
    assert res.humor_style == "kuru mizah"
    assert res.social_orientation == "gözlemci"
    assert res.confidence == 0.9
