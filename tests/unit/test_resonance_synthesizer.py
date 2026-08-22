import pytest
from unittest.mock import AsyncMock, MagicMock
from agent_core.agents.resonance_synthesizer import ResonanceSynthesizerAgent
from agent_core.domain.memory_models import AuthenticBridge
from agent_core.services.llm_gateway import LLMGateway

@pytest.mark.asyncio
async def test_resonance_synthesizer_fallback():
    mock_gateway = MagicMock(spec=LLMGateway)
    mock_gateway.query_json = AsyncMock(side_effect=RuntimeError("LLM Hatası"))
    
    agent = ResonanceSynthesizerAgent(llm_gateway=mock_gateway)
    res = await agent.execute({})
    assert isinstance(res, AuthenticBridge)
    assert res.confidence == 0.4
    assert res.resonance_score == 0.5

@pytest.mark.asyncio
async def test_resonance_synthesizer_success():
    mock_gateway = MagicMock(spec=LLMGateway)
    mock_gateway.query_json = AsyncMock(return_value=AuthenticBridge(
        shared_passions=["Sokak Fotoğrafçılığı", "Mimari Estetik"],
        complementary_perspectives=["Işık ve Gölge Yorumları"],
        resonance_score=0.92,
        authentic_opening_topic="Kentsel Dönüşümde Estetik Detaylar",
        conversation_starter_rationale="İki taraf da görsel kompozisyon ve mekan algısına önem veriyor.",
        suggested_opening_message="Merhaba! Son paylaştığınız sokak çekimindeki ışık açısı çok etkileyiciydi, mekan estetiği üzerine benzer bir bakış açımız olduğunu hissettim.",
        confidence=0.95
    ))
    
    agent = ResonanceSynthesizerAgent(llm_gateway=mock_gateway)
    payload = {
        "user_profile": {"bio": "Görsel hikaye anlatıcısı.", "posts": ["Işığın peşinde."]},
        "passions": {"core_passions": ["Sokak Fotoğrafçılığı"]},
        "frictions": {"sensitivities": ["Yüzeysellik"]},
        "cognitive": {"communication_tone": "samimi"},
        "sacred_rules": "Ucuz manipülasyon yapma, sahici ol."
    }
    res = await agent.execute(payload)
    assert isinstance(res, AuthenticBridge)
    assert res.resonance_score == 0.92
    assert "Sokak Fotoğrafçılığı" in res.shared_passions
    assert "Merhaba!" in res.suggested_opening_message
