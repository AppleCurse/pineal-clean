import pytest
from unittest.mock import AsyncMock
from pydantic import BaseModel
from agent_core.services.llm_gateway import LLMGateway
from agent_core.agents.depth_analyst import DepthAnalyst, DepthReport
from agent_core.agents.autonomous_verifier import AutonomousVerifier
from agent_core.agents.resonance_synthesizer import ResonanceSynthesizerAgent

class SampleSchema(BaseModel):
    title: str
    score: float

def test_default_chains_and_env_overrides(monkeypatch):
    gw = LLMGateway()
    
    # 1. Varsayılan zincirler
    assert gw.get_chain("depth") == ["upstage/solar-pro4", "z-ai/glm-5.2", "deepseek/deepseek-v4-pro"]
    assert gw.get_chain("vision") == ["google/gemini-3.7-flash"]
    assert gw.get_chain("dialogue") == ["upstage/solar-pro4", "deepseek/deepseek-v4-flash"]
    assert gw.get_chain("fast") == ["inclusionai/ling-3.0-flash", "deepseek/deepseek-v4-flash"]
    
    # 2. Env ile ezilebilirlik
    monkeypatch.setenv("OPENROUTER_CHAIN_DEPTH", "custom/model-1, custom/model-2")
    monkeypatch.setenv("OPENROUTER_CHAIN_FAST", "openai/gpt-4o-mini")
    
    assert gw.get_chain("depth") == ["custom/model-1", "custom/model-2"]
    assert gw.get_chain("fast") == ["openai/gpt-4o-mini"]

@pytest.mark.asyncio
async def test_query_chain_fallback_on_server_error():
    gw = LLMGateway()
    gw.api_key = "sk-test"
    gw.live_unlocked = True

    call_count = 0
    async def mock_query(prompt, model=None, **kwargs):
        nonlocal call_count
        call_count += 1
        if model == "upstage/solar-pro4":
            raise RuntimeError("503 Service Unavailable: Overloaded")
        return f"OK from {model}"

    gw.query = AsyncMock(side_effect=mock_query)

    res = await gw.query_chain("test prompt", task="depth")
    assert res == "OK from z-ai/glm-5.2"
    assert call_count == 2

@pytest.mark.asyncio
async def test_query_chain_auth_error_does_not_fallback():
    gw = LLMGateway()
    gw.api_key = "sk-test"
    gw.live_unlocked = True

    call_count = 0
    async def mock_query(prompt, model=None, **kwargs):
        nonlocal call_count
        call_count += 1
        raise RuntimeError("401 Unauthorized: Invalid API Key")

    gw.query = AsyncMock(side_effect=mock_query)

    with pytest.raises(RuntimeError, match="401 Unauthorized"):
        await gw.query_chain("test prompt", task="depth")

    assert call_count == 1, "AUTH hatasında sıradaki modele düşülmemeli, hemen yükseltilmeli"

@pytest.mark.asyncio
async def test_query_json_chain_fallback_on_schema_error():
    gw = LLMGateway()
    gw.api_key = "sk-test"
    gw.live_unlocked = True

    call_count = 0
    async def mock_query_json(prompt, schema=None, model=None, **kwargs):
        nonlocal call_count
        call_count += 1
        if model == "upstage/solar-pro4":
            raise ValueError("JSON şema tamir edilemedi")
        return SampleSchema(title=f"Başarı: {model}", score=0.95)

    gw.query_json = AsyncMock(side_effect=mock_query_json)

    res = await gw.query_json_chain("JSON prompt", SampleSchema, task="depth")
    assert isinstance(res, SampleSchema)
    assert res.title == "Başarı: z-ai/glm-5.2"
    assert call_count == 2

@pytest.mark.asyncio
async def test_depth_analyst_wired_to_depth_chain():
    mock_gw = AsyncMock()
    mock_gw.query_json_chain.return_value = DepthReport(
        reality_index=0.85,
        reality_rationale="Kanıtlar tutarlı",
        reality_findings=[],
        contradictions=[],
        essence_one_liner="Stratejik ve derin gözlemci"
    )

    analyst = DepthAnalyst(llm_gateway=mock_gw)
    report = await analyst.analyze(
        input_data={"target_profile": {"bio": "Müzik yapımcısı", "posts": []}},
        evidence_chain=[]
    )

    assert report.reality_index == 0.85
    mock_gw.query_json_chain.assert_called_once()
    assert mock_gw.query_json_chain.call_args.kwargs.get("task") == "depth"

@pytest.mark.asyncio
async def test_autonomous_verifier_wired_to_fast_chain():
    mock_gw = AsyncMock()
    
    class MockClaimList(BaseModel):
        claims: list = []

    mock_gw.query_json_chain.return_value = MockClaimList(claims=[])

    mock_search = AsyncMock()
    mock_search.tavily_key = "test-tavily"

    verifier = AutonomousVerifier(search_engine=mock_search)
    report = await verifier.execute(
        input_data={"target_profile": {"bio": "Teknoloji Girişimcisi @ Pineal"}},
        memory=None,
        llm_gateway=mock_gw
    )

    assert report.status == "UNVERIFIED"
    mock_gw.query_json_chain.assert_called_once()
    assert mock_gw.query_json_chain.call_args.kwargs.get("task") == "fast"

@pytest.mark.asyncio
async def test_resonance_synthesizer_wired_to_dialogue_chain():
    mock_gw = AsyncMock()
    from agent_core.domain.memory_models import AuthenticBridge
    mock_gw.query_json_chain.return_value = AuthenticBridge(
        shared_passions=["Müzik prodüksiyonu"],
        complementary_perspectives=["Analog vs Dijital"],
        resonance_score=0.9,
        authentic_opening_topic="Analog Sentezleyiciler",
        conversation_starter_rationale="Ortak ilgi",
        suggested_opening_message="Gece kayıtlarında analog ses tasarımı üzerine konuşmak isterim."
    )

    agent = ResonanceSynthesizerAgent(llm_gateway=mock_gw)
    res = await agent.execute(payload={
        "user_profile": {"bio": "Müzisyen"},
        "passions": {"core_passions": ["Müzik"]}
    })

    assert res.resonance_score == 0.9
    mock_gw.query_json_chain.assert_called_once()
    assert mock_gw.query_json_chain.call_args.kwargs.get("task") == "dialogue"
